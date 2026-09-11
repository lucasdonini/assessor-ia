from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MongoConfig:
    uri: str
    database_name: str


@dataclass(frozen=True, slots=True)
class PostgresConfig:
    url: str


@dataclass(frozen=True, slots=True)
class AgentRuntimeConfig:
    timezone_name: str
    execution_timeout_seconds: float


@dataclass(frozen=True, slots=True)
class ProfileIndexConfig:
    dimensions: int
