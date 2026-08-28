"""The Mind must be reached for real, and must never be faked when it is not."""

from unittest.mock import MagicMock

import pytest

from app.agent import agent_service
from app.agent.minds_client import MindsUnavailable
from app.ai.types import CommentCategory, TriageDecision, TriageResult


@pytest.fixture
def mind():
    client = MagicMock()
    client.send_message.return_value = "Publish the backend walkthrough next."
    client.check_status.return_value = {"status": "ok", "mindId": "mind_1"}
    return client


@pytest.fixture
def offline_mind():
    client = MagicMock()
    client.send_message.side_effect = MindsUnavailable("connection refused")
    client.check_status.side_effect = MindsUnavailable("connection refused")
    return client


def test_ask_reaches_the_mind(mind):
    answer = agent_service.ask("What should I create next?", client=mind)

    assert answer.source == "minds"
    assert answer.answer == "Publish the backend walkthrough next."
    mind.send_message.assert_called_once()


def test_ask_uses_one_stable_alias_for_continuity(mind):
    agent_service.ask("First question", client=mind)
    agent_service.ask("Second question", client=mind)

    aliases = {c.kwargs["alias"] for c in mind.send_message.call_args_list}
    assert aliases == {agent_service.CONSOLE_ALIAS}


def test_context_carries_real_creator_state(mind):
    agent_service.ask("Who are my supporters?", client=mind)
    message = mind.send_message.call_args.kwargs["message"]

    assert "CREATOR:" in message
    assert "CREATOR QUESTION" in message
    assert "Who are my supporters?" in message


def test_offline_mind_is_reported_not_invented(offline_mind):
    answer = agent_service.ask("What should I create next?", client=offline_mind)

    assert answer.source == "unavailable"
    assert not answer.ok
    # It must say it failed rather than produce a plausible-looking answer.
    assert "not reachable" in answer.answer
    assert "connection refused" in answer.answer


def test_empty_question_is_rejected(mind):
    answer = agent_service.ask("   ", client=mind)

    assert answer.source == "unavailable"
    mind.send_message.assert_not_called()


def test_health_reports_connection_state(mind, offline_mind):
    assert agent_service.health(client=mind)["connected"] is True

    offline = agent_service.health(client=offline_mind)
    assert offline["connected"] is False
    assert "connection refused" in offline["error"]


def test_analyze_comment_persists_a_signal(mind, monkeypatch):
    monkeypatch.setenv("REPLYMIND_MODE", "demo")
    triage = TriageResult(
        decision=TriageDecision.DRAFT_REPLY,
        category=CommentCategory.QUESTION,
        reasons=[],
        spam_score=0.0,
        relevance_score=0.8,
    )

    stored = agent_service.analyze_comment(
        comment_id="c-42", comment_text="Can you make a video on this?", triage_result=triage, author="mira"
    )

    assert stored.comment_id == "c-42"
    assert stored.author == "mira"
    assert 0 <= stored.priority <= 100
    # Demo mode does not spend Mind cognition on every comment.
    mind.send_message.assert_not_called()


# ---------------------------------------------------------------------------
# cognition budget: a Mind call costs credits, so it must be spent selectively
# ---------------------------------------------------------------------------


def _triage():
    return TriageResult(
        decision=TriageDecision.DRAFT_REPLY,
        category=CommentCategory.OTHER,
        reasons=[],
        spam_score=0.0,
        relevance_score=0.1,
    )


def test_low_priority_comment_does_not_spend_a_mind_call(mind, monkeypatch):
    monkeypatch.setenv("REPLYMIND_MODE", "production")
    monkeypatch.setenv("REPLYMIND_MIND_REVIEW_THRESHOLD", "70")

    agent_service.analyze_comment(
        comment_id="low-1", comment_text="nice", triage_result=_triage(), author="a", client=mind
    )

    mind.send_message.assert_not_called()


def test_high_priority_comment_is_escalated_to_the_mind(mind, monkeypatch):
    monkeypatch.setenv("REPLYMIND_MODE", "production")
    monkeypatch.setenv("REPLYMIND_MIND_REVIEW_THRESHOLD", "0")  # escalate everything

    agent_service.analyze_comment(
        comment_id="high-1",
        comment_text="Urgent - this is completely broken in production",
        triage_result=_triage(),
        author="b",
        client=mind,
    )

    mind.send_message.assert_called_once()


def test_threshold_is_configurable_and_falls_back_on_junk(monkeypatch):
    monkeypatch.setenv("REPLYMIND_MIND_REVIEW_THRESHOLD", "42")
    assert agent_service.mind_review_threshold() == 42

    monkeypatch.setenv("REPLYMIND_MIND_REVIEW_THRESHOLD", "not-a-number")
    assert agent_service.mind_review_threshold() == agent_service.DEFAULT_MIND_REVIEW_THRESHOLD
