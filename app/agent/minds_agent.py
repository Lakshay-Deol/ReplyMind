import logging
import os
from typing import List, Optional

from app.agent.action_router import ActionStateMachine, AgentActionPlan
from app.agent.minds_client import MindsClient, MindsUnavailable
from app.agent.models import AgentMemory
from app.agent.planner import AgentPlanner
from app.agent.tools import AgentTool
from app.ai.openai_client import OpenAIClient
from app.ai.types import TriageResult

logger = logging.getLogger(__name__)

class MindsAgent:
    ROLE = (
        "You are ReplyMind, the AI community manager for every platform. "
        "You are a persistent Minds agent that understands conversations across a creator's social platforms, "
        "remembers their community and preferences, detects opportunities and risks, and recommends the next best action. "
        "Never publish or execute external actions without explicit creator approval."
    )

    def __init__(self, client: OpenAIClient, tools: List[AgentTool], minds_client: MindsClient = None):
        self.client = client
        self.minds_client = minds_client or MindsClient()
        self.tools = {t.name: t for t in tools}
        self.planner = AgentPlanner()
        logger.info("Agent started: ReplyMind initialized.")

    def process_comment(self, comment_id: str, comment_text: str, triage_result: TriageResult) -> AgentActionPlan:
        memory = None
        signal = None
        
        tool = self.tools.get("inspect_memory")
        if tool:
            memory = tool.execute()
            
        tool = self.tools.get("analyze_signals")
        if tool:
            signal = tool.execute(comment_text=comment_text, triage_result=triage_result)
            
        if not signal:
            raise RuntimeError("Failed to analyze signals.")
            
        # Use planner to map signal to AgentActionPlan
        action_plan = self.planner.plan_action(signal, comment_id)
        
        # State machine flow
        state_machine = ActionStateMachine(action_plan)
        state_machine.recommend()
        state_machine.request_approval()

        mode = os.getenv("REPLYMIND_MODE", "demo").lower()

        # In production mode, we consult the real Minds agent for reasoning
        minds_reasoning = ""
        if mode == "production":
            try:
                # Orchestrate the context for the real Mind. The creator memory
                # is what makes this a persistent agent rather than a classifier,
                # so it travels with every request.
                context = (
                    f"{self.ROLE}\n\n"
                    f"{self._memory_brief(memory)}"
                    f"New comment from {comment_id}: '{comment_text}'. "
                    f"Triage decision: {triage_result.decision.value}. "
                    f"Audience Signal: {signal.signal_type.value}. "
                    f"Explanation: {signal.explanation}."
                )
                minds_reasoning = self.minds_client.send_message(
                    alias=f"comment_{comment_id}",
                    message=context
                )
                logger.info(f"Received reasoning from REAL Minds API: {minds_reasoning}")
            except MindsUnavailable as e:
                # Degrade to the rule-based plan rather than inventing reasoning.
                logger.warning(f"Minds service unavailable, using rule-based plan: {e}")
                
        # Prepare recommendation using tool to ensure proper logging
        tool = self.tools.get("prepare_recommendation")
        if tool:
            # Inject minds reasoning if available
            if minds_reasoning:
                action_plan.reason = f"{action_plan.reason} | Minds: {minds_reasoning}"
            return tool.execute(rec=action_plan)

        return action_plan

    @staticmethod
    def _memory_brief(memory: Optional[AgentMemory]) -> str:
        """Condense persistent memory into a preamble for the Mind."""
        if memory is None:
            return ""

        profile = memory.creator_profile
        lines = [
            f"CREATOR: {profile.creator_name} | niche={profile.niche} | tone={profile.tone} "
            f"| preferred reply length={profile.preferred_reply_length}"
        ]
        if profile.topics_to_avoid:
            lines.append(f"AVOID: {', '.join(profile.topics_to_avoid)}")
        if memory.approved_preferences:
            lines.append(f"LEARNED: {'; '.join(memory.approved_preferences[-4:])}")
        if memory.previous_decisions:
            lines.append(f"PAST DECISIONS RECORDED: {len(memory.previous_decisions)}")
        return "\n".join(lines) + "\n\n"
