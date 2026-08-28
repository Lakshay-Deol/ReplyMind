from dataclasses import dataclass


@dataclass(frozen=True)
class Comment:
    comment_id: str
    video_id: str | None
    author: str
    text: str
    like_count: int
    published_at: str  # ISO string like "2026-01-12T17:42:18Z"
