"""HTTP client for the local Minds integration service.

The service (minds-service/) wraps the official @animocabrands/minds-client-lib
and holds the Builder API key, so the key never reaches this process or a browser.

Every failure here raises MindsUnavailable. This module deliberately returns no
placeholder wallet address and no placeholder cognition balance: presenting
invented on-chain values as real readings is worse than showing nothing.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

import requests

logger = logging.getLogger(__name__)

def _default_base_url() -> str:
    """Resolve the integration service URL.

    A bare host is accepted so a PaaS blueprint can inject one directly
    (Render's `fromService` yields a hostname, not a URL).
    """
    configured = (os.getenv("MINDS_SERVICE_URL") or "").strip()
    if configured:
        if not configured.startswith(("http://", "https://")):
            configured = "https://" + configured
        return configured
    return f"http://localhost:{os.getenv('MINDS_SERVICE_PORT', '3001')}"


class MindsUnavailable(RuntimeError):
    """The Minds integration service could not be reached or returned an error."""


class MindsClient:
    def __init__(self, base_url: str | None = None, timeout: int = 60):
        self.base_url = (base_url or _default_base_url()).rstrip("/")
        self.timeout = timeout
        self.token = (os.getenv("MINDS_SERVICE_TOKEN") or "").strip()

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        headers = dict(kwargs.pop("headers", {}) or {})
        if self.token:
            headers["x-replymind-token"] = self.token
        try:
            resp = requests.request(
                method, url, timeout=kwargs.pop("timeout", 10), headers=headers, **kwargs
            )
        except requests.RequestException as exc:
            raise MindsUnavailable(
                f"cannot reach the Minds service at {self.base_url} "
                f"(start it with: cd minds-service && npm start)"
            ) from exc

        if resp.status_code >= 400:
            detail = resp.text[:300]
            raise MindsUnavailable(f"Minds service returned {resp.status_code}: {detail}")

        try:
            return resp.json()
        except ValueError as exc:
            raise MindsUnavailable("Minds service returned a non-JSON response") from exc

    # ------------------------------------------------------------------
    # api
    # ------------------------------------------------------------------
    def check_status(self) -> Dict[str, Any]:
        # The upstream Minds API takes 6-15s to answer this, so it gets the full
        # client timeout. Callers keep it off the request path rather than
        # capping it here -- a short cap reported a reachable Mind as offline.
        return self._request("GET", "/agent/status", timeout=self.timeout)

    def send_message(self, alias: str, message: str) -> str:
        data = self._request(
            "POST",
            "/agent/message",
            json={"alias": alias, "message": message},
            timeout=self.timeout,
        )
        reply = (data.get("reply") or "").strip()
        if not reply:
            raise MindsUnavailable("the Mind returned an empty reply")
        return reply

    def get_history(self, alias: str) -> List[Dict[str, Any]]:
        data = self._request("GET", "/agent/history", params={"alias": alias})
        return data.get("history", [])

    def get_wallet(self) -> Dict[str, Any]:
        """Live wallet/cognition reading. Raises MindsUnavailable rather than guessing."""
        return self._request("GET", "/agent/wallet")
