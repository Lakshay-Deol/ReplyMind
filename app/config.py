import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=BASE_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    # Token endpoint for both code exchange & refresh flow
    GOOGLE_TOKEN_URL: str = "https://oauth2.googleapis.com/token"

    CLIENT_ID: Optional[str] = None
    CLIENT_SECRET: Optional[str] = None

    YOUTUBE_CHANNEL_ID: Optional[str] = None

    # Paths (may be derived from environment)
    REFRESH_TOKEN_PATH: Optional[Path] = None
    ACCESS_TOKEN_PATH: Optional[Path] = None

    # Check interval
    CHECK_INTERVAL_SECONDS: int = 30 * 60  # 30 minutes

    # Refresh early so you never hit expiry mid-request
    REFRESH_EARLY_SECONDS: int = 5 * 60   # refresh if <5 min remaining

    def __post_init__(self) -> None:
        # populate from environment if not provided
        client_id = os.getenv("YT_CLIENT_ID")
        client_secret = os.getenv("YT_CLIENT_SECRET")
        youtube_channel = os.getenv("YOUTUBE_CHANNEL_ID")
        refresh_path = os.getenv("REFRESH_TOKEN_PATH")
        access_path = os.getenv("ACCESS_TOKEN_PATH")

        if client_id:
            object.__setattr__(self, "CLIENT_ID", client_id)
        if client_secret:
            object.__setattr__(self, "CLIENT_SECRET", client_secret)
        if youtube_channel:
            object.__setattr__(self, "YOUTUBE_CHANNEL_ID", youtube_channel)
        if refresh_path:
            object.__setattr__(self, "REFRESH_TOKEN_PATH", BASE_DIR / refresh_path)
        if access_path:
            object.__setattr__(self, "ACCESS_TOKEN_PATH", BASE_DIR / access_path)

    def validate(self) -> List[str]:
        """Return a list of validation error messages (empty if valid).

        This method allows callers (and tests) to inspect configuration
        without forcing the process to exit or raise immediately.
        """
        errs: List[str] = []
        if not self.CLIENT_ID:
            errs.append("YT_CLIENT_ID is not set")
        if not self.CLIENT_SECRET:
            errs.append("YT_CLIENT_SECRET is not set")
        if not self.YOUTUBE_CHANNEL_ID:
            errs.append("YOUTUBE_CHANNEL_ID is not set")
        if not self.REFRESH_TOKEN_PATH:
            errs.append("REFRESH_TOKEN_PATH is not set")
        else:
            try:
                p = Path(self.REFRESH_TOKEN_PATH)
                if not p.exists():
                    errs.append(f"REFRESH_TOKEN_PATH not found: {p}")
            except Exception:
                errs.append("REFRESH_TOKEN_PATH is invalid")

        # access token path is optional; we just cache if present
        if self.ACCESS_TOKEN_PATH:
            try:
                p = Path(self.ACCESS_TOKEN_PATH)
                # file may not yet exist, that's fine; just ensure parent dir exists
                p.parent.mkdir(parents=True, exist_ok=True)
            except Exception:
                errs.append("ACCESS_TOKEN_PATH is invalid")

        return errs
