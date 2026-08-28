"""Regressions for bugs that were silently corrupting real output."""

from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.ai.batch_drafter import batch_draft_replies
from app.ai.triage_engine import CommentTriageEngine, TriageConfig
from app.ai.types import CommentCategory, DraftReply

CFG_PATH = Path(__file__).resolve().parents[1] / "app" / "config" / "triage_rules.json"


@pytest.fixture(scope="module")
def engine() -> CommentTriageEngine:
    return CommentTriageEngine(TriageConfig.load(CFG_PATH))


# ---------------------------------------------------------------------------
# Triage: substring matching produced false positives on ordinary English
# ---------------------------------------------------------------------------


def test_help_inside_helped_is_not_a_complaint(engine):
    result = engine.triage_text("This helped me ship my first agent. Thank you.")
    assert result.category is CommentCategory.PRAISE


def test_subscribe_inside_subscriber_does_not_score_as_spam(engine):
    loyal = "I have been watching since the 300 subscriber days. Huge fan!"
    promo = "subscribe to my channel for a giveaway, check my channel"
    assert engine.triage_text(loyal).spam_score < engine.triage_text(promo).spam_score


def test_genuine_complaint_words_still_match(engine):
    assert engine.triage_text("Help please, my account is broken").category is (
        CommentCategory.COMPLAINT
    )


# ---------------------------------------------------------------------------
# Drafting: guardrails mutated a frozen dataclass and destroyed the draft
# ---------------------------------------------------------------------------


def test_draft_reply_is_still_immutable():
    """The guardrail fix relies on DraftReply being frozen; pin that."""
    draft = DraftReply(
        comment_id="c1",
        reply_text="hi",
        category=CommentCategory.OTHER,
        confidence=0.4,
        needs_human=False,
        reasons=[],
    )
    with pytest.raises(FrozenInstanceError):
        draft.needs_human = True  # type: ignore[misc]


def _comment(cid="c1", text="How does this work?", author="viewer"):
    return MagicMock(comment_id=cid, text=text, author=author)


def test_low_confidence_draft_is_flagged_not_discarded():
    """Regression: FrozenInstanceError was swallowed, dropping the draft entirely."""
    client = MagicMock()
    client.complete.return_value = (
        '[{"comment_id": "c1", "reply_text": "Sure thing!", "category": "question",'
        ' "confidence": 0.2, "needs_human": false, "reasons": []}]'
    )

    drafts, failures = batch_draft_replies([_comment()], client)

    assert failures == []
    assert len(drafts) == 1
    assert drafts[0].needs_human is True
    assert "low_confidence" in drafts[0].reasons


def test_empty_reply_is_backfilled_and_flagged():
    client = MagicMock()
    client.complete.return_value = (
        '[{"comment_id": "c1", "reply_text": "", "category": "other",'
        ' "confidence": 0.9, "needs_human": false, "reasons": []}]'
    )

    drafts, failures = batch_draft_replies([_comment()], client)

    assert failures == []
    assert drafts[0].reply_text
    assert drafts[0].needs_human is True
    assert "empty_reply_text" in drafts[0].reasons


def test_output_budget_scales_with_batch_size():
    """200 tokens truncated the JSON array for any batch >1, losing every draft."""
    client = MagicMock()
    client.complete.return_value = "[]"
    comments = [_comment(cid=f"c{i}") for i in range(12)]

    batch_draft_replies(comments, client)

    budget = client.complete.call_args.kwargs["max_output_tokens"]
    assert budget >= 160 * len(comments)
