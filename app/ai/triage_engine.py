from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from app.ai.types import CommentCategory, TriageDecision, TriageResult

_MULTI_SPACE_RE = re.compile(r"\s+")
_REPEAT_CHAR_RE = re.compile(r"(.)\1{6,}", re.UNICODE)
_REPEAT_WORD_RE = re.compile(r"\b(\w+)(\s+\1){3,}\b", re.IGNORECASE)


def _phrase_regex(phrases: List[str]) -> Optional[re.Pattern]:
    """One alternation of whole-word phrases, longest first.

    Substring matching produced false positives on ordinary English -- "help" in
    "helped", "subscribe" in "subscriber". Phrases are matched on word
    boundaries instead.
    """
    cleaned = [p.strip() for p in phrases if p and p.strip()]
    if not cleaned:
        return None
    cleaned.sort(key=len, reverse=True)
    alternation = "|".join(re.escape(p) for p in cleaned)
    return re.compile(rf"(?<!\w)(?:{alternation})(?!\w)", re.IGNORECASE | re.UNICODE)


def _normalize(text: str) -> str:
    # It trims edges and collapses any run of whitespace into a single space
    return _MULTI_SPACE_RE.sub(" ", (text or "").strip())


def _ratio(part: int, total: int) -> float:
    return (part / total) if total > 0 else 0.0


def _sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1 / (1 + z)
    z = math.exp(x)
    return z / (1 + z)


def _symbol_ratio(text: str) -> float:
    if not text:
        return 0.0
    symbols = sum(1 for c in text if not (c.isalnum() or c.isspace()))
    return _ratio(symbols, len(text))


@dataclass(frozen=True)
class TriageConfig:
    spam_threshold: float
    min_text_len: int
    hard_block_regex: List[re.Pattern]
    pii_regex: List[re.Pattern]
    spam_phrases: List[str]
    question_words: List[str]
    complaint_words: List[str]
    praise_words: List[str]
    ignore_exact: List[str]

    # Compiled whole-word matchers, derived from the word lists above.
    spam_phrase_re: Optional[re.Pattern] = None
    complaint_re: Optional[re.Pattern] = None
    praise_re: Optional[re.Pattern] = None

    @staticmethod
    def load(path: Path) -> "TriageConfig":
        data = json.loads(path.read_text(encoding="utf-8"))

        def compile_all(items: List[str]) -> List[re.Pattern]:
            return [re.compile(x, re.IGNORECASE | re.UNICODE) for x in items]

        spam_phrases = [s.lower() for s in data.get("spam_phrases", [])]
        complaint_words = [s.lower() for s in data.get("complaint_words", [])]
        praise_words = [s.lower() for s in data.get("praise_words", [])]

        return TriageConfig(
            spam_threshold=float(data.get("spam_threshold", 0.65)),
            min_text_len=int(data.get("min_text_len", 3)),
            hard_block_regex=compile_all(data.get("hard_block_regex", [])),
            pii_regex=compile_all(data.get("pii_regex", [])),
            spam_phrases=spam_phrases,
            question_words=[s.lower() for s in data.get("relevance_question_words", [])],
            complaint_words=complaint_words,
            praise_words=praise_words,
            ignore_exact=[s.lower() for s in data.get("ignore_exact", [])],
            spam_phrase_re=_phrase_regex(spam_phrases),
            complaint_re=_phrase_regex(complaint_words),
            praise_re=_phrase_regex(praise_words),
        )


class CommentTriageEngine:
    """
    Efficient, production-style triage:
    - hard block checks (links, contact, pii)
    - spam scoring (multi-signal)
    - relevance & category
    Returns explainable reasons + scores.
    """

    def __init__(self, cfg: TriageConfig):
        self.cfg = cfg

    def triage_text(self, text: str) -> TriageResult:
        """Takes one YouTube comment (text) and decides:
        - Ignore it
        - Mark it as spam
        - Send it to the LLM to draft a reply
        """
        raw = _normalize(text)
        t = raw.lower()
        reasons: List[str] = []

        # A) trivial ignore
        if not t or len(t) < self.cfg.min_text_len:
            return TriageResult(TriageDecision.IGNORE,CommentCategory.OTHER,["empty_or_too_short"],0.0,0.0,)

        if t in self.cfg.ignore_exact:
            return TriageResult(
                TriageDecision.IGNORE,CommentCategory.OTHER,["low_value_exact"],0.0,0.05,)

        # B) hard blocks (never send to LLM)
        for rx in self.cfg.hard_block_regex:
            if rx.search(raw):
                return TriageResult(TriageDecision.SPAM,CommentCategory.OTHER,["hard_block_match"],1.0,0.0,)

        for rx in self.cfg.pii_regex:
            if rx.search(raw):
                return TriageResult(TriageDecision.SPAM,CommentCategory.OTHER,["pii_detected"],1.0,0.0,)

        # C) spam scoring
        spam_score, spam_reasons = self._spam_score(t)
        reasons.extend(spam_reasons)

        if spam_score >= self.cfg.spam_threshold:
            return TriageResult(TriageDecision.SPAM,CommentCategory.OTHER,["spam_score_high"] + reasons,spam_score,0.0,)

        # D) relevance + category
        category, rel_score, rel_reasons = self._relevance_and_category(raw)
        reasons.extend(rel_reasons)

        # Conservative routing
        if category in (CommentCategory.QUESTION, CommentCategory.COMPLAINT):
            return TriageResult(TriageDecision.DRAFT_REPLY, category, reasons, spam_score, rel_score)

        # Praise can be drafted if it is meaningful (optional engagement)
        if category == CommentCategory.PRAISE and rel_score >= 0.35:
            return TriageResult(TriageDecision.DRAFT_REPLY, category, reasons, spam_score, rel_score)

        return TriageResult(
            TriageDecision.IGNORE,
            category,
            ["low_relevance"] + reasons,
            spam_score,
            rel_score,
        )

    def _spam_score(self, raw: str) -> Tuple[float, List[str]]:
        t = raw.lower()
        reasons: List[str] = []
        score = 0.0

        hits = len(self.cfg.spam_phrase_re.findall(t)) if self.cfg.spam_phrase_re else 0
        if hits:
            score += min(0.60, 0.18 * hits)
            reasons.append(f"spam_phrases:{hits}")

        if _REPEAT_CHAR_RE.search(raw):
            score += 0.18
            reasons.append("repeat_chars")

        if _REPEAT_WORD_RE.search(t):
            score += 0.25
            reasons.append("repeat_words")

        sym = _symbol_ratio(raw)
        if sym > 0.35:
            score += min(0.22, (sym - 0.35) * 0.6)
            reasons.append(f"symbol_ratio:{sym:.2f}")

        # bound to 0..1
        bounded = _sigmoid((score - 0.45) * 3.2)
        final = max(bounded, min(score, 0.95))
        return final, reasons

    def _relevance_and_category(self, raw: str) -> Tuple[CommentCategory, float, List[str]]:
        t = raw.lower()
        reasons: List[str] = []
        rel = 0.10  # base

        if "?" in raw or any(t.startswith(w + " ") for w in self.cfg.question_words):
            reasons.append("question_intent")
            rel += 0.55
            return CommentCategory.QUESTION, min(rel, 1.0), reasons

        if self.cfg.complaint_re and self.cfg.complaint_re.search(t):
            reasons.append("complaint_intent")
            rel += 0.50
            return CommentCategory.COMPLAINT, min(rel, 1.0), reasons

        if self.cfg.praise_re and self.cfg.praise_re.search(t):
            reasons.append("praise_intent")
            rel += 0.25

        if len(t) >= 20:
            rel += 0.10
        if len(t) >= 60:
            rel += 0.10

        category = CommentCategory.PRAISE if "praise_intent" in reasons else CommentCategory.OTHER
        return category, min(rel, 1.0), reasons
