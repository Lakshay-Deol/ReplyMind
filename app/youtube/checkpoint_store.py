import json
from datetime import datetime
from pathlib import Path
from typing import Optional


class CheckpointStore:
    """
    Stores ONE checkpoint:
      last_processed_published_at (UTC)
    in runtime/checkpoint.json
    """
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> Optional[datetime]:
        if not self.path.exists():
            return None
        data = json.loads(self.path.read_text(encoding="utf-8"))
        ts = data.get("last_processed_published_at")
        if not ts:
            return None
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))

    def save(self, dt_utc: datetime) -> None:
        payload = {
            "last_processed_published_at": dt_utc.isoformat().replace("+00:00", "Z")
        }
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self.path)
