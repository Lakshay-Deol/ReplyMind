"""Persistence for detected audience signals.

The dashboards (recommendations, superfans, moderation) previously rendered
hardcoded examples. They now read from here: every triaged comment gets its
opportunity signal written out, so what the UI shows is what the engine found.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel

from app.ai.opportunity_models import OpportunityResult, OpportunitySignalType
from app.paths import signals_dir


class StoredSignal(BaseModel):
    comment_id: str
    author: str = ""
    text: str = ""
    signal_type: OpportunitySignalType
    confidence: float
    priority: int
    explanation: str
    recommended_action: str
    detected_at: str

    @property
    def short_text(self) -> str:
        t = (self.text or "").strip()
        return t if len(t) <= 220 else t[:217] + "..."


def save_signal(
    comment_id: str,
    signal: OpportunityResult,
    author: str = "",
    text: str = "",
) -> StoredSignal:
    stored = StoredSignal(
        comment_id=comment_id,
        author=author,
        text=text,
        signal_type=signal.signal_type,
        confidence=signal.confidence,
        priority=signal.priority,
        explanation=signal.explanation,
        recommended_action=signal.recommended_action,
        detected_at=datetime.now(timezone.utc).isoformat(),
    )
    try:
        directory = signals_dir()
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{comment_id}.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(stored.model_dump_json(indent=2), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        pass
    return stored


def list_signals(
    signal_types: Optional[List[OpportunitySignalType]] = None,
    min_priority: int = 0,
    limit: int = 200,
) -> List[StoredSignal]:
    """Return stored signals, highest priority first."""
    directory = signals_dir()
    if not directory.exists():
        return []

    out: List[StoredSignal] = []
    for path in directory.glob("*.json"):
        try:
            stored = StoredSignal.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if signal_types and stored.signal_type not in signal_types:
            continue
        if stored.priority < min_priority:
            continue
        out.append(stored)

    out.sort(key=lambda s: (s.priority, s.detected_at), reverse=True)
    return out[:limit]


def load_all() -> List[OpportunityResult]:
    """Rebuild plain OpportunityResults, for community-pulse aggregation."""
    return [
        OpportunityResult(
            signal_type=s.signal_type,
            confidence=s.confidence,
            priority=s.priority,
            explanation=s.explanation,
            recommended_action=s.recommended_action,
        )
        for s in list_signals(limit=10_000)
    ]


def count() -> int:
    directory = signals_dir()
    if not directory.exists():
        return 0
    return sum(1 for _ in directory.glob("*.json"))
