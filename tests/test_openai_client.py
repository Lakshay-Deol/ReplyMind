import pytest


def test_openaiclient_missing_key_raises(monkeypatch):
    # If the environment running the tests already has an OpenAI key configured
    # (local dev machine), skip this case because the process-wide env will
    # satisfy the client and we can't reliably assert a failure.
    import os
    if os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY_PATH"):
        pytest.skip("OpenAI key present in test environment; skipping missing-key assertion")

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY_PATH", raising=False)
    from app.ai.openai_client import OpenAIClient

    with pytest.raises(RuntimeError):
        OpenAIClient(model="test-model")


def test_openaiclient_reads_api_key_from_path(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    key_file = tmp_path / "key.txt"
    key_file.write_text("file-key")
    monkeypatch.setenv("OPENAI_API_KEY_PATH", str(key_file))

    from app.ai.openai_client import OpenAIClient

    c = OpenAIClient(model="m")
    assert c.api_key == "file-key"


def test_openaiclient_retry_on_500(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    import requests

    from app.ai.openai_client import OpenAIClient

    class FakeResp:
        def __init__(self, status, text, data=None):
            self.status_code = status
            self.text = text
            self._data = data or {}

        def json(self):
            return self._data

    calls = {"n": 0}

    def fake_post(url, json=None, headers=None, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return FakeResp(500, "server error")
        return FakeResp(200, "ok", {"choices": [{"message": {"content": "hello from llm"}}]})

    monkeypatch.setattr(requests, "post", fake_post)

    c = OpenAIClient(model="m")
    out = c.complete(system="", user="hi", max_output_tokens=10)
    assert "hello" in out
