import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass
class TokenInfo:
    access_token: str
    expires_at_utc: datetime  # when access token expires (UTC)

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) >= self.expires_at_utc

    def seconds_remaining(self) -> int:
        delta = self.expires_at_utc - datetime.now(timezone.utc)
        return max(0, int(delta.total_seconds()))

class TokenStore:
    """
    Handles:
    - reading refresh token from a separate file (manual paste)
    - persisting access token + expiry to a configurable file (default runtime/access_token.json)
    """
    def __init__(self, refresh_token_path: Path, cache_path: Path):
        self.refresh_token_path = refresh_token_path
        self.cache_path = cache_path

    def load_refresh_token(self) -> str:
        if not self.refresh_token_path.exists():
            raise FileNotFoundError(
                f"Refresh token file not found: {self.refresh_token_path}. "
                f"Create it and paste refresh token inside."
            )
        else:
            token = self.refresh_token_path.read_text(encoding="utf-8").strip()
            
        if not token:
            raise ValueError(f"Refresh token file is empty: {self.refresh_token_path}")
        return token

    def save_access_token(self, token_info: TokenInfo) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "access_token": token_info.access_token,
            "expires_at_utc": token_info.expires_at_utc.isoformat()
        }
        self.cache_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")



    def load_access_token(self) -> Optional[TokenInfo]:
        if not self.cache_path.exists():
            return None

        text = self.cache_path.read_text(encoding="utf-8").strip()
        if not text:
            return None

        try:
            raw = json.loads(text)
        except json.JSONDecodeError:
            return None

        access_token = raw.get("access_token")
        expires_at_str = raw.get("expires_at_utc")

        if not access_token or not expires_at_str:
            return None

        expires_at = datetime.fromisoformat(expires_at_str)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        return TokenInfo(access_token=access_token, expires_at_utc=expires_at)

