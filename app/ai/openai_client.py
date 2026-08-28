from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import requests
from dotenv import load_dotenv

from app.logging import get_logger

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(dotenv_path=BASE_DIR / ".env")


def _read_api_key_from_path(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8").strip()


def _extract_output_text(resp: Dict[str, Any]) -> str:
    # Standard OpenAI Chat Completions format
    choices = resp.get("choices", [])
    if choices:
        message = choices[0].get("message", {})
        content = message.get("content")
        if content:
            return content.strip()
    return ""


@dataclass
class OpenAIClient:
    model: str
    base_url: str | None = None
    api_key: str | None = None
    timeout_seconds: int = 60

    def __post_init__(self) -> None:
        if not self.base_url:
            self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")

        if not self.api_key:
            self.api_key = os.getenv("OPENAI_API_KEY")

        if not self.api_key:
            key_path = os.getenv("OPENAI_API_KEY_PATH")
            if key_path:
                self.api_key = _read_api_key_from_path(BASE_DIR / key_path)

        if not self.api_key:
            raise RuntimeError(
                "Missing OpenAI API key. Set OPENAI_API_KEY or OPENAI_API_KEY_PATH in .env."
            )
            
        self._logger = get_logger("openai_client")

    def _post_with_retry(self, url: str, json: Dict[str, Any], headers: Dict[str, str], timeout: int, max_retries: int = 3) -> requests.Response:
        delay = 1.0
        for attempt in range(1, max_retries + 1):
            try:
                resp = requests.post(url, json=json, headers=headers, timeout=timeout)
                if resp.status_code == 429 or 500 <= resp.status_code < 600:
                    # transient, retry
                    self._logger.warning(f"OpenAI transient status {resp.status_code}, attempt {attempt}")
                    if attempt == max_retries:
                        return resp
                    time.sleep(delay)
                    delay *= 2
                    continue
                return resp
            except requests.RequestException as exc:
                self._logger.warning(f"OpenAI request exception on attempt {attempt}: {exc}")
                if attempt == max_retries:
                    raise
                time.sleep(delay)
                delay *= 2


    def complete(self, system: str, user: str, max_output_tokens: int = 800) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})
        
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": int(max_output_tokens),
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        resp = self._post_with_retry(
            f"{self.base_url}/chat/completions",
            json=payload,
            headers=headers,
            timeout=self.timeout_seconds,
            max_retries=3,
        )

        if resp.status_code >= 400:
            # include body up to a limit
            txt = resp.text[:2000]
            raise RuntimeError(f"OpenAI API error {resp.status_code}: {txt}")

        data = resp.json()
        text = _extract_output_text(data)
        if not text:
            raise RuntimeError("OpenAI API returned no text output.")
        return text
