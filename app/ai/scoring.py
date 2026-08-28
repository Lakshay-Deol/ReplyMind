from typing import Optional

# Weight each dimension contributes to a 0-100 priority.
WEIGHTS = {
    "sentiment_risk": 25.0,          # urgent issues or reputational risk
    "relevance": 25.0,               # how relevant to the video / niche
    "creator_goals_alignment": 20.0,  # sales, collabs, current objectives
    "engagement": 15.0,              # length and detail of the comment
    "recurrence": 15.0,              # superfan or frequently-asked
}

# A signal at or above this is surfaced as "high priority" in the pulse.
HIGH_PRIORITY_THRESHOLD = 75


def calculate_priority(
    engagement: Optional[float] = None,
    relevance: Optional[float] = None,
    recurrence: Optional[float] = None,
    sentiment_risk: Optional[float] = None,
    creator_goals_alignment: Optional[float] = None,
) -> int:
    """Priority out of 100 from the audience-intelligence factors that apply.

    Only the dimensions a caller actually measures are scored, and the result is
    normalised over those weights. Previously every unsupplied dimension counted
    as 0.0 against the full 100-point scale, so a signal was punished for facts
    nobody claimed to know: a maximally urgent complaint topped out around 49 and
    the >=75 "high priority" band was unreachable. Inputs are clamped to [0, 1].
    """
    supplied = {
        "engagement": engagement,
        "relevance": relevance,
        "recurrence": recurrence,
        "sentiment_risk": sentiment_risk,
        "creator_goals_alignment": creator_goals_alignment,
    }

    total_weight = 0.0
    score = 0.0
    for name, value in supplied.items():
        if value is None:
            continue
        weight = WEIGHTS[name]
        total_weight += weight
        score += min(max(float(value), 0.0), 1.0) * weight

    if total_weight <= 0:
        return 0

    return min(max(round(score / total_weight * 100), 0), 100)
