from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class AgentAction:
    action_type: str
    target_id: str
    payload: Dict[str, Any]

def create_draft_action(comment_id: str, text: str) -> AgentAction:
    return AgentAction("DRAFT_REPLY", comment_id, {"text": text})

def create_recommendation_action(rec_id: str, recommended_action: str) -> AgentAction:
    return AgentAction("CREATE_RECOMMENDATION", rec_id, {"action": recommended_action})
