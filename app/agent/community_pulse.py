from typing import List, Optional

from pydantic import BaseModel

from app.ai.opportunity_models import OpportunityResult, OpportunitySignalType
from app.paths import opportunities_dir


class CommunityPulse(BaseModel):
    total_comments_analyzed: int
    high_priority_comments: int
    questions: int
    recurring_questions: int
    content_requests: int
    complaints: int
    spam: int
    potential_superfans: int
    collaboration_opportunities: int
    top_audience_topics: List[str]
    top_recommendation: Optional[str]
    explanation_for_recommendation: Optional[str]
    
    def format_text(self) -> str:
        lines = [
            "ReplyMind Community Pulse",
            "",
            f"{self.total_comments_analyzed} comments analyzed",
            "",
            f"{self.high_priority_comments} high-priority conversations",
            f"{self.questions} questions",
            f"{self.content_requests} content requests",
            f"{self.potential_superfans} potential superfans",
            f"{self.complaints} complaints",
            f"{self.collaboration_opportunities} collaboration opportunities",
            f"{self.spam} spam",
            ""
        ]
        
        if self.explanation_for_recommendation:
            lines.extend([
                "Top audience signal:",
                "",
                self.explanation_for_recommendation,
                "",
                "Recommendation:",
                "",
                self.top_recommendation or ""
            ])
            
        return "\n".join(lines)
    
def generate_community_pulse(signals: List[OpportunityResult]) -> CommunityPulse:
    pulse = CommunityPulse(
        total_comments_analyzed=len(signals),
        high_priority_comments=sum(1 for s in signals if s.priority >= 75),
        questions=sum(1 for s in signals if s.signal_type == OpportunitySignalType.QUESTION),
        recurring_questions=sum(1 for s in signals if s.signal_type == OpportunitySignalType.FAQ),
        content_requests=sum(1 for s in signals if s.signal_type == OpportunitySignalType.CONTENT_REQUEST),
        complaints=sum(1 for s in signals if s.signal_type == OpportunitySignalType.COMPLAINT),
        spam=sum(1 for s in signals if s.signal_type == OpportunitySignalType.SPAM),
        potential_superfans=sum(1 for s in signals if s.signal_type == OpportunitySignalType.SUPERFAN),
        collaboration_opportunities=sum(1 for s in signals if s.signal_type == OpportunitySignalType.COLLABORATION),
        top_audience_topics=[],
        top_recommendation=None,
        explanation_for_recommendation=None
    )
    
    # Calculate top recommendation based on the highest priority signal
    # Exclude SPAM and OTHER from top recommendation
    valid_signals = [s for s in signals if s.signal_type not in (OpportunitySignalType.SPAM, OpportunitySignalType.OTHER)]
    if valid_signals:
        top_signal = max(valid_signals, key=lambda s: s.priority)
        pulse.top_recommendation = top_signal.recommended_action
        pulse.explanation_for_recommendation = top_signal.explanation
        
    return pulse

def save_community_pulse(pulse: CommunityPulse) -> None:
    directory = opportunities_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "pulse.json"
    temp_path = path.with_suffix('.tmp')
    try:
        temp_path.write_text(pulse.model_dump_json(indent=2), encoding="utf-8")
        temp_path.replace(path)
    except OSError:
        pass

def load_community_pulse() -> Optional[CommunityPulse]:
    path = opportunities_dir() / "pulse.json"
    if not path.exists():
        return None
    try:
        return CommunityPulse.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception:
        return None
