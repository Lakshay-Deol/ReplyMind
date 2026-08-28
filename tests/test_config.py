from app.config import Settings


def test_settings_validate_missing_env(monkeypatch):
    # Clear relevant env vars
    monkeypatch.delenv("YT_CLIENT_ID", raising=False)
    monkeypatch.delenv("YT_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("YOUTUBE_CHANNEL_ID", raising=False)
    monkeypatch.delenv("REFRESH_TOKEN_PATH", raising=False)
    monkeypatch.delenv("ACCESS_TOKEN_PATH", raising=False)

    s = Settings()
    errs = s.validate()
    assert isinstance(errs, list)
    # expect at least one error when all are missing
    assert len(errs) >= 1


def test_settings_with_refresh_path(tmp_path, monkeypatch):
    # Provide a fake refresh token file path and some envs
    token_file = tmp_path / "refresh.txt"
    token_file.write_text("dummy")
    monkeypatch.setenv("REFRESH_TOKEN_PATH", str(token_file.relative_to(token_file.parents[1]) ) if False else str(token_file))
    monkeypatch.setenv("ACCESS_TOKEN_PATH", str(token_file.parent / "access.json"))
    monkeypatch.setenv("YT_CLIENT_ID", "abc")
    monkeypatch.setenv("YT_CLIENT_SECRET", "secret")
    monkeypatch.setenv("YOUTUBE_CHANNEL_ID", "chan123")

    s = Settings()
    errs = s.validate()
    # All required set and file exists => no errors
    assert errs == []
    # access token path should be converted to Path and prefixed with base dir
    assert s.ACCESS_TOKEN_PATH is not None
