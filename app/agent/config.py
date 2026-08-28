import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AgentConfig:
    MINDS_BUILDER_API_KEY: str = ""
    AGENT_MAX_HISTORY: int = 10
    AGENT_CONFIDENCE_THRESHOLD: float = 0.75

    def __post_init__(self) -> None:
        key = os.getenv("MINDS_BUILDER_API_KEY")
        if key:
            object.__setattr__(self, "MINDS_BUILDER_API_KEY", key)
