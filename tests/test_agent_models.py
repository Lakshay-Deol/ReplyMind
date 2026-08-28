from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.agent.config import AgentConfig
from app.agent.models import (
    AgentDecision,
    AgentMemory,
    AgentRecommendation,
    AudienceSignal,
    CreatorProfile,
    DecisionStatus,
    RecommendationStatus,
    RecommendationType,
    SignalType,
)


def test_creator_profile_valid():
    profile = CreatorProfile(
        creator_name="Test Creator",
        niche="Tech",
        tone="Professional",
        goals=["Grow audience"],
        preferred_reply_length="Short",
    )
    assert profile.creator_name == "Test Creator"
    assert profile.goals == ["Grow audience"]
    assert profile.topics_to_avoid == []


def test_creator_profile_missing_required():
    with pytest.raises(ValidationError):
        CreatorProfile(
            creator_name="Test Creator",
            niche="Tech",
            # tone and preferred_reply_length missing
        )


def test_audience_signal_valid():
    signal = AudienceSignal(
        signal_id="sig-123",
        comment_id="comment-123",
        signal_type=SignalType.PRAISE,
        confidence=0.8,
        explanation="Positive sentiment",
        detected_at=datetime.now(timezone.utc),
    )
    assert signal.signal_type == "praise"
    assert signal.confidence == 0.8


def test_audience_signal_invalid_confidence():
    with pytest.raises(ValidationError):
        AudienceSignal(
            signal_id="sig-123",
            comment_id="comment-123",
            signal_type=SignalType.PRAISE,
            confidence=1.5,  # Out of bounds
            explanation="Positive sentiment",
            detected_at=datetime.now(timezone.utc),
        )


def test_agent_recommendation_valid():
    rec = AgentRecommendation(
        recommendation_id="rec-1",
        recommendation_type=RecommendationType.REPLY_DRAFT,
        title="Draft Reply",
        description="A draft reply to the comment",
        confidence=0.9,
        proposed_action="Send draft",
        created_at=datetime.now(timezone.utc),
    )
    assert rec.status == RecommendationStatus.PENDING


def test_agent_decision_valid():
    decision = AgentDecision(
        recommendation_id="rec-1",
        decision=DecisionStatus.APPROVED,
        decided_at=datetime.now(timezone.utc),
        decided_by="human",
    )
    assert decision.decision == "approved"
    assert decision.edited_content is None


def test_agent_memory_valid():
    profile = CreatorProfile(
        creator_name="Test Creator",
        niche="Tech",
        tone="Professional",
        preferred_reply_length="Short",
    )
    memory = AgentMemory(
        creator_profile=profile,
        approved_preferences=["Keep it short"],
        recurring_questions={"When is the next video?": 5},
    )
    assert memory.creator_profile.creator_name == "Test Creator"
    assert memory.recurring_questions["When is the next video?"] == 5
    assert len(memory.previous_decisions) == 0


def test_agent_config():
    config = AgentConfig()
    assert config.AGENT_MAX_HISTORY == 10
    assert config.AGENT_CONFIDENCE_THRESHOLD == 0.75
