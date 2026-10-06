# Existing project baseline

Recorded: 2026-10-06
Source revision inspected: `129d406`
Purpose: help future specifications find existing contracts and constraints.
This is a documentation snapshot, not a complete behavioral specification or a
claim that the test suites were executed during SDD setup.

## Product and layer map

Assessor.IA is a financial assistant with a FastAPI/LangGraph backend and a
React/TypeScript/Vite frontend. PostgreSQL holds financial transactions, MongoDB
holds chat sessions, and Qdrant supports FAQ and session-summary retrieval.

| Area | Starting point | Responsibility to consider in a future plan |
| --- | --- | --- |
| HTTP boundary | [API](../app/api/) | Inputs, user context, public responses, and request coordination |
| Application contracts | [Application](../app/application/) | Ports, input models, and application exceptions |
| Domain | [Domain](../app/domain/) | Domain models and business rules |
| Use cases | [Services](../app/services/) | Service coordination and explicit user scoping |
| Composition | [Bootstrap](../app/bootstrap/) | Dishka container and dependency providers |
| Technical adapters | [Infrastructure](../app/infrastructure/) | Agents, persistence, model providers, and logging |
| Web interface | [Frontend](../frontend/) | User selection and conversation interaction |
| Schema evolution | [Migrations](../migrations/) | Alembic revisions and existing-data constraints |
| Verification | [Tests](../tests/) | Unit, architectural, and integration checks |

## Contracts inspected during setup

- [The chat route](../app/api/routes/chat.py) accepts a session ID and executes the
  graph using the resolved user context. It persists the question and response.
  [The response schema](../app/api/schemas/chat.py) contains `session_id`, `content`,
  and `called_agents`. Do not assume the older plain-string response example in
  the root README represents this route's current response contract.
- [The finalization route](../app/api/routes/session.py) calls the session service
  with both session ID and user ID and returns a session summary.
- [Session coordination](../app/infrastructure/session_coordinator.py) uses
  `asyncio.Lock` per session within one event loop. This does not establish
  distributed coordination or multi-worker safety.
- [The local MCP entry point](../app/mcp_server.py) selects a user through
  `ASSESSOR_MCP_USER_ID`, validates that the user exists, and reuses financial tools
  through the existing services. Its identity model must be considered separately
  from HTTP user selection.

## Documented constraints to recheck for affected features

The [root README](../README.md) describes a demonstration identity model: selecting
a UUID does not authenticate the person using it. Sessions, transactions, and
history are scoped to users; the institutional FAQ is shared. Future specifications
must distinguish ownership enforcement from authentication.

It also documents single-worker operation, in-memory graph checkpoints, persisted
messages that do not automatically reconstruct those checkpoints, and independent
MongoDB summary persistence and Qdrant indexing. A future specification affecting
these areas must inspect the relevant implementations and define restart,
concurrency, and partial-failure behavior explicitly.

## Verification entry points

| Concern | Existing reference |
| --- | --- |
| Dependency boundaries | [Architecture tests](../tests/test_architecture/) |
| Financial user isolation | [PostgreSQL multi-user integration tests](../tests/integration/test_multiuser.py) |
| Session ownership | [MongoDB multi-user integration tests](../tests/integration/test_multiuser_mongodb.py) |
| Session concurrency | [Coordinator tests](../tests/test_infrastructure/test_session_coordinator.py) |
| Graph execution | [Graph tests](../tests/test_agents/test_graph_execution.py) |
| Summary retrieval | [History-index tests](../tests/test_infrastructure/test_session_history_index.py) |
| MCP contracts | [MCP tests](../tests/test_mcp_server.py) |
| Backend checks and markers | [Python project configuration](../pyproject.toml) |
| Frontend checks | [Frontend scripts](../frontend/package.json) |
| Automated checks | [CI workflow](../.github/workflows/ci.yml) |

Container-backed integration tests require Docker. Runtime validation of model
behavior may require external services and separate evaluation. Record which
checks were actually executed in each feature's `tasks.md`.

## Historical references

- [context.md](../context.md) contains broader project and migration context.
- [TODO.md](../TODO.md) contains historical improvement proposals. Some overlap
  with behavior already present, such as explicit finalization and session
  coordination. Inspect source before turning an item into a new requirement.
- [AGENTS.md](../AGENTS.md) defines repository collaboration constraints.

Keep these references intact. New feature specifications describe their own
verified starting state instead of treating all historical notes as current facts.
