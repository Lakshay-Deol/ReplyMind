import json
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Deque, Set


@dataclass
class RepliedState:
    # rolling list (keeps last N)
    recent: Deque[str] = field(default_factory=lambda: deque(maxlen=5000))
    # fast lookup
    recent_set: Set[str] = field(default_factory=set)

class RepliedStore:
    """
    Keeps last N replied commentIds to prevent double replies.
    Stored in runtime/replied_ids.json
    """
    def __init__(self, path: Path, maxlen: int = 5000):
        self.path = path
        self.maxlen = maxlen
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> RepliedState:
        st = RepliedState()
        st.recent = deque(maxlen=self.maxlen)

        if not self.path.exists():
            return st

        data = json.loads(self.path.read_text(encoding="utf-8"))
        ids = data.get("replied_recent", [])
        st.recent = deque(ids, maxlen=self.maxlen)
        st.recent_set = set(st.recent)
        return st

    def save(self, st: RepliedState) -> None:
        payload = {"replied_recent": list(st.recent)}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def has(self, st: RepliedState, comment_id: str) -> bool:
        return comment_id in st.recent_set

    def add(self, st: RepliedState, comment_id: str) -> None:
        if comment_id in st.recent_set:
            return

        if len(st.recent) == st.recent.maxlen:
            oldest = st.recent[0]
            st.recent_set.discard(oldest)

        st.recent.append(comment_id)
        st.recent_set.add(comment_id)
