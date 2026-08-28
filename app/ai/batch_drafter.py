from __future__ import annotations

import json
from dataclasses import replace
from typing import Any, Dict, List, Tuple

from app.ai.types import CommentCategory, DraftReply

SYSTEM_PROMPT = """
Draft short, polite, human YouTube replies for the channel owner.

Rules:
- Never invent facts; if unsure, ask ONE question.
- Never ask for contact info.
- If medical, legal, financial, abusive, hate, or threat content → needs_human=true.
- Output ONLY valid JSON (no markdown, no prose).

Input: list of comments.
Output: JSON array (same length), each item:
comment_id, reply_text, category (question|complaint|praise|other), confidence (0..1), needs_human (bool), reasons[].

"""


def _make_user_prompt(comments: List[Any]) -> str:
    # comments are your existing fetched comment objects from app.youtube.model
    lines = ["Draft replies for these comments:\n"]
    for i, c in enumerate(comments, start=1):
        text = (c.text or "").strip().replace("\n", " ")
        if len(text) > 300:
            text = text[:300] + "..."
        lines.append(f"{i}) comment_id: {c.comment_id}")
        lines.append(f"   author: {c.author}")
        lines.append(f"   text: {text}")
        lines.append("")
    lines.append("Return ONLY JSON array.")
    return "\n".join(lines)


def _fallback_drafts(comments: List[Any], reason: str) -> List[DraftReply]:
    """Deterministic, keyword-based drafts.

    Used when no OpenAI client is configured (demo mode on a fresh clone) or when
    the API is unavailable or out of quota. Every fallback draft is flagged
    needs_human, because a template is a starting point, not an answer.
    """
    drafts: List[DraftReply] = []
    for c in comments:
        txt_lower = (c.text or "").lower()
        author = c.author or "viewer"
        if "?" in txt_lower or any(q in txt_lower for q in ["how", "what", "where", "when", "why", "can you"]):
            cat = CommentCategory.QUESTION
            reply = f"Thanks for reaching out, @{author}! Great question—I'll share more details on this shortly."
        elif any(p in txt_lower for p in ["love", "great", "awesome", "amazing", "thanks", "thank you", "good"]):
            cat = CommentCategory.PRAISE
            reply = f"Thank you so much for the support, @{author}! Glad you enjoyed it."
        elif any(b in txt_lower for b in ["bad", "issue", "bug", "broken", "wrong", "fix", "dislike"]):
            cat = CommentCategory.COMPLAINT
            reply = f"Thanks for the feedback, @{author}. I appreciate you bringing this to my attention!"
        else:
            cat = CommentCategory.OTHER
            reply = f"Thanks for commenting, @{author}! I appreciate you sharing your thoughts."

        drafts.append(
            DraftReply(
                comment_id=c.comment_id,
                reply_text=reply,
                category=cat,
                confidence=0.7,
                needs_human=True,
                reasons=[f"fallback_draft: {reason}"],
            )
        )
    return drafts


def batch_draft_replies(
    comments: List[Any],
    openai_client=None,
) -> Tuple[List[DraftReply], List[Dict[str, Any]]]:
    """
    Returns:
      drafts: List[DraftReply]
      failures: list of {comment_id, error, raw}

    openai_client may be None -- demo mode on a fresh clone has no API key, and
    the product must still be explorable end to end.
    """
    if not comments:
        return [], []

    if openai_client is None:
        return _fallback_drafts(comments, "no OpenAI client configured"), []

    try:
        raw = openai_client.complete(
            system=SYSTEM_PROMPT,
            user=_make_user_prompt(comments),
            # ~160 tokens per drafted comment; 200 total truncated the JSON array
            # for any batch >1, so json.loads failed and every draft was lost.
            max_output_tokens=max(400, 160 * len(comments)),
        ).strip()
    except Exception as exc:
        return _fallback_drafts(comments, f"OpenAI unavailable: {exc}"), []

    failures: List[Dict[str, Any]] = []

    try:
        data = json.loads(raw)
        if not isinstance(data, list):
            raise ValueError("LLM output is not a JSON array")
    except Exception as e:
        # If batch fails, fail all items (but still return usable failure info)
        for c in comments:
            failures.append({"comment_id": c.comment_id, "error": f"batch_json_parse_failed:{e}", "raw": raw})
        return [], failures

    # Map drafts by comment_id for robustness
    drafts: List[DraftReply] = []
    by_id = {c.comment_id: c for c in comments}

    for item in data:
        try:
            cid = str(item.get("comment_id", "")).strip()
            if cid not in by_id:
                raise ValueError("unknown_comment_id_returned")

            draft = DraftReply(
                comment_id=cid,
                reply_text=str(item.get("reply_text", "")).strip(),
                category=CommentCategory(str(item.get("category", "other")).strip()),
                confidence=float(item.get("confidence", 0.5)),
                needs_human=bool(item.get("needs_human", True)),
                reasons=list(item.get("reasons", [])),
            )

            # Guardrails.
            # DraftReply is a frozen dataclass, so these must go through
            # dataclasses.replace(). Assigning directly raised FrozenInstanceError,
            # which the except below swallowed -- silently discarding exactly the
            # low-confidence drafts that most needed a human to look at them.
            reasons = list(draft.reasons)

            if not draft.reply_text:
                reasons.append("empty_reply_text")
                draft = replace(
                    draft,
                    reply_text="Thanks for your comment! Can you clarify a bit so I can help accurately?",
                    needs_human=True,
                )

            if draft.confidence < 0.55:
                reasons.append("low_confidence")
                draft = replace(draft, needs_human=True)

            drafts.append(replace(draft, reasons=reasons))

        except Exception as e:
            failures.append({"comment_id": item.get("comment_id", None), "error": f"item_parse_failed:{e}", "raw": item})

    # If model missed some comment_ids, record failures
    drafted_ids = {d.comment_id for d in drafts}
    missing = [c.comment_id for c in comments if c.comment_id not in drafted_ids]
    for cid in missing:
        failures.append({"comment_id": cid, "error": "missing_from_batch_output", "raw": raw})

    return drafts, failures
