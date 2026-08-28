class TokenManagerError(RuntimeError):
    """Base class for all token manager related errors."""

class TokenCacheError(TokenManagerError):
    """Raised when the token cache file is unreadable/corrupted."""

class RefreshTokenMissing(TokenManagerError):
    """Raised when refresh token file is missing or empty."""

class OAuthRefreshError(TokenManagerError):
    """Raised when Google OAuth refresh fails (401/400/network issues)."""

class TokenStoreError(RuntimeError): 
    """Base class for all token store related errors."""
    
class TokenCacheCorrupted(TokenStoreError):
    """Raised when the token cache file is unreadable/corrupted.""" 
