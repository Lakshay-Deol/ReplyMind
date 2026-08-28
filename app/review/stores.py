from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from app.paths import runtime_dir
from app.review.models import DraftRecord


class DraftStores:
    def __init__(self, base_dir: Path | None = None):
        base = base_dir if base_dir is not None else runtime_dir()
        self.pending = base / "drafts"
        self.processed = base / "processed"
        self.rejected = base / "rejected"
        self.errors = base / "errors"
        for d in (self.pending, self.processed, self.rejected, self.errors):
            d.mkdir(parents=True, exist_ok=True)

    def _path(self, folder: Path, comment_id: str) -> Path:
        return folder / f"{comment_id}.json"

    def list_pending(self) -> List[DraftRecord]:
        files = sorted(self.pending.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        out: List[DraftRecord] = []
        for p in files:
            try:
                out.append(DraftRecord.model_validate_json(p.read_text(encoding="utf-8")))
            except Exception:
                continue
        return out

    def get_pending(self, comment_id: str) -> Optional[DraftRecord]:
        p = self._path(self.pending, comment_id)
        if not p.exists():
            return None
        return DraftRecord.model_validate_json(p.read_text(encoding="utf-8"))

    def save_pending(self, draft: DraftRecord) -> None:
        if not draft.created_at:
            draft = draft.model_copy(update={"created_at": datetime.now(timezone.utc).isoformat()})
        self._path(self.pending, draft.comment_id).write_text(
            draft.model_dump_json(indent=2),
            encoding="utf-8",
        )

    # -------------------------
    # Processed / Rejected
    # -------------------------
    def move_to_processed(self, draft: DraftRecord, extra: dict) -> None:
        p = self._path(self.processed, draft.comment_id)
        payload = draft.model_dump()
        payload.update(extra)
        p.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        self._safe_delete(self._path(self.pending, draft.comment_id))

    def move_to_rejected(self, draft: DraftRecord, reason: str | None) -> None:
        p = self._path(self.rejected, draft.comment_id)
        payload = draft.model_dump()
        payload["rejected_reason"] = reason
        payload["rejected_at"] = datetime.now(timezone.utc).isoformat()
        p.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        self._safe_delete(self._path(self.pending, draft.comment_id))
        self._safe_delete(self._path(self.errors, draft.comment_id))

    # -------------------------
    # Errors (failed posts)
    # -------------------------
    def list_errors(self) -> List[DraftRecord]:
        files = sorted(self.errors.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        out: List[DraftRecord] = []
        for p in files:
            try:
                out.append(DraftRecord.model_validate_json(p.read_text(encoding="utf-8")))
            except Exception:
                continue
        return out

    def get_error(self, comment_id: str) -> Optional[DraftRecord]:
        p = self._path(self.errors, comment_id)
        if not p.exists():
            return None
        return DraftRecord.model_validate_json(p.read_text(encoding="utf-8"))

    def move_to_errors(self, draft: DraftRecord, error: str) -> None:
        p = self._path(self.errors, draft.comment_id)
        payload = draft.model_dump()
        payload["error"] = error
        payload["failed_at"] = datetime.now(timezone.utc).isoformat()
        p.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

        # ✅ remove from pending so it disappears from main window
        self._safe_delete(self._path(self.pending, draft.comment_id))

    def update_error(self, comment_id: str, error: str) -> None:
        p = self._path(self.errors, comment_id)
        if not p.exists():
            return
        try:
            payload = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        payload["error"] = error
        payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        p.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    def move_error_to_processed(self, draft: DraftRecord, extra: dict) -> None:
        p = self._path(self.processed, draft.comment_id)
        payload = draft.model_dump()
        payload.update(extra)
        p.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

        # remove from everywhere once posted successfully
        self._safe_delete(self._path(self.errors, draft.comment_id))
        self._safe_delete(self._path(self.pending, draft.comment_id))

    def _safe_delete(self, path: Path) -> None:
        try:
            if path.exists():
                path.unlink()
        except Exception:
            pass
