from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

from app.paths import metrics_path


class Metrics:
    def __init__(self, path: Path | None = None):
        if path is None:
            path = metrics_path()
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text(json.dumps({}, indent=2), encoding="utf-8")

    def inc(self, key: str, n: int = 1) -> None:
        data = self._read()
        data[key] = int(data.get(key, 0)) + n
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _read(self) -> Dict:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        

# ---------------------------
# Dashboard helpers (UI)
# ---------------------------

def read_triage(runtime_dir: Path, comment_id: str) -> dict[str, Any]:
    """
    Reads runtime/triage/<comment_id>.json if present.
    Returns {} if not found or invalid.
    """
    p = runtime_dir / "triage" / f"{comment_id}.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def build_dashboard(runtime_dir: Path, drafts: List[Any]) -> dict[str, Any]:
    """
    drafts: list of DraftRecord (has comment_id, original_text, etc.)
    Returns:
      {
        "cards": [{"label":..., "value":..., "hint":...}, ...],
        "insights": {"top_intent":..., "top_keywords":[...], "risk_alerts":[...]}
      }
    """

    # Read triage for each draft (if exists)
    triages = []
    for d in drafts:
        triages.append(read_triage(runtime_dir, d.comment_id))

    def _label(t: dict[str, Any]) -> str:
        return str(t.get("label") or t.get("category") or t.get("triage_label") or "").lower()

    labels = [_label(t) for t in triages]
    # spam_count = sum(1 for l in labels if "spam" in l)
    # high_priority = sum(1 for p in priorities if p in ("high", "urgent", "p1"))

    # processed count = number of json files in runtime/processed (optional)
    # processed_dir = runtime_dir / "processed"
    # processed_count = len(list(processed_dir.glob("*.json"))) if processed_dir.exists() else 0
    m = read_metrics(runtime_dir / "metrics.json")


    cards = [
         {"label": "pending", "value": str(len(drafts)), "hint": "needs review"},
    {"label": "drafted by ai", "value": str(int(m.get("llm_drafts_saved", 0))), "hint": "generated replies"},
    {"label": "posted", "value": str(int(m.get("posted", 0))), "hint": "successfully replied"},
    {"label": "rejected", "value": str(int(m.get("rejected", 0))), "hint": "needs attention"},
    ]

    # Insights
    filtered = [label for label in labels if label and "spam" not in label]
    top_intent = Counter(filtered).most_common(1)[0][0] if filtered else None

    # keyword extraction (simple, good enough for demo)
    words: list[str] = []
    for d in drafts:
        txt = (d.original_text or "").lower()
        for w in txt.split():
            w = "".join(ch for ch in w if ch.isalnum())
            if len(w) >= 4:
                words.append(w)
    top_keywords = [w for (w, _) in Counter(words).most_common(6)] if words else []

    # simple risk flag if toxic/abuse exists in labels
    risk_alerts: list[str] = []
    if any("toxic" in label or "abuse" in label or "hate" in label for label in labels):
        risk_alerts.append("possible toxic thread detected")

    insights = {
        "top_intent": top_intent,
        "top_keywords": top_keywords,
        "risk_alerts": risk_alerts,
    }

    return {"cards": cards, "insights": insights}


def read_metrics(runtime_metrics_path: Path) -> dict:
    try:
        return json.loads(runtime_metrics_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    
def list_triage_by_decision(runtime_dir: Path, decision: str) -> list[dict[str, Any]]:
    triage_dir = runtime_dir / "triage"
    if not triage_dir.exists():
        return []

    out: list[dict[str, Any]] = []
    for p in triage_dir.glob("*.json"):
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue

        if str(obj.get("decision", "")).lower() == decision.lower():
            out.append(obj)

    # newest first (if published_at exists)
    out.sort(key=lambda x: x.get("published_at", ""), reverse=True)
    return out


