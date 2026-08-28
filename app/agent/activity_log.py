"""Append-only audit log of everything the ReplyMind agent does.

The /activity page used to render a hardcoded timeline. This module is the real
thing: every Mind call, triage sweep, recommendation and human decision appends
an event here, and the UI reads it back. It doubles as the evidence trail behind
the "no autonomous publishing" guarantee -- an approval is only meaningful if it
is recorded.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.paths import activity_path

MAX_EVENTS = 500


class ActivityEvent(BaseModel):
    at: str
    kind: str
    title: str
    detail: str = ""
    source: str = "replymind"
    meta: Dict[str, Any] = Field(default_factory=dict)


def record(
    kind: str,
    title: str,
    detail: str = "",
    source: str = "replymind",
    **meta: Any,
) -> ActivityEvent:
    """Append one event. Never raises -- logging must not break the pipeline."""
    event = ActivityEvent(
        at=datetime.now(timezone.utc).isoformat(),
        kind=kind,
        title=title,
        detail=detail,
        source=source,
        meta=meta,
    )
    try:
        path = activity_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(event.model_dump_json() + "\n")
    except OSError:
        pass
    return event


def read_events(limit: int = 60, kind: Optional[str] = None) -> List[ActivityEvent]:
    """Return the most recent events, newest first."""
    path = activity_path()
    if not path.exists():
        return []

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []

    events: List[ActivityEvent] = []
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            event = ActivityEvent.model_validate_json(line)
        except Exception:
            continue
        if kind and event.kind != kind:
            continue
        events.append(event)
        if len(events) >= limit:
            break
    return events


def compact() -> None:
    """Trim the log to MAX_EVENTS so a long-running monitor cannot grow it forever."""
    path = activity_path()
    if not path.exists():
        return
    try:
        lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    except OSError:
        return
    if len(lines) <= MAX_EVENTS:
        return
    try:
        tmp = path.with_suffix(".tmp")
        tmp.write_text("\n".join(lines[-MAX_EVENTS:]) + "\n", encoding="utf-8")
        tmp.replace(path)
    except OSError:
        pass
