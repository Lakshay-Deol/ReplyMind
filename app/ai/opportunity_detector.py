import re

from app.ai.opportunity_models import OpportunityResult, OpportunitySignalType
from app.ai.scoring import calculate_priority
from app.ai.types import CommentCategory, TriageDecision, TriageResult


def detect_opportunities(comment_text: str, triage_result: TriageResult) -> OpportunityResult:
    text_lower = comment_text.lower()
    
    # Base scoring inputs
    engagement = min(len(text_lower) / 200.0, 1.0)
    relevance = triage_result.relevance_score
    
    # 1. SPAM
    if triage_result.decision == TriageDecision.SPAM or "buy followers at" in text_lower:
        priority = calculate_priority(engagement=engagement, sentiment_risk=1.0)
        return OpportunityResult(
            signal_type=OpportunitySignalType.SPAM,
            confidence=0.95 if "buy followers" in text_lower else triage_result.spam_score,
            priority=priority,
            explanation="Spam detected based on triage score or keyword.",
            recommended_action="Delete comment and block user."
        )

    # 2. URGENT
    if re.search(r'\b(urgent|help please|asap|emergency)\b', text_lower):
        priority = calculate_priority(engagement=engagement, relevance=relevance, sentiment_risk=1.0)
        return OpportunityResult(
            signal_type=OpportunitySignalType.URGENT,
            confidence=0.85,
            priority=priority,
            explanation="Comment contains urgent keywords.",
            recommended_action="Review and reply immediately."
        )

    # 3. TOXICITY
    if re.search(r'\b(terrible|worst|awful|idiot|stupid)\b', text_lower):
        priority = calculate_priority(engagement=engagement, sentiment_risk=0.9)
        return OpportunityResult(
            signal_type=OpportunitySignalType.TOXICITY,
            confidence=0.8,
            priority=priority,
            explanation="Comment contains toxic or hostile language.",
            recommended_action="Review for moderation or deletion."
        )

    # 4. COLLABORATION
    if re.search(r'\b(collaborate|collab|work together)\b', text_lower):
        priority = calculate_priority(engagement=engagement, relevance=relevance, creator_goals_alignment=0.9)
        return OpportunityResult(
            signal_type=OpportunitySignalType.COLLABORATION,
            confidence=0.9,
            priority=priority,
            explanation="User is proposing a collaboration.",
            recommended_action="Assess user's channel and DM if interested."
        )

    # 5. PURCHASE_INTENT
    if re.search(r'\b(buy|purchase|how much is|where can i (buy|get))\b', text_lower):
        priority = calculate_priority(engagement=engagement, relevance=relevance, creator_goals_alignment=1.0)
        return OpportunityResult(
            signal_type=OpportunitySignalType.PURCHASE_INTENT,
            confidence=0.85,
            priority=priority,
            explanation="User is expressing interest in buying a product.",
            recommended_action="Provide a direct link to the product/store."
        )

    # 6. SUPERFAN
    if re.search(r'\b(huge fan|third video|always watch|love your channel|biggest fan)\b', text_lower):
        priority = calculate_priority(engagement=engagement, relevance=relevance, recurrence=0.9)
        return OpportunityResult(
            signal_type=OpportunitySignalType.SUPERFAN,
            confidence=0.9,
            priority=priority,
            explanation="User is demonstrating high loyalty (Superfan).",
            recommended_action="Express deep gratitude and consider pinning."
        )

    # 7. CONTENT_REQUEST
    if re.search(r'\b(make a video|tutorial on|can you explain|do a video)\b', text_lower):
        priority = calculate_priority(engagement=engagement, relevance=relevance, creator_goals_alignment=0.7)
        return OpportunityResult(
            signal_type=OpportunitySignalType.CONTENT_REQUEST,
            confidence=0.85,
            priority=priority,
            explanation="User is requesting specific content or a tutorial.",
            recommended_action="Add to content ideas backlog and acknowledge."
        )

    # 8. TREND
    if re.search(r'\b(trend|viral|everyone is doing|challenge)\b', text_lower):
        priority = calculate_priority(engagement=engagement, relevance=relevance)
        return OpportunityResult(
            signal_type=OpportunitySignalType.TREND,
            confidence=0.75,
            priority=priority,
            explanation="User mentioned a trend or viral topic.",
            recommended_action="Evaluate if trend aligns with channel niche."
        )

    # 9. COMPLAINT
    if triage_result.category == CommentCategory.COMPLAINT or re.search(r'\b(skipped|doesn\'t work|issue|problem)\b', text_lower):
        priority = calculate_priority(engagement=engagement, relevance=relevance, sentiment_risk=0.8)
        return OpportunityResult(
            signal_type=OpportunitySignalType.COMPLAINT,
            confidence=0.85,
            priority=priority,
            explanation="Comment is expressing a complaint or issue.",
            recommended_action="Address the issue politely and provide a fix if possible."
        )

    # 10. QUESTION / FAQ
    if triage_result.category == CommentCategory.QUESTION or '?' in text_lower or "how did you" in text_lower:
        # Simplistic FAQ detection
        if re.search(r'\b(what camera|what software|how old|where do you live)\b', text_lower):
            priority = calculate_priority(engagement=engagement, relevance=relevance, recurrence=0.8)
            return OpportunityResult(
                signal_type=OpportunitySignalType.FAQ,
                confidence=0.8,
                priority=priority,
                explanation="Common frequently asked question.",
                recommended_action="Reply with canned FAQ response."
            )
        else:
            priority = calculate_priority(engagement=engagement, relevance=relevance)
            return OpportunityResult(
                signal_type=OpportunitySignalType.QUESTION,
                confidence=0.9,
                priority=priority,
                explanation="General question.",
                recommended_action="Answer the question directly."
            )

    # 11. PRAISE
    if triage_result.category == CommentCategory.PRAISE:
        priority = calculate_priority(engagement=engagement, relevance=relevance, sentiment_risk=0.1)
        return OpportunityResult(
            signal_type=OpportunitySignalType.PRAISE,
            confidence=0.9,
            priority=priority,
            explanation="Positive praise comment.",
            recommended_action="Heart or short thank you."
        )

    # 12. OTHER
    priority = calculate_priority(engagement=engagement, relevance=relevance)
    return OpportunityResult(
        signal_type=OpportunitySignalType.OTHER,
        confidence=0.5,
        priority=priority,
        explanation="General or neutral comment without specific strong signals.",
        recommended_action="No specific action needed."
    )
