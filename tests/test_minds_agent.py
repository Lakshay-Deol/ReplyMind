import logging
from unittest.mock import MagicMock

from app.agent.action_router import ActionState, ActionType
from app.agent.minds_agent import MindsAgent
from app.agent.tools import AnalyzeSignalsTool, InspectMemoryTool, PrepareRecommendationTool
from app.ai.openai_client import OpenAIClient
from app.ai.types import CommentCategory, TriageDecision, TriageResult


def test_minds_agent_initialization(caplog):
    caplog.set_level(logging.INFO)
    mock_client = MagicMock(spec=OpenAIClient)
    
    tools = [
        InspectMemoryTool(),
        AnalyzeSignalsTool(),
        PrepareRecommendationTool()
    ]
    
    agent = MindsAgent(client=mock_client, tools=tools)
    
    assert "Agent started" in caplog.text
    assert len(agent.tools) == 3

def test_minds_agent_process_comment(caplog):
    caplog.set_level(logging.INFO)
    mock_client = MagicMock(spec=OpenAIClient)
    
    tools = [
        InspectMemoryTool(),
        AnalyzeSignalsTool(),
        PrepareRecommendationTool()
    ]
    
    agent = MindsAgent(client=mock_client, tools=tools)
    
    triage_result = TriageResult(
        decision=TriageDecision.DRAFT_REPLY,
        category=CommentCategory.QUESTION,
        reasons=[],
        spam_score=0.0,
        relevance_score=0.8
    )
    
    rec = agent.process_comment("comment-123", "How do I do this?", triage_result)
    
    # Check that tools logged correctly
    assert "Tool called: inspect_memory - Memory accessed" in caplog.text
    assert "Tool called: analyze_signals" in caplog.text
    assert "Tool called: prepare_recommendation - Recommendation created" in caplog.text
    assert "Human approval required" in caplog.text
    
    # Check recommendation (which is now an AgentActionPlan)
    assert rec.action_type == ActionType.DRAFT_REPLY
    assert rec.state == ActionState.PENDING_APPROVAL
    assert "comment-123" in rec.source_comments
