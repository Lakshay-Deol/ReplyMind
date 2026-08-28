"""Background monitor: poll YouTube, triage, and let the Mind reason over signals.

The previous version could not start. It constructed FetchCommentsTool() and
AnalyzeSignalsTool(detector) with the wrong arity, called a method
(process_new_comment) that does not exist, and duck-typed TriageResult with
objects whose .decision never compared equal to the TriageDecision enum -- so
spam and complaint detection silently degraded to keyword matching.

It now drives the same app.agent.agent_service used by the review UI, so the
scheduled path and the interactive path exercise one code path.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import List

from app.agent import activity_log
from app.agent.agent_service import analyze_comment
from app.agent.community_pulse import generate_community_pulse, save_community_pulse
from app.ai.opportunity_models import OpportunityResult
from app.ai.types import CommentCategory, TriageDecision, TriageResult
from app.paths import triage_dir

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("replymind.monitor")



def _triage_from_record(data: dict) -> TriageResult:
    """Rebuild a real TriageResult from a persisted triage record.

    Reconstructing the actual enums matters: the old DummyT used
    type('obj', (object,), {'value': ...}), so every `== TriageDecision.SPAM`
    check in the detector evaluated False.
    """
    try:
        decision = TriageDecision(data.get("decision", "ignore"))
    except ValueError:
        decision = TriageDecision.IGNORE
    try:
        category = CommentCategory(data.get("category", "other"))
    except ValueError:
        category = CommentCategory.OTHER

    return TriageResult(
        decision=decision,
        category=category,
        reasons=list(data.get("reasons", [])),
        spam_score=float(data.get("spam_score", 0.0) or 0.0),
        relevance_score=float(data.get("relevance_score", 0.0) or 0.0),
    )


def analyze_triaged_comments() -> List[OpportunityResult]:
    """Run signal detection over every triaged comment and refresh the pulse."""
    directory = triage_dir()
    if not directory.exists():
        logger.info("No triage records yet at %s", directory)
        return []

    signals: List[OpportunityResult] = []
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Skipping unreadable triage record %s: %s", path.name, exc)
            continue

        comment_id = data.get("comment_id")
        if not comment_id:
            continue

        try:
            stored = analyze_comment(
                comment_id=comment_id,
                comment_text=data.get("text") or "",
                triage_result=_triage_from_record(data),
                author=data.get("author") or "",
            )
        except Exception as exc:
            logger.warning("Signal analysis failed for %s: %s", comment_id, exc)
            continue

        signals.append(
            OpportunityResult(
                signal_type=stored.signal_type,
                confidence=stored.confidence,
                priority=stored.priority,
                explanation=stored.explanation,
                recommended_action=stored.recommended_action,
            )
        )

    if signals:
        pulse = generate_community_pulse(signals)
        save_community_pulse(pulse)
        logger.info(
            "Pulse updated: %d analyzed, %d high-priority",
            pulse.total_comments_analyzed,
            pulse.high_priority_comments,
        )
        activity_log.record(
            "pulse_updated",
            "Community pulse recalculated",
            f"{pulse.total_comments_analyzed} comments analyzed, "
            f"{pulse.high_priority_comments} high-priority",
            signals=len(signals),
        )

    return signals


def run_cycle() -> dict:
    """One full pass: fetch + triage + draft, then detect signals and reason."""
    from main import run_once  # imported lazily; run_once needs YouTube credentials

    summary = {"fetched": 0, "drafts_saved": 0, "failures": 0}
    try:
        summary = run_once()
        activity_log.record(
            "fetch",
            "Fetched and triaged new comments",
            f"{summary.get('fetched', 0)} fetched, {summary.get('drafts_saved', 0)} drafted",
            **summary,
        )
    except Exception as exc:
        logger.error("Fetch/triage cycle failed: %s", exc)
        activity_log.record("error", "Fetch cycle failed", str(exc))

    signals = analyze_triaged_comments()
    activity_log.compact()

    return {**summary, "signals": len(signals)}


def run_monitor() -> None:
    if os.getenv("REPLYMIND_MONITOR_ENABLED", "false").lower() != "true":
        logger.info("Monitor disabled. Set REPLYMIND_MONITOR_ENABLED=true to run.")
        return

    interval_mins = int(os.getenv("REPLYMIND_INTERVAL_MINUTES", "30"))
    logger.info("Starting ReplyMind monitor. Interval: %d min.", interval_mins)
    activity_log.record("monitor_started", "Background monitor started", f"every {interval_mins} min")

    while True:
        try:
            result = run_cycle()
            logger.info("Cycle complete: %s", result)
        except KeyboardInterrupt:
            logger.info("Monitor stopped.")
            activity_log.record("monitor_stopped", "Background monitor stopped")
            return
        except Exception as exc:
            logger.exception("Unexpected monitor error: %s", exc)

        logger.info("Sleeping %d minutes...", interval_mins)
        time.sleep(interval_mins * 60)


if __name__ == "__main__":
    run_monitor()
