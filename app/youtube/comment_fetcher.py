from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from app.youtube.checkpoint_store import CheckpointStore
from app.youtube.model import Comment
from app.youtube.replied_store import RepliedState, RepliedStore


@dataclass(frozen=True)
class FetchConfig:
    page_size: int = 50
    max_pages: int = 5

@dataclass(frozen=True)
class FetchResult:
    new_comments: List[Comment]
    checkpoint_before: Optional[str]
    checkpoint_after: Optional[str]
    stopped_because_checkpoint_hit: bool


class CommentFetcher:
    """
    Fetches latest comments WITHOUT duplicates using:
    - checkpoint timestamp (stop scanning older comments)
    - rolling replied IDs (extra protection)

    This does NOT post replies. It only returns "new comments" to act on.
    """

    def __init__(
        self,
        youtube_client,  # expects: list_comment_threads_for_channel(...)
        checkpoint_store: CheckpointStore,
        replied_store: RepliedStore,
    ):
        self.youtube = youtube_client
        self.checkpoints = checkpoint_store
        self.replied_store = replied_store

    def fetch_latest_for_channel(self, channel_id: str, cfg: FetchConfig = FetchConfig()) -> FetchResult:
        checkpoint_dt = self.checkpoints.load()
        replied_state: RepliedState = self.replied_store.load()

        checkpoint_before_str = (
            checkpoint_dt.isoformat().replace("+00:00", "Z") if checkpoint_dt else None
        )

        collected: List[Comment] = []
        newest_seen_dt: Optional[datetime] = None
        stopped_on_checkpoint = False

        next_token: Optional[str] = None
        pages = 0

        while pages < cfg.max_pages:
            pages += 1

            data = self.youtube.list_comment_threads_for_channel(
                channel_id=channel_id,
                max_results=cfg.page_size,
                page_token=next_token,
                include_replies=False,
            )

            items = data.get("items", [])
            for item in items:
                snippet = (item.get("snippet") or {})
                top_obj = (snippet.get("topLevelComment") or {})
                top_snip = (top_obj.get("snippet") or {})

                comment_id = top_obj.get("id")
                if not comment_id:
                    continue

                published_at_str = top_snip.get("publishedAt", "")
                if not published_at_str:
                    continue

                published_at_dt = datetime.fromisoformat(published_at_str.replace("Z", "+00:00"))

                # STOP RULE: as soon as we reach already-processed history
                if checkpoint_dt and published_at_dt <= checkpoint_dt:
                    stopped_on_checkpoint = True
                    next_token = None
                    break

                # SAFETY RULE: skip if already replied
                if self.replied_store.has(replied_state, comment_id):
                    continue
#  below code is similar to java's  collected.add(obj); where collected is a list
                collected.append(
                    Comment(
                        comment_id=comment_id,
                        video_id=snippet.get("videoId"),
                        author=top_snip.get("authorDisplayName", ""),
                        text=top_snip.get("textDisplay", ""),
                        like_count=int(top_snip.get("likeCount", 0) or 0),
                        published_at=published_at_str,
                    )
                )

                if newest_seen_dt is None or published_at_dt > newest_seen_dt:
                    newest_seen_dt = published_at_dt

            next_token = data.get("nextPageToken")
            if not next_token:
                break

        # Update checkpoint AFTER successful fetch:
        # checkpoint becomes the newest comment timestamp we saw this run.
        checkpoint_after_str = checkpoint_before_str
        if newest_seen_dt:
            self.checkpoints.save(newest_seen_dt)
            checkpoint_after_str = newest_seen_dt.isoformat().replace("+00:00", "Z")

        return FetchResult(
            new_comments=collected,
            checkpoint_before=checkpoint_before_str,
            checkpoint_after=checkpoint_after_str,
            stopped_because_checkpoint_hit=stopped_on_checkpoint,
        )
