"""Demo mode must run the whole product with no credentials at all.

The README documented a demo mode and a runtime/demo_comments.json that never
existed, and nothing branched on the mode -- a fresh clone hit
RefreshTokenMissing on the first click. These tests pin the promise.
"""

from unittest.mock import MagicMock

import pytest

from app.ai.batch_drafter import batch_draft_replies
from app.demo.seed import DEMO_COMMENTS, load_demo_comments


@pytest.fixture(autouse=True)
def isolated_runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("REPLYMIND_MODE", "demo")


def test_seed_covers_a_realistic_signal_spread():
    """A demo that only produces one signal type shows nothing about the product."""
    from app.ai.opportunity_detector import detect_opportunities
    from app.ai.triage import triage_comment

    kinds = {
        detect_opportunities(c.text, triage_comment(c)).signal_type
        for c in DEMO_COMMENTS
    }
    assert len(kinds) >= 8, f"demo seed only exercises {len(kinds)} signal types: {kinds}"


def test_demo_comments_load_without_a_file_present():
    assert len(load_demo_comments()) == len(DEMO_COMMENTS)


def test_drafting_works_with_no_openai_client():
    """No API key on a fresh clone must degrade, not abort the cycle."""
    drafts, failures = batch_draft_replies(list(DEMO_COMMENTS[:5]), openai_client=None)

    assert failures == []
    assert len(drafts) == 5
    # A template is a starting point, never an answer.
    assert all(d.needs_human for d in drafts)
    assert all(any("fallback" in r for r in d.reasons) for d in drafts)


def test_drafting_falls_back_when_the_api_fails():
    client = MagicMock()
    client.complete.side_effect = RuntimeError("insufficient_quota")

    drafts, failures = batch_draft_replies(list(DEMO_COMMENTS[:3]), client)

    assert failures == []
    assert len(drafts) == 3
    assert "insufficient_quota" in drafts[0].reasons[0]


def test_full_demo_cycle_needs_no_credentials(monkeypatch):
    for var in ("OPENAI_API_KEY", "YT_CLIENT_ID", "YT_CLIENT_SECRET", "YOUTUBE_CHANNEL_ID"):
        monkeypatch.delenv(var, raising=False)

    from main import run_once

    result = run_once()

    assert result["fetched"] == len(DEMO_COMMENTS)
    assert result["signals"] == len(DEMO_COMMENTS)
    assert result["drafts_saved"] > 0

    from app.agent import signal_store
    from app.agent.community_pulse import load_community_pulse

    assert signal_store.count() == len(DEMO_COMMENTS)
    pulse = load_community_pulse()
    assert pulse is not None and pulse.total_comments_analyzed == len(DEMO_COMMENTS)


def test_production_still_fails_loudly_without_an_openai_key(monkeypatch):
    """Silently shipping template replies to a real channel would be worse."""
    monkeypatch.setenv("REPLYMIND_MODE", "production")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY_PATH", raising=False)

    from main import _make_drafting_client

    with pytest.raises(RuntimeError, match="OpenAI API key"):
        _make_drafting_client()
