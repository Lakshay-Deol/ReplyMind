import logging
import uuid
from datetime import datetime, timezone

from app.agent.action_router import ActionState, ActionType, AgentActionPlan
from app.ai.opportunity_models import OpportunityResult, OpportunitySignalType

logger = logging.getLogger(__name__)

class AgentPlanner:
    def plan_action(self, signal: OpportunityResult, comment_id: str) -> AgentActionPlan:
        logger.info(f"Planning action for signal: {signal.signal_type.value}")
        
        # Determine the action type based on the audience signal
        action_mapping = {
            OpportunitySignalType.QUESTION: ActionType.DRAFT_REPLY,
            OpportunitySignalType.FAQ: ActionType.DRAFT_REPLY,
            OpportunitySignalType.PRAISE: ActionType.DRAFT_REPLY,
            OpportunitySignalType.SUPERFAN: ActionType.RECOGNIZE_SUPERFAN,
            OpportunitySignalType.COMPLAINT: ActionType.ESCALATE_COMPLAINT,
            OpportunitySignalType.TOXICITY: ActionType.FLAG_FOR_REVIEW,
            OpportunitySignalType.SPAM: ActionType.MARK_SPAM,
            OpportunitySignalType.CONTENT_REQUEST: ActionType.CREATE_CONTENT_IDEA,
            OpportunitySignalType.COLLABORATION: ActionType.DRAFT_COLLABORATION,
            OpportunitySignalType.PURCHASE_INTENT: ActionType.DRAFT_REPLY,
            OpportunitySignalType.TREND: ActionType.CREATE_CONTENT_IDEA,
            OpportunitySignalType.URGENT: ActionType.ESCALATE_COMPLAINT,
            OpportunitySignalType.OTHER: ActionType.IGNORE,
        }
        
        action_type = action_mapping.get(signal.signal_type, ActionType.IGNORE)
        
        # Determine if human approval is required
        requires_approval = True
        if action_type in [ActionType.IGNORE]:
            requires_approval = False
            
        now = datetime.now(timezone.utc)
        
        plan = AgentActionPlan(
            action_id=str(uuid.uuid4()),
            action_type=action_type,
            state=ActionState.DETECTED,
            reason=signal.explanation,
            confidence=signal.confidence,
            priority=signal.priority,
            source_comments=[comment_id],
            proposed_action=signal.recommended_action,
            requires_human_approval=requires_approval,
            created_at=now,
            updated_at=now
        )
        
        return plan
