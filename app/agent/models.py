from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class SignalType(str, Enum):
    PRAISE = "praise"
    COMPLAINT = "complaint"
    QUESTION = "question"
    SUGGESTION = "suggestion"
    SPAM = "spam"
    OTHER = "other"

class RecommendationType(str, Enum):
    REPLY_DRAFT = "reply_draft"
    ACTION_SUGGESTION = "action_suggestion"
    POLICY_UPDATE = "policy_update"

class RecommendationStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"

class DecisionStatus(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"
    DEFERRED = "deferred"


class CreatorProfile(BaseModel):
    creator_name: str
    niche: str
    tone: str
    goals: List[str] = Field(default_factory=list)
    preferred_reply_length: str
    topics_to_avoid: List[str] = Field(default_factory=list)
    preferred_actions: List[str] = Field(default_factory=list)


class AudienceSignal(BaseModel):
    signal_id: str
    comment_id: str
    signal_type: SignalType
    confidence: float = Field(ge=0.0, le=1.0)
    priority: int = Field(default=0)
    explanation: str
    detected_at: datetime


class AgentRecommendation(BaseModel):
    recommendation_id: str
    recommendation_type: RecommendationType
    title: str
    description: str
    priority: int = Field(default=0)
    confidence: float = Field(ge=0.0, le=1.0)
    source_comment_ids: List[str] = Field(default_factory=list)
    proposed_action: str
    status: RecommendationStatus = Field(default=RecommendationStatus.PENDING)
    created_at: datetime


class AgentDecision(BaseModel):
    recommendation_id: str
    decision: DecisionStatus
    edited_content: Optional[str] = None
    decided_at: datetime
    decided_by: str


class AgentMemory(BaseModel):
    creator_profile: CreatorProfile
    approved_preferences: List[str] = Field(default_factory=list)
    rejected_preferences: List[str] = Field(default_factory=list)
    recurring_questions: Dict[str, int] = Field(default_factory=dict)
    recurring_topics: Dict[str, int] = Field(default_factory=dict)
    important_commenters: List[str] = Field(default_factory=list)
    previous_decisions: List[AgentDecision] = Field(default_factory=list)
    successful_actions: List[str] = Field(default_factory=list)
