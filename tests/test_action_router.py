from datetime import datetime, timezone

import pytest

from app.agent.action_router import ActionState, ActionStateMachine, ActionType, AgentActionPlan


def create_action(state=ActionState.DETECTED):
    return AgentActionPlan(
        action_id="act-123",
        action_type=ActionType.DRAFT_REPLY,
        state=state,
        reason="Test reason",
        confidence=0.9,
        priority=50,
        source_comments=["comment-1"],
        proposed_action="Do something",
        requires_human_approval=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )

def test_successful_execution_path():
    action = create_action()
    machine = ActionStateMachine(action)
    
    assert action.state == ActionState.DETECTED
    
    machine.recommend()
    assert action.state == ActionState.RECOMMENDED
    
    machine.request_approval()
    assert action.state == ActionState.PENDING_APPROVAL
    
    machine.approve()
    assert action.state == ActionState.APPROVED
    
    machine.execute()
    assert action.state == ActionState.EXECUTED

def test_rejection_path():
    action = create_action()
    machine = ActionStateMachine(action)
    
    machine.recommend()
    machine.request_approval()
    
    machine.reject()
    assert action.state == ActionState.REJECTED
    
    with pytest.raises(ValueError, match="Cannot execute without approval"):
        machine.execute()

def test_invalid_transitions():
    action = create_action()
    machine = ActionStateMachine(action)
    
    # Cannot skip DETECTED to PENDING_APPROVAL
    with pytest.raises(ValueError, match="Cannot transition to PENDING_APPROVAL"):
        machine.request_approval()
        
    machine.recommend()
    
    # Cannot approve from RECOMMENDED (must go through PENDING_APPROVAL)
    with pytest.raises(ValueError, match="Cannot transition to APPROVED"):
        machine.approve()
        
    machine.request_approval()
    
    # Cannot execute from PENDING_APPROVAL (must be APPROVED)
    with pytest.raises(ValueError, match="Cannot execute without approval"):
        machine.execute()
