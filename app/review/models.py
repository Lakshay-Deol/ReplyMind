from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

Category = Literal["question", "complaint", "praise", "other"]


class DraftRecord(BaseModel):
    comment_id: str
    reply_text: str
    category: Category = "other"
    confidence: float = Field(ge=0.0, le=1.0)
    needs_human: bool = True
    reasons: List[str] =  Field(default_factory=list)
    # helpful for UI/debug
    author: Optional[str] = None
    published_at: Optional[str] = None
    original_text: Optional[str] = None
    triage_reasons: List[str] =  Field(default_factory=list)
    created_at: Optional[str] = None


class ApproveRequest(BaseModel):
    edited_reply_text: Optional[str] = None


class RejectRequest(BaseModel):
    reason: Optional[str] = None
