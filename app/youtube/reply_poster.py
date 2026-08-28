from __future__ import annotations

import time
from typing import Any, Dict

import requests

YOUTUBE_COMMENTS_INSERT_URL = "https://www.googleapis.com/youtube/v3/comments"
# docs: comments.insert (reply) uses part=snippet and body.snippet.parentId + body.snippet.textOriginal :contentReference[oaicite:2]{index=2}


class YouTubeReplyPoster:
    def __init__(self, token_manager):
        self.token_manager = token_manager

    def reply_with_retry(
        self,
        *,
        parent_comment_id: str,
        reply_text: str,
        max_attempts: int = 4,
        base_sleep: float = 0.8,
    ) -> Dict[str, Any]:
        """
        Retries on rate-limit / transient errors.
        """
        last_err = None
        for attempt in range(1, max_attempts + 1):
            try:
                return self.reply(parent_comment_id=parent_comment_id, reply_text=reply_text)
            except requests.HTTPError as e:
                last_err = e
                status = e.response.status_code if e.response is not None else None
                # Retry on common transient codes
                if status in (429, 500, 502, 503, 504):
                    sleep_s = base_sleep * (2 ** (attempt - 1))
                    time.sleep(sleep_s)
                    continue
                raise
            except Exception as e:
                last_err = e
                time.sleep(base_sleep * (2 ** (attempt - 1)))
        raise RuntimeError(f"reply_failed_after_retries: {last_err}")

    def reply(self, *, parent_comment_id: str, reply_text: str) -> Dict[str, Any]:
        access_token = self.token_manager.get_valid_access_token()

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        params = {"part": "snippet"}
        body = {
            "snippet": {
                "parentId": parent_comment_id,
                "textOriginal": reply_text,
            }
        }

        r = requests.post(YOUTUBE_COMMENTS_INSERT_URL, headers=headers, params=params, json=body, timeout=20)
        if r.status_code >= 400:
            # include body for debug
            raise requests.HTTPError(f"youtube_reply_failed {r.status_code}: {r.text}", response=r)
        return r.json()
