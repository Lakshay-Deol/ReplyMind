from datetime import datetime, timedelta, timezone

from app.errors import RefreshTokenMissing

from .google_oauth_client import GoogleOAuthClient
from .token_store import TokenInfo, TokenStore


class TokenManager:
    """
    Single responsibility:
    - ensure a valid access token exists
    - refresh if expired or near expiry
    """
    def __init__(self, store: TokenStore, oauth_client: GoogleOAuthClient, refresh_early_seconds: int = 300):
        self.store = store
        self.oauth_client = oauth_client
        self.refresh_early_seconds = refresh_early_seconds

    def get_valid_access_token(self) -> str:
        # token_info = self.store.load_access_token()

        try:
            token_info = self.store.load_access_token()
        
        except FileNotFoundError as e:
            raise RefreshTokenMissing(
                "Refresh token file is missing. Create secrets/refresh_token.txt and paste token."
            ) from e
        
        except ValueError as e:
            raise RefreshTokenMissing(
                "Refresh token file is empty. Paste refresh token inside."
            ) from e


        # If none cached, refresh immediately
        if token_info is None:
            return self._refresh_and_cache()

        # Refresh if expired or close to expiry
        if token_info.is_expired or token_info.seconds_remaining() <= self.refresh_early_seconds:
            return self._refresh_and_cache()

        return token_info.access_token

    def _refresh_and_cache(self) -> str:

        refresh_token = self.store.load_refresh_token()
        oauth = self.oauth_client.refresh_access_token(refresh_token)

        expires_at = datetime.now(timezone.utc) + timedelta(seconds=oauth.expires_in)
        token_info = TokenInfo(access_token=oauth.access_token, expires_at_utc=expires_at)

        self.store.save_access_token(token_info)
        return oauth.access_token
