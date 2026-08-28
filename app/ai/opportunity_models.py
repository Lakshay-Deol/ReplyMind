from enum import Enum

from pydantic import BaseModel


class OpportunitySignalType(str, Enum):
    QUESTION = "QUESTION"
    FAQ = "FAQ"
    PRAISE = "PRAISE"
    SUPERFAN = "SUPERFAN"
    COMPLAINT = "COMPLAINT"
    TOXICITY = "TOXICITY"
    SPAM = "SPAM"
    CONTENT_REQUEST = "CONTENT_REQUEST"
    COLLABORATION = "COLLABORATION"
    PURCHASE_INTENT = "PURCHASE_INTENT"
    TREND = "TREND"
    URGENT = "URGENT"
    OTHER = "OTHER"

class OpportunityResult(BaseModel):
    signal_type: OpportunitySignalType
    confidence: float
    priority: int
    explanation: str
    recommended_action: str
