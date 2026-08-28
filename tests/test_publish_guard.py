"""Approving a draft publishes to a real channel, so it must be authenticated.

Before this guard every route was anonymous: anyone who could reach the deployed
URL could publish as the creator, and "nothing is published without human
approval" had no notion of which human.
"""

import pytest
from fastapi import HTTPException

from app.review import webapp


class FakeRequest:
    def __init__(self, cookies=None):
        self.cookies = cookies or {}


def test_demo_mode_stays_open_for_exploration(monkeypatch):
    monkeypatch.setenv("REPLYMIND_MODE", "demo")
    monkeypatch.delenv("REPLYMIND_CONSOLE_TOKEN", raising=False)

    # Demo publishes nothing, so judges can click through without a token.
    webapp.require_operator(FakeRequest())


def test_production_without_a_token_refuses_rather_than_opening(monkeypatch):
    monkeypatch.setenv("REPLYMIND_MODE", "production")
    monkeypatch.delenv("REPLYMIND_CONSOLE_TOKEN", raising=False)

    with pytest.raises(HTTPException) as exc:
        webapp.require_operator(FakeRequest())

    assert exc.value.status_code == 403
    assert "REPLYMIND_CONSOLE_TOKEN" in exc.value.detail


def test_configured_token_rejects_anonymous_callers(monkeypatch):
    monkeypatch.setenv("REPLYMIND_MODE", "production")
    monkeypatch.setenv("REPLYMIND_CONSOLE_TOKEN", "s3cret")

    with pytest.raises(HTTPException) as exc:
        webapp.require_operator(FakeRequest())

    assert exc.value.status_code == 401


def test_configured_token_rejects_a_wrong_cookie(monkeypatch):
    monkeypatch.setenv("REPLYMIND_MODE", "production")
    monkeypatch.setenv("REPLYMIND_CONSOLE_TOKEN", "s3cret")

    bad = FakeRequest({webapp.SESSION_COOKIE: "not-the-session-value"})
    with pytest.raises(HTTPException):
        webapp.require_operator(bad)


def test_valid_session_is_accepted(monkeypatch):
    monkeypatch.setenv("REPLYMIND_MODE", "production")
    monkeypatch.setenv("REPLYMIND_CONSOLE_TOKEN", "s3cret")

    good = FakeRequest({webapp.SESSION_COOKIE: webapp._session_value("s3cret")})
    webapp.require_operator(good)  # must not raise


def test_session_cookie_is_not_the_raw_token(monkeypatch):
    """The cookie must not hand the token back to anyone who reads it."""
    assert webapp._session_value("s3cret") != "s3cret"
    assert len(webapp._session_value("s3cret")) == 64


def test_demo_mode_never_publishes(monkeypatch, tmp_path):
    """Demo approval records the decision but must not construct a YouTube poster."""
    monkeypatch.setenv("REPLYMIND_MODE", "demo")

    def explode():
        raise AssertionError("demo mode must never build a YouTube poster")

    monkeypatch.setattr(webapp, "_build_poster", explode)
    monkeypatch.setattr(webapp.stores, "move_to_processed", lambda *a, **k: None)
    monkeypatch.setattr(webapp.metrics, "inc", lambda *a, **k: None)
    monkeypatch.setattr(webapp, "_record_decision", lambda *a, **k: None)

    class Draft:
        reply_text = "Thanks!"

        def model_copy(self, update=None):
            return self

    response = webapp._publish("c1", "Thanks!", Draft(), source="pending")
    assert response.status_code == 303
