from datetime import datetime, timezone

import pytest

import app.agent.memory as memory
import app.agent.memory_store as memory_store
from app.agent.models import AgentDecision, CreatorProfile, DecisionStatus


@pytest.fixture
def temp_memory_dir(tmp_path, monkeypatch):
    """Redirect the whole runtime root; paths resolve lazily from RUNTIME_DIR."""
    monkeypatch.setenv("RUNTIME_DIR", str(tmp_path))
    return tmp_path / "memory"

def test_safe_load_save_json(temp_memory_dir):
    # Test fallback
    data = memory_store.safe_load_json("test.json", {"default": True})
    assert data == {"default": True}
    
    # Test save
    memory_store.safe_save_json("test.json", {"saved": "data"})
    data2 = memory_store.safe_load_json("test.json", {})
    assert data2 == {"saved": "data"}

def test_load_memory_empty(temp_memory_dir):
    mem = memory.load_memory()
    assert mem.creator_profile.creator_name == "Unknown Creator"
    assert mem.approved_preferences == []
    assert mem.recurring_questions == {}

def test_update_creator_profile(temp_memory_dir):
    profile = CreatorProfile(
        creator_name="Alice",
        niche="Gaming",
        tone="Excited",
        preferred_reply_length="Short"
    )
    memory.update_creator_profile(profile)
    
    mem = memory.load_memory()
    assert mem.creator_profile.creator_name == "Alice"
    assert mem.creator_profile.niche == "Gaming"

def test_record_preference(temp_memory_dir):
    memory.record_preference("Use emojis", True)
    memory.record_preference("Use caps", False)
    
    mem = memory.load_memory()
    assert "Use emojis" in mem.approved_preferences
    assert "Use caps" in mem.rejected_preferences

def test_record_topic(temp_memory_dir):
    memory.record_topic("Settings", is_question=False)
    memory.record_topic("Settings", is_question=False)
    memory.record_topic("How to save?", is_question=True)
    
    mem = memory.load_memory()
    assert mem.recurring_topics["Settings"] == 2
    assert mem.recurring_questions["How to save?"] == 1

def test_record_important_commenter(temp_memory_dir):
    memory.record_important_commenter("user_123")
    memory.record_important_commenter("user_123")  # duplicate shouldn't duplicate in list
    
    mem = memory.load_memory()
    assert mem.important_commenters == ["user_123"]

def test_record_decisions(temp_memory_dir):
    decision1 = AgentDecision(
        recommendation_id="rec-1",
        decision=DecisionStatus.APPROVED,
        decided_at=datetime.now(timezone.utc),
        decided_by="admin"
    )
    decision2 = AgentDecision(
        recommendation_id="rec-2",
        decision=DecisionStatus.REJECTED,
        decided_at=datetime.now(timezone.utc),
        decided_by="admin"
    )
    
    memory.record_approval(decision1)
    memory.record_rejection(decision2)
    
    mem = memory.load_memory()
    assert len(mem.previous_decisions) == 2
    assert mem.previous_decisions[0].recommendation_id == "rec-1"
    assert mem.previous_decisions[1].recommendation_id == "rec-2"
