import logging
from abc import ABC, abstractmethod
from typing import Any

from app.agent.memory import get_relevant_memory
from app.agent.models import AgentRecommendation
from app.ai.opportunity_detector import detect_opportunities
from app.ai.types import TriageResult
from app.youtube.comment_fetcher import CommentFetcher

logger = logging.getLogger(__name__)

class AgentTool(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        pass

    @abstractmethod
    def execute(self, **kwargs) -> Any:
        pass

class FetchCommentsTool(AgentTool):
    name = "fetch_comments"
    description = "Fetches new YouTube comments"
    
    def __init__(self, fetcher: CommentFetcher, channel_id: str):
        self.fetcher = fetcher
        self.channel_id = channel_id

    def execute(self, **kwargs) -> Any:
        logger.info(f"Tool called: {self.name}")
        from app.youtube.comment_fetcher import FetchConfig
        res = self.fetcher.fetch_latest_for_channel(self.channel_id, FetchConfig(page_size=20, max_pages=1))
        return res.new_comments

class InspectMemoryTool(AgentTool):
    name = "inspect_memory"
    description = "Inspects creator memory for context"
    
    def execute(self, **kwargs) -> Any:
        logger.info(f"Tool called: {self.name} - Memory accessed")
        return get_relevant_memory()

class AnalyzeSignalsTool(AgentTool):
    name = "analyze_signals"
    description = "Analyzes audience signals for a comment"
    
    def execute(self, comment_text: str, triage_result: TriageResult, **kwargs) -> Any:
        logger.info(f"Tool called: {self.name}")
        return detect_opportunities(comment_text, triage_result)

class PrepareRecommendationTool(AgentTool):
    name = "prepare_recommendation"
    description = "Prepares an action recommendation requiring human approval"
    
    def execute(self, rec: AgentRecommendation, **kwargs) -> Any:
        logger.info(f"Tool called: {self.name} - Recommendation created")
        logger.info("Human approval required")
        return rec
