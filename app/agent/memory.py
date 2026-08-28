from app.agent.memory_store import safe_load_json, safe_save_json
from app.agent.models import AgentDecision, AgentMemory, CreatorProfile


def load_memory() -> AgentMemory:
    profile_data = safe_load_json("creator_profile.json", {})
    try:
        if not profile_data:
            raise ValueError("Empty profile data")
        profile = CreatorProfile(**profile_data)
    except Exception:
        profile = CreatorProfile(
            creator_name="Unknown Creator",
            niche="General",
            tone="Friendly",
            preferred_reply_length="Short",
            goals=[],
            topics_to_avoid=[],
            preferred_actions=[]
        )

    prefs = safe_load_json("preferences.json", {"approved": [], "rejected": []})
    topics = safe_load_json("topics.json", {"questions": {}, "topics": {}})
    commenters = safe_load_json("important_commenters.json", [])
    decisions_data = safe_load_json("decisions.json", [])
    
    decisions = []
    if isinstance(decisions_data, list):
        for d in decisions_data:
            try:
                decisions.append(AgentDecision(**d))
            except Exception:
                continue
                
    return AgentMemory(
        creator_profile=profile,
        approved_preferences=prefs.get("approved", []),
        rejected_preferences=prefs.get("rejected", []),
        recurring_questions=topics.get("questions", {}),
        recurring_topics=topics.get("topics", {}),
        important_commenters=commenters if isinstance(commenters, list) else [],
        previous_decisions=decisions,
        successful_actions=[]
    )

def save_memory(memory: AgentMemory) -> None:
    safe_save_json("creator_profile.json", memory.creator_profile.model_dump())
    safe_save_json("preferences.json", {
        "approved": memory.approved_preferences,
        "rejected": memory.rejected_preferences
    })
    safe_save_json("topics.json", {
        "questions": memory.recurring_questions,
        "topics": memory.recurring_topics
    })
    safe_save_json("important_commenters.json", memory.important_commenters)
    safe_save_json("decisions.json", [d.model_dump() for d in memory.previous_decisions])

def update_creator_profile(profile: CreatorProfile) -> None:
    mem = load_memory()
    mem.creator_profile = profile
    save_memory(mem)

def record_approval(decision: AgentDecision) -> None:
    mem = load_memory()
    mem.previous_decisions.append(decision)
    # keep last 50 decisions to avoid huge file size
    mem.previous_decisions = mem.previous_decisions[-50:]
    save_memory(mem)

def record_rejection(decision: AgentDecision) -> None:
    record_approval(decision)
    
def record_preference(preference: str, approved: bool) -> None:
    mem = load_memory()
    if approved:
        if preference not in mem.approved_preferences:
            mem.approved_preferences.append(preference)
    else:
        if preference not in mem.rejected_preferences:
            mem.rejected_preferences.append(preference)
    save_memory(mem)

def record_topic(topic: str, is_question: bool = False) -> None:
    mem = load_memory()
    if is_question:
        mem.recurring_questions[topic] = mem.recurring_questions.get(topic, 0) + 1
    else:
        mem.recurring_topics[topic] = mem.recurring_topics.get(topic, 0) + 1
    save_memory(mem)

def record_important_commenter(commenter_id: str) -> None:
    mem = load_memory()
    if commenter_id not in mem.important_commenters:
        mem.important_commenters.append(commenter_id)
    save_memory(mem)

def get_relevant_memory() -> AgentMemory:
    """Returns the full memory for the agent context."""
    return load_memory()
