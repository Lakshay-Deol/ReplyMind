from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List


class TriageDecision(str, Enum):
    IGNORE = "ignore"
    SPAM = "spam"
    DRAFT_REPLY = "draft_reply"
    NEEDS_HUMAN = "needs_human"  # reserved for future moderation workflows


class CommentCategory(str, Enum):
    QUESTION = "question"
    COMPLAINT = "complaint"
    PRAISE = "praise"
    OTHER = "other"


@dataclass(frozen=True)
class TriageResult:
    decision: TriageDecision
    category: CommentCategory
    reasons: List[str]
    spam_score: float = 0.0
    relevance_score: float = 0.0


@dataclass(frozen=True)
class DraftReply:
    comment_id: str
    reply_text: str
    category: CommentCategory
    confidence: float
    needs_human: bool
    reasons: List[str]
