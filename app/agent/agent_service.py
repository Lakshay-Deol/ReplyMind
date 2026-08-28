"""The single entry point to the persistent ReplyMind Mind.

This is the seam that makes the Mind integral rather than optional. Both the
review UI (/agent chat, comment analysis) and the background monitor call
through here, so there is exactly one code path that:

  1. assembles real creator context -- persistent memory, community pulse,
     and the highest-priority live audience signals,
  2. sends it to the persistent Mind over the Minds Builder API,
  3. records the exchange to the activity log and back into memory.

When the Minds service is unreachable we say so explicitly. We never fabricate
a reasoning trace, a wallet or a balance and present it as the Mind's output.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from app.agent import activity_log, signal_store
from app.agent.community_pulse import load_community_pulse
from app.agent.memory import load_memory, record_topic
from app.agent.minds_client import MindsClient, MindsUnavailable
from app.ai.opportunity_detector import detect_opportunities
from app.ai.opportunity_models import OpportunityResult
from app.ai.types import TriageResult

logger = logging.getLogger(__name__)

# One stable alias keeps a single long-running conversation with the Mind, which
# is what gives it continuity across sessions. Per-comment analysis uses its own
# alias so a specific thread's reasoning stays separable.
CONSOLE_ALIAS = "replymind-console"

# Only signals at or above this priority are escalated to the Mind for reasoning.
DEFAULT_MIND_REVIEW_THRESHOLD = 70


def mind_review_threshold() -> int:
    """Priority at or above which a comment is worth a Mind call."""
    try:
        return int(os.getenv("REPLYMIND_MIND_REVIEW_THRESHOLD", DEFAULT_MIND_REVIEW_THRESHOLD))
    except ValueError:
        return DEFAULT_MIND_REVIEW_THRESHOLD

ROLE_BRIEF = (
    "You are ReplyMind, a persistent AI community manager for a content creator. "
    "You reason over the creator's audience signals and your own long-term memory of "
    "their preferences, then recommend the single next best action. "
    "Be specific and cite the evidence you were given. Keep answers under 180 words. "
    "Never claim to have published anything: every external action requires the "
    "creator's explicit approval."
)


class AgentAnswer(BaseModel):
    question: str
    answer: str
    source: str  # "minds" | "unavailable"
    context_used: Dict[str, Any] = {}

    @property
    def ok(self) -> bool:
        return self.source == "minds"


def is_production() -> bool:
    return os.getenv("REPLYMIND_MODE", "demo").lower() == "production"


def build_context() -> Dict[str, Any]:
    """Assemble the real creator context handed to the Mind."""
    memory = load_memory()
    pulse = load_community_pulse()
    top_signals = signal_store.list_signals(limit=8)

    return {
        "profile": {
            "name": memory.creator_profile.creator_name,
            "niche": memory.creator_profile.niche,
            "tone": memory.creator_profile.tone,
            "reply_length": memory.creator_profile.preferred_reply_length,
            "goals": memory.creator_profile.goals,
            "avoid": memory.creator_profile.topics_to_avoid,
        },
        "learned_preferences": {
            "approved": memory.approved_preferences[-6:],
            "rejected": memory.rejected_preferences[-6:],
        },
        "recurring_questions": dict(list(memory.recurring_questions.items())[:8]),
        "recurring_topics": dict(list(memory.recurring_topics.items())[:8]),
        "decisions_recorded": len(memory.previous_decisions),
        "pulse": pulse.model_dump() if pulse else None,
        "top_signals": [
            {
                "author": s.author,
                "type": s.signal_type.value,
                "priority": s.priority,
                "text": s.short_text,
                "recommended_action": s.recommended_action,
            }
            for s in top_signals
        ],
    }


def _render_context(ctx: Dict[str, Any]) -> str:
    lines: List[str] = []
    p = ctx["profile"]
    lines.append(
        f"CREATOR: {p['name']} | niche={p['niche']} | tone={p['tone']} | "
        f"preferred reply length={p['reply_length']}"
    )
    if p["goals"]:
        lines.append(f"GOALS: {', '.join(p['goals'])}")
    if p["avoid"]:
        lines.append(f"AVOID: {', '.join(p['avoid'])}")

    prefs = ctx["learned_preferences"]
    if prefs["approved"]:
        lines.append(f"LEARNED (approved): {'; '.join(prefs['approved'])}")
    if prefs["rejected"]:
        lines.append(f"LEARNED (rejected): {'; '.join(prefs['rejected'])}")
    lines.append(f"DECISIONS RECORDED: {ctx['decisions_recorded']}")

    if ctx["recurring_questions"]:
        rq = ", ".join(f"{k} (x{v})" for k, v in ctx["recurring_questions"].items())
        lines.append(f"RECURRING QUESTIONS: {rq}")
    if ctx["recurring_topics"]:
        rt = ", ".join(f"{k} (x{v})" for k, v in ctx["recurring_topics"].items())
        lines.append(f"RECURRING TOPICS: {rt}")

    pulse = ctx.get("pulse")
    if pulse:
        lines.append(
            "COMMUNITY PULSE: "
            f"{pulse['total_comments_analyzed']} analyzed, "
            f"{pulse['high_priority_comments']} high-priority, "
            f"{pulse['questions']} questions, "
            f"{pulse['content_requests']} content requests, "
            f"{pulse['complaints']} complaints, "
            f"{pulse['potential_superfans']} superfans, "
            f"{pulse['spam']} spam"
        )

    if ctx["top_signals"]:
        lines.append("TOP LIVE SIGNALS:")
        for s in ctx["top_signals"]:
            lines.append(
                f"  - [{s['type']} p{s['priority']}] @{s['author'] or 'viewer'}: "
                f"\"{s['text']}\" -> suggested: {s['recommended_action']}"
            )

    return "\n".join(lines)


def ask(question: str, client: Optional[MindsClient] = None) -> AgentAnswer:
    """Put a creator question to the persistent Mind, with full real context."""
    question = (question or "").strip()
    if not question:
        return AgentAnswer(
            question="",
            answer="Ask ReplyMind something about your community.",
            source="unavailable",
        )

    minds = client or MindsClient()
    ctx = build_context()
    message = (
        f"{ROLE_BRIEF}\n\n"
        f"--- CURRENT CREATOR CONTEXT ---\n{_render_context(ctx)}\n\n"
        f"--- CREATOR QUESTION ---\n{question}"
    )

    try:
        reply = minds.send_message(alias=CONSOLE_ALIAS, message=message)
    except MindsUnavailable as exc:
        logger.warning("Minds service unavailable: %s", exc)
        activity_log.record(
            "minds_unavailable",
            "Mind unreachable",
            str(exc),
            source="minds",
            question=question,
        )
        return AgentAnswer(
            question=question,
            answer=(
                "The ReplyMind Mind is not reachable right now, so there is no "
                "reasoning to show. Start the Minds integration service "
                "(cd minds-service && npm start) and confirm MINDS_BUILDER_API_KEY "
                "and MINDS_MIND_ID are set.\n\n"
                f"Details: {exc}"
            ),
            source="unavailable",
            context_used=ctx,
        )

    activity_log.record(
        "minds_reasoning",
        "Mind answered a creator question",
        question,
        source="minds",
        signals_in_context=len(ctx["top_signals"]),
    )
    # Asking about a topic is itself a signal about what the creator cares about.
    record_topic(question[:60], is_question=True)

    return AgentAnswer(question=question, answer=reply, source="minds", context_used=ctx)


def analyze_comment(
    comment_id: str,
    comment_text: str,
    triage_result: TriageResult,
    author: str = "",
    client: Optional[MindsClient] = None,
) -> signal_store.StoredSignal:
    """Detect the audience signal for one comment and persist it.

    In production mode the persistent Mind is consulted for its reasoning and
    that reasoning replaces the rule-based explanation.
    """
    signal: OpportunityResult = detect_opportunities(comment_text, triage_result)

    # Consulting the Mind costs cognition, and a cycle can triage dozens of
    # comments. Spending a call on every "thanks!" would drain a creator's
    # balance on the comments least in need of judgement, so the Mind is asked
    # only about signals the rule-based pass already ranks as consequential.
    if is_production() and signal.priority >= mind_review_threshold():
        minds = client or MindsClient()
        prompt = (
            f"{ROLE_BRIEF}\n\n"
            f"A new comment arrived from @{author or 'viewer'}: \"{comment_text}\"\n"
            f"Rule-based triage says: {triage_result.decision.value} / "
            f"{triage_result.category.value}. Detected signal: {signal.signal_type.value} "
            f"(priority {signal.priority}).\n\n"
            "In two sentences: is that read correct, and what is the single best next "
            "action for the creator?"
        )
        try:
            reasoning = minds.send_message(alias=f"comment-{comment_id}", message=prompt)
            signal = signal.model_copy(update={"explanation": reasoning.strip()})
            activity_log.record(
                "minds_reasoning",
                f"Mind reasoned over a {signal.signal_type.value.lower()} signal",
                reasoning.strip()[:240],
                source="minds",
                comment_id=comment_id,
            )
        except MindsUnavailable as exc:
            logger.warning("Minds reasoning skipped for %s: %s", comment_id, exc)

    stored = signal_store.save_signal(
        comment_id=comment_id, signal=signal, author=author, text=comment_text
    )
    activity_log.record(
        "signal_detected",
        f"{signal.signal_type.value} detected",
        signal.recommended_action,
        comment_id=comment_id,
        priority=signal.priority,
    )
    return stored


def health(client: Optional[MindsClient] = None) -> Dict[str, Any]:
    """Live status of the Mind. Reports unreachable honestly."""
    minds = client or MindsClient()
    try:
        status = minds.check_status()
        return {"connected": True, **status}
    except MindsUnavailable as exc:
        return {"connected": False, "error": str(exc)}
