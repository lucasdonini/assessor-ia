# 001 Implementation plan

Specification: [spec.md](spec.md)
Last updated: 2026-10-26

## Verified context and architectural adaptation

Read agenda_agent.py, agenda_prompt.py, specialist_output.py, composition.py,
bootstrap/container.py and providers, existing migrations, financial tool models,
README.md, .gitignore, specs conventions and the supplied HTML. Agenda operations,
events persistence and Google authentication are absent. Preserve history search,
existing financial services, graph topology and the application directory layout.

The HTML's synchronous decorators, raw SQL, global token file, manual async-loop
bridge, broad exception catches and prompt-only write sequencing do not fit the
repository. Add responsibilities within existing layers; do not copy its modules.

## Approach and affected layers

| Requirements | Existing layer/path | Proposed responsibility |
| --- | --- | --- |
| FR-001/002, NFR-002 | app/api/routes, dependencies; frontend/src | Login, server-derived user context, OAuth callbacks, connection UI, remove UUID selector from web flow |
| FR-001/002 | app/domain/model, app/application/repositories, app/services | External identity, connection ownership, session/consent lifecycle contracts and coordination |
| FR-003/004/005/010 | app/domain/model, app/application/models and repositories, app/services | Typed event, validated query/proposal, conflict confirmation and idempotent local creation |
| FR-006/007/008 | app/application/ports, app/services | Calendar export port and deterministic local-first creation workflow |
| FR-003/008, NFR-003 | app/infrastructure/postgres/entities and repositories, migrations/versions | Add events, external identity, encrypted connection grants and operation receipts; indexes and uniqueness |
| FR-001/002, NFR-002 | app/infrastructure/mongodb | Expiring OAuth state and opaque app sessions in dedicated collections; preserve chat collections |
| FR-006/007, NFR-004 | app/infrastructure | Async Google OAuth/OIDC and MCP/REST adapters; typed provider error classification; bounded cancellation-aware I/O |
| FR-009 | app/infrastructure/agents/agenda and _core/schemas | Inject agenda tools, preserve history search, structured receipts, truthful examples and deterministic receipt validation |
| FR-009 | app/infrastructure/agents/orquestrator | Preserve local/Google distinctions and clarification/conflict states |
| NFR-001 | app/bootstrap/providers, composition.py | Inject ports, configs, services and tool instances; services never import MCP/LangChain adapters |

New filenames inside these folders will follow existing naming conventions.
Configuration changes are listed for future authorized implementation only:
settings/config/provider registration, .env.example, .gitignore and dependency
manifests. No changes to docker-compose.yml or alembic.ini are needed by this plan.

## Decisions and provider contract

- Google login uses a verified OIDC identity and server-side sessions. Validate
  signature, expiry, issuer, audience, nonce and OAuth state using maintained
  libraries; never implement JWT cryptography manually. Keep OAuth state distinct
  from chat session IDs. Protect all existing private routes, not only agenda.
- Calendar consent follows login and binds to the same owner and Google subject.
  Request offline access and store refreshed credentials per owner; select minimum
  provider-supported write scopes during preflight. Read-only setup examples do
  not establish permission to create events. No global access-token override.
- Configuration supplies login/calendar OAuth client settings, fixed redirect and
  frontend URLs, MCP endpoint, encryption key/key ID and provider deadline through
  existing SettingsProvider. Separate login and agent OAuth clients are supported
  when required by Google's agent-client policy. No private SDK imports.
- Discover create_event and validate the expected schema. Map title to summary,
  aware times to startTime/endTime, timezone to America/Sao_Paulo and use primary.
  Map a successful provider ID/link to a typed receipt. MCP isError is failure even
  when HTTP is 200. Treat provider text as data, never as model instructions.
- REST mapping uses summary, start/end dateTime/timeZone and the primary calendar.
  Restrict fallback to a structured, definitive MCP-service-disabled rejection.
  Generic exception text or any occurrence of a hostname is not sufficient.
- Keep remote export in the event service workflow so a model cannot report local
  success then omit the Google attempt, change its parameters or export another
  owner's event. Do not hold a database transaction open during remote I/O.

## Data, concurrency and recovery

Additive PostgreSQL migrations introduce event ownership foreign keys, identity
uniqueness on issuer/subject, one grant per owner, and operation uniqueness per
owner/operation ID. Store timezone-aware timestamps, Google remote ID/link,
transport, export status, safe failure code and update timestamps. Migrations
preserve previous users and all current transaction/session/profile data.

Use database owner-level transaction serialization for overlap recheck and local
insert. Confirmation proposals contain owner, exact fields, observed conflict set
and server-generated ID, expire after 10 minutes and are invalid after changes.
No data mutation occurs during clarification or conflict confirmation requests.

Persist pending export before calling Google; record succeeded/failed/unknown
afterwards. Stale pending after interruption is treated as uncertain and not
retried automatically. An explicit operator reconciliation uses provider readback
before resolving the receipt. A failed remote call never rolls back the local
commit. No distributed transaction, blind retries or exactly-once claim.

Use a per-owner grant version/lock for refresh/disconnect coordination. Disconnect
invalidates the local grant before provider revocation; revocation failure is
reported without making deleted credentials usable again. Cookie sessions expire
after 24 hours; OAuth state and confirmation proposals after 10 minutes.

Legacy users cannot be claimed just by knowing their UUID. Retire public user
listing/creation and frontend UUID selection; preserve legacy records without
automatic reassignment. Document this intentional compatibility change. The
trusted local financial MCP configuration remains unchanged.

## Errors and observability

Separate unauthenticated, forbidden, invalid proposal, conflict, reconnect-needed,
service-disabled, provider-failed and unknown-outcome cases. Internal exceptions
stay in redacted diagnostics; map to safe application errors/ToolFailure results.
Do not catch BaseException or swallow cancellation. Log operation IDs and stages,
not tokens, authorization codes, raw provider bodies or event contents.

## Verification and delivery

1. Verify Cloud/OAuth write access and runtime SDK contracts without changing live
   data. Capture sanitized schema/eligibility evidence. No automatic Cloud changes.
2. Deliver identity and consent boundary, then additive event persistence, then
   service orchestration, provider adapters, tools/prompts and frontend integration.
3. Test OAuth rejection/replay/CSRF and owner isolation with synthetic identities.
   Test SQL filters, migrations and concurrency in disposable databases.
4. During future implementation, use the Postman api-simulation workflow for HTTP
   dependency failure scenarios, plus protocol-faithful MCP tests. No Postman setup
   is necessary for this documentation-only delivery.
5. Exercise real authorized Google test accounts only after controlled checks;
   read back local and Google event IDs. Record whether MCP or fallback was used.
6. Evaluate representative Portuguese prompts with actual tool traces and
   persistence evidence; prompt string tests alone cannot establish correctness.
7. Run appropriate Ruff, formatting, MyPy, pytest and frontend checks, including
   financial MCP regressions. Record actual outcomes without assumed passes.

Recovery disables Calendar export while retaining local agenda data and receipts.
Do not drop new tables or remove populated migrations as an automatic rollback.
Authentication must never fall back to trusting X-User-ID after an OAuth failure.

## Risks and readiness

No unresolved product choices remain after the user's four answers. Cloud preview
eligibility, agent OAuth settings, approved scopes and live account access are
external preflight gates, not verified facts. If eligibility blocks a real MCP
write, keep the feature incomplete; do not relabel REST success as MCP evidence.
Provisioning secrets or modifying configuration is not authorized by this plan.

## Implementation decisions and evidence

The user's subsequent implementation request authorized code, example configuration,
semantic commits and a draft PR. No live environment configuration was changed.
Conflict confirmation uses a CSRF-protected HTTP action and an explicit frontend
button, never a tool argument. MongoDB OAuth transactions are single-use and checked
for expiration independently of TTL cleanup. Token refresh, export and disconnect
share an owner-level lock for the supported single-worker deployment.

The final agenda write response is generated from server-collected tool receipts
using trusted status templates. It relies on a real internal local receipt and
remote state, without exposing IDs or echoing event contents. This protects the
checkpoint/final answer from model rewriting of partial failures, while normal
non-write responses retain the existing
output guardrail. Payload logging is redacted for the agenda tools; OAuth query
parameters are removed from Uvicorn callback access records.

The installed MCP v2 SDK wraps HTTP errors as MCPError, so a public HTTP response
hook retains structured rejection evidence for fallback classification. Cleanup
failure cannot replace an already obtained receipt or cause a second create.
Five real-HTTP simulation cases passed, including commit followed by HTTP 500.
Current checks and remaining real-service/model gates are recorded in tasks.md.
