import pytest

from app.agent.community_pulse import (
    CommunityPulse,
    generate_community_pulse,
    load_community_pulse,
    save_community_pulse,
)
from app.ai.opportunity_models import OpportunityResult, OpportunitySignalType


@pytest.fixture
def temp_opportunities_dir(tmp_path, monkeypatch):
    """Redirect the whole runtime root; paths resolve lazily from RUNTIME_DIR."""
    monkeypatch.setenv("RUNTIME_DIR", str(tmp_path))
    return tmp_path / "opportunities"

def test_generate_community_pulse():
    signals = [
        OpportunityResult(
            signal_type=OpportunitySignalType.QUESTION,
            confidence=0.9,
            priority=80,
            explanation="Good question",
            recommended_action="Draft reply"
        ),
        OpportunityResult(
            signal_type=OpportunitySignalType.SPAM,
            confidence=0.99,
            priority=20,
            explanation="Spam comment",
            recommended_action="Ignore"
        ),
        OpportunityResult(
            signal_type=OpportunitySignalType.CONTENT_REQUEST,
            confidence=0.85,
            priority=95,
            explanation="Wants a tutorial on backend",
            recommended_action="Create backend tutorial video"
        )
    ]
    
    pulse = generate_community_pulse(signals)
    
    assert pulse.total_comments_analyzed == 3
    assert pulse.high_priority_comments == 2  # 80 and 95
    assert pulse.questions == 1
    assert pulse.spam == 1
    assert pulse.content_requests == 1
    
    # Top recommendation should be from the content request (priority 95)
    assert pulse.explanation_for_recommendation == "Wants a tutorial on backend"
    assert pulse.top_recommendation == "Create backend tutorial video"
    
    formatted = pulse.format_text()
    assert "3 comments analyzed" in formatted
    assert "2 high-priority conversations" in formatted
    assert "Create backend tutorial video" in formatted

def test_load_save_pulse(temp_opportunities_dir):
    # Test load when empty
    assert load_community_pulse() is None
    
    pulse = CommunityPulse(
        total_comments_analyzed=10,
        high_priority_comments=2,
        questions=1,
        recurring_questions=0,
        content_requests=0,
        complaints=0,
        spam=5,
        potential_superfans=0,
        collaboration_opportunities=0,
        top_audience_topics=[],
        top_recommendation="Top Rec",
        explanation_for_recommendation="Top Exp"
    )
    
    save_community_pulse(pulse)
    
    loaded = load_community_pulse()
    assert loaded is not None
    assert loaded.total_comments_analyzed == 10
    assert loaded.spam == 5
    assert loaded.top_recommendation == "Top Rec"
