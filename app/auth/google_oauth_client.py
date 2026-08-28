from dataclasses import dataclass

import requests


@dataclass(frozen=True)
class OAuthResponse:
    access_token: str
    expires_in: int  # seconds

class GoogleOAuthClient:
    """
    Calls Google's token endpoint to refresh access token using refresh token.
    """
    def __init__(self, token_url: str, client_id: str, client_secret: str, timeout_seconds: int = 20):
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.timeout_seconds = timeout_seconds

    def refresh_access_token(self, refresh_token: str) -> OAuthResponse:
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }

        resp = requests.post(
            self.token_url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=self.timeout_seconds,
        )

        # Helpful error message
        if resp.status_code != 200:
            raise RuntimeError(f"Token refresh failed: {resp.status_code} {resp.text}")

        j = resp.json()
        access_token = j.get("access_token")
        expires_in = j.get("expires_in")

        if not access_token or not expires_in:
            raise RuntimeError(f"Unexpected token response: {j}")

        return OAuthResponse(access_token=access_token, expires_in=int(expires_in))
