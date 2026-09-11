from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SessionHistoryConfig:
    collection_name: str
    dimensions: int
    score_threshold: float = 0.6
