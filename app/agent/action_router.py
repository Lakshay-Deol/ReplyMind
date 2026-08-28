from datetime import datetime, timezone
from enum import Enum
from typing import List

from pydantic import BaseModel, Field


class ActionType(str, Enum):
    DRAFT_REPLY = "DRAFT_REPLY"
    CREATE_CONTENT_IDEA = "CREATE_CONTENT_IDEA"
    FLAG_FOR_REVIEW = "FLAG_FOR_REVIEW"
    ESCALATE_COMPLAINT = "ESCALATE_COMPLAINT"
    RECOGNIZE_SUPERFAN = "RECOGNIZE_SUPERFAN"
    DRAFT_COLLABORATION = "DRAFT_COLLABORATION"
    IGNORE = "IGNORE"
    MARK_SPAM = "MARK_SPAM"

class ActionState(str, Enum):
    DETECTED = "DETECTED"
    RECOMMENDED = "RECOMMENDED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTED = "EXECUTED"

class AgentActionPlan(BaseModel):
    action_id: str
    action_type: ActionType
    state: ActionState = ActionState.DETECTED
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)
    priority: int
    source_comments: List[str]
    proposed_action: str
    requires_human_approval: bool = True
    created_at: datetime
    updated_at: datetime

class ActionStateMachine:
    def __init__(self, action: AgentActionPlan):
        self.action = action

    def recommend(self):
        if self.action.state != ActionState.DETECTED:
            raise ValueError(f"Cannot transition to RECOMMENDED from {self.action.state}")
        self.action.state = ActionState.RECOMMENDED
        self.action.updated_at = datetime.now(timezone.utc)

    def request_approval(self):
        if self.action.state != ActionState.RECOMMENDED:
            raise ValueError(f"Cannot transition to PENDING_APPROVAL from {self.action.state}")
        # Always require PENDING_APPROVAL for external actions
        self.action.state = ActionState.PENDING_APPROVAL
        self.action.updated_at = datetime.now(timezone.utc)

    def approve(self):
        if self.action.state != ActionState.PENDING_APPROVAL:
            raise ValueError(f"Cannot transition to APPROVED from {self.action.state}")
        self.action.state = ActionState.APPROVED
        self.action.updated_at = datetime.now(timezone.utc)

    def reject(self):
        if self.action.state != ActionState.PENDING_APPROVAL:
            raise ValueError(f"Cannot transition to REJECTED from {self.action.state}")
        self.action.state = ActionState.REJECTED
        self.action.updated_at = datetime.now(timezone.utc)

    def execute(self):
        if self.action.state != ActionState.APPROVED:
            # We strictly enforce approval before execution to prevent unauthorized external actions
            raise ValueError(f"Cannot execute without approval. Current state: {self.action.state}")
        self.action.state = ActionState.EXECUTED
        self.action.updated_at = datetime.now(timezone.utc)
