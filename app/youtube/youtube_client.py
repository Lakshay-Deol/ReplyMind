from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests


@dataclass(frozen=True)
class YouTubeClientConfig:
    base_url: str = "https://www.googleapis.com/youtube/v3"
    timeout_seconds: int = 20


class YouTubeClient:
    """
    Minimal YouTube Data API client.

    Responsibilities:
    - Call YouTube endpoints (GET/POST)
    - Attach Authorization header using TokenManager
    - Retry ONCE on 401 (token expired/invalid)
    """

    def __init__(self, token_manager, config: YouTubeClientConfig | None = None):
        # token_manager must provide: get_valid_access_token() -> str
        self.token_manager = token_manager
        self.config = config or YouTubeClientConfig()

    # -------------------------
    # READ: comment threads
    # -------------------------



    def list_comment_threads_for_channel(self,channel_id: str,max_results: int = 50,page_token: Optional[str] = None,include_replies: bool = False,order: str = "time",  # newest first
    ) -> Dict[str, Any]:
        
        """
        commentThreads.list using allThreadsRelatedToChannelId (best for channel owner OAuth).
        Docs: https://developers.google.com/youtube/v3/docs/commentThreads/list
        """

        params: Dict[str, Any] = {
            "part": "snippet,replies" if include_replies else "snippet",
            "allThreadsRelatedToChannelId": channel_id,
            "maxResults": max_results,
            "order": order,
        }
        if page_token:
            params["pageToken"] = page_token

        return self._request_json("GET", "/commentThreads", params=params)

    # -------------------------
    # WRITE: reply to comment
    # -------------------------


    def reply_to_comment(self, parent_comment_id: str, text: str) -> Dict[str, Any]:
        """
        comments.insert to reply to a top-level comment.
        Requires OAuth scope: https://www.googleapis.com/auth/youtube.force-ssl
        Docs: https://developers.google.com/youtube/v3/docs/comments/insert
        """
        if not text or not text.strip():
            raise ValueError("Reply text cannot be empty.")

        params = {"part": "snippet"}
        body = {
            "snippet": {
                "parentId": parent_comment_id,
                "textOriginal": text.strip(),
            }
        }
        return self._request_json("POST", "/comments", params=params, json_body=body)

    # -------------------------
    # Internal HTTP
    # -------------------------

    
    def _request_json(self, method: str, path: str, params=None, json_body=None):
        url = f"{self.config.base_url}{path}"

        token = self.token_manager.get_valid_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

        try:
            if method.upper() == "GET":
                resp = requests.get(url, headers=headers, params=params, timeout=self.config.timeout_seconds)
            elif method.upper() == "POST":
                resp = requests.post(url, headers=headers, params=params, json=json_body, timeout=self.config.timeout_seconds)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
        except requests.Timeout as e:
            raise RuntimeError(f"YouTube API timed out calling {path}: {e}") from e
        except requests.RequestException as e:
            raise RuntimeError(f"YouTube API request failed calling {path}: {e}") from e

        # If token is invalid/expired, refresh and retry ONCE.
        # This block must stay nested under the 401 check: at module scope it
        # re-sent every request, doubling quota and duplicating comment writes.
        if resp.status_code == 401:
            token = self.token_manager.get_valid_access_token()
            headers["Authorization"] = f"Bearer {token}"

            try:
                if method.upper() == "GET":
                    resp = requests.get(url, headers=headers, params=params, timeout=self.config.timeout_seconds)
                else:
                    resp = requests.post(url, headers=headers, params=params, json=json_body, timeout=self.config.timeout_seconds)
            except requests.Timeout as e:
                raise RuntimeError(f"YouTube API timed out on retry calling {path}: {e}") from e
            except requests.RequestException as e:
                raise RuntimeError(f"YouTube API request failed on retry calling {path}: {e}") from e

        if resp.status_code not in (200, 201):
            raise RuntimeError(f"YouTube API error {resp.status_code} calling {path}: {resp.text}")

        try:
            return resp.json()
        except ValueError as e:
            raise RuntimeError(f"YouTube API returned non-JSON: {resp.text}") from e


    # def _force_token_refresh_best_effort(self) -> None:
    #     """
    #     Best-effort way to force refresh:
    #     - if TokenManager exposes store.cache_path, delete it
    #     - then call get_valid_access_token() again
    #     """
    #     store = getattr(self.token_manager, "store", None)
    #     cache_path = getattr(store, "cache_path", None)

    #     try:
    #         if cache_path and cache_path.exists():
    #             cache_path.unlink()
    #     except Exception:
    #         pass

    #     # Next call should refresh if cache was cleared
    #     try:
    #         _ = self.token_manager.get_valid_access_token()
    #     except Exception:
    #         # If refresh fails, the retry will surface the error anyway
    #         pass
