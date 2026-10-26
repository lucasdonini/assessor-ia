from dataclasses import dataclass
from typing import Literal


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


@dataclass(frozen=True, slots=True, repr=False)
class GoogleConfig:
    client_id: str = ""
    client_secret: str = ""
    calendar_client_id: str = ""
    calendar_client_secret: str = ""
    login_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"
    calendar_redirect_uri: str = "http://localhost:8000/api/calendar/google/callback"
    frontend_url: str = "http://localhost:8000/"
    encryption_key: str = ""
    key_id: str = "v1"
    secure_cookies: bool = True
    transport: Literal["rest", "mcp"] = "rest"
    mcp_url: str = "https://calendarmcp.googleapis.com/mcp/v1"
    rest_url: str = "https://www.googleapis.com/calendar/v3"
    authorization_url: str = "https://accounts.google.com/o/oauth2/v2/auth"
    token_url: str = "https://oauth2.googleapis.com/token"
    certs_url: str = "https://www.googleapis.com/oauth2/v1/certs"
    revoke_url: str = "https://oauth2.googleapis.com/revoke"
