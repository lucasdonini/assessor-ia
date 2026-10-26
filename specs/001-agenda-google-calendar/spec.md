# 001 Agenda persistence and per-user Google Calendar

Status: Ready
Owner: Project maintainer
Created: 2026-10-26
Last updated: 2026-10-26

## Problem and current behavior

The source reference is `ROTEIRO_ETAPA5_2.html`, supplied by the user. Its copy,
installation and replacement commands are teaching material, not execution
authorization. This specification adapts its outcomes, rather than its file layout.

Verified against the repository:
- `app/infrastructure/agents/agenda/agenda_agent.py` exposes only SearchHistoryTool.
- `agenda_prompt.py` explicitly states that real agenda operations are unavailable.
- Domain models, application repositories and Alembic revisions contain no event
  persistence. The reference's existing events table cannot be assumed to exist.
- AgendaOutput has no typed write receipt. Composition provides no calendar tools.
- `app/mcp_server.py` is an existing financial MCP server, not a Google client.
- API identity uses an unverified UUID; Google login and OAuth storage are absent.
- `.gitignore` does not currently ignore the reference's credential/token filenames.

## Intended outcome and scope

An authenticated user can query their local agenda, create an event, and have it
copied to their explicitly connected Google primary calendar. Local persistence
survives remote failure. Responses distinguish local and Google outcomes.

Included: Google application login, separate Calendar consent, local events,
per-user credentials, conflict confirmation, MCP client with bounded REST fallback,
typed write evidence, frontend account controls, and automated/manual verification.

Excluded: recurrence, all-day events, invitations, notifications, reminders,
rescheduling/deletion tools, importing Google events, bidirectional synchronization,
Google-based availability, background retry workers, multi-worker deployment,
production hosting and automatic claims of legacy demo data. Publishing local
agenda tools through the existing MCP server is an optional reference exercise and
is deferred; the nine existing tools must remain compatible.

## Requirements

| ID | Requirement | Acceptance |
| --- | --- | --- |
| FR-001 | Authenticate through Google OIDC; derive ownership server-side from a verified identity, never from X-User-ID or tool arguments. Protect all existing private HTTP routes. | AC-001 |
| FR-002 | Provide separate Connect, connection status and Disconnect Calendar actions for the signed-in user. Calendar denial must not prevent local agenda use. | AC-002 |
| FR-003 | Persist local events with UUID, immutable user_id, title, source_text, aware start/end, optional location/notes, and recorded_at. Require title, date, start and end/duration before mutation; end must follow start. | AC-003 |
| FR-004 | Query only the acting user's events. Support case-insensitive text over title/location/notes/source_text; one local day OR inclusive local start/end dates; default limit 20, range 1..200. Order by start then ID ascending. Without a date filter include past events too. | AC-004 |
| FR-005 | Check interval overlaps locally before creating. On conflict, return details and request explicit confirmation; do not write either destination until confirmed. Recheck under serialization immediately before writing. | AC-005 |
| FR-006 | After a successful local commit, attempt Google creation using the same persisted title, start/end, location and notes, for that user's connection only. Never create remotely if local creation fails. | AC-006 |
| FR-007 | Use MCP Streamable HTTP, initialize, discover/validate create_event and invoke it. Support REST fallback only for a positively identified disabled/unavailable MCP service rejection before execution; not for general 403, permission denial, timeout, 5xx or ambiguous outcome. | AC-007 |
| FR-008 | Persist separate local and remote evidence: local ID, operation ID, Google ID/link when known, transport and state. States: not_connected, pending, succeeded, failed, unknown. Never undo a local event because Google failed. | AC-008 |
| FR-009 | Creation claims require a real local receipt; Google success additionally requires a provider event ID. Preserve the distinction through specialist output, orchestration and final response. Keep history search for context, never as agenda evidence. | AC-009 |
| FR-010 | Repeated execution of the same operation must return the existing local result and must not recreate confirmed Google events. An ambiguous remote result requires reconciliation before any further create attempt. | AC-010 |
| NFR-001 | Preserve existing dependency directions, asynchronous I/O, Dishka composition, strict Python typing, safe public errors and configured Ruff rules. No folder restructuring. | AC-011 |
| NFR-002 | Encrypt tokens at rest, isolate by owner, refresh per user with serialization and keep secrets out of frontend responses, logs, prompts, history, Git and model-accessible tools. | AC-002, AC-012 |
| NFR-003 | Preserve existing financial/chat data and user ownership through additive migrations. No resets or automatic legacy-account merging. | AC-001, AC-011 |
| NFR-004 | Remote work must fit the existing 120-second graph deadline: at most 30 seconds for the complete Calendar attempt including refresh, handshake and fallback. Cancellation must propagate and leave recoverable state. | AC-007, AC-008 |

## Acceptance scenarios

- **AC-001 Identity:** first verified Google login creates one local user and stable
  issuer/subject mapping; repeat login reuses it. Anonymous private requests return
  401; a forged UUID cannot select another owner. Existing demo users and their
  records remain unchanged and unclaimed. Login never matches accounts by email.
- **AC-002 Consent and isolation:** A connects Calendar, B does not. Only A's
  operations can read A's encrypted grant. Denial/expired grant reports a reconnect
  action; B still creates locally. Disconnect prevents future token use, deletes
  stored grant material and attempts revocation without deleting either agenda.
- **AC-003 Input:** missing duration/end asks a focused question and writes nothing.
  Invalid dates, naive tool timestamps and end <= start fail before I/O. A complete
  ordinary create request itself authorizes creation; no redundant confirmation.
- **AC-004 Search:** text and date combinations, empty results, cross-midnight
  starts, invalid limits and mixed day/range filters behave as specified. Convert
  local dates in America/Sao_Paulo into UTC half-open bounds. Filter on start time,
  matching the reference. Empty or truncated results do not prove full availability.
- **AC-005 Conflict:** overlap uses existing.start < requested.end AND
  existing.end > requested.start; adjacent events do not conflict. Include events
  that started on a prior day. Confirmation is bound to owner and exact proposal;
  changes or newly conflicting events require fresh confirmation. Concurrent
  same-user requests cannot both bypass the check.
- **AC-006 Successful creation:** database readback proves local commit; provider
  readback proves the same event exists in the connected user's primary calendar.
  Local commit failure results in zero Google mutation calls.
- **AC-007 Provider boundary:** verify initialize/discovery/schema mapping, MCP
  tool-level errors, HTTP 401/403/429/5xx, refresh and global deadline. Only a
  definitive service-disabled rejection permits one REST attempt. MCP timeout
  after send never triggers a second create through REST.
- **AC-008 Partial results:** Google denial retains the local event with failed
  state and a truthful response. Timeout or crash after remote submission marks
  unknown/recoverable pending, not success. Restart cannot silently retry creation.
- **AC-009 Model behavior:** evaluate create, consult, ambiguous dates, conflict,
  local failure, absent consent and remote failure in Portuguese. Fabricated
  receipts are rejected by deterministic validation; orchestration cannot convert
  a proposal into a success. Trace actual tools and verify persisted effects.
- **AC-010 Repetition:** repeated tool calls with the same server-issued operation
  reuse the local ID; different intentional requests may create separate events.
  Confirmed remote results are reused. Unknown results require external readback
  before an operator resolves their state; no automatic remote retry in this scope.
- **AC-011 Compatibility:** migrate a populated previous schema without losing
  transactions, profiles or sessions. Existing private routes retain their business
  responses under authenticated ownership. Existing financial MCP tests still pass.
- **AC-012 OAuth/session:** reject state replay, invalid nonce/issuer/audience,
  expired identity tokens, session fixation and cross-user callback binding.
  Refresh and disconnect races cannot restore deleted credentials. No credential
  appears in captured logs, model input, frontend storage or public errors.

## Contracts and data behavior

Local agenda remains authoritative for queries. Google-only appointments are not
included; say explicitly that availability applies only to the Assessor's records.
Conflict queries cannot use a truncated display list as their source of truth.

Use typed inputs/results and the existing AgentTool success/failure convention.
Expose add_event and query_events internally; remote export is a deterministic
service step within creation, not a separately ordered action entrusted to the
model. Preserve add_google_event's capability through an application port; do not
expose arbitrary provider names, tokens, URLs or calendar IDs to the model.

The application uses server-side sessions with an opaque HttpOnly, SameSite=Lax
cookie, Secure outside localhost; 24-hour absolute expiry, logout invalidation and
CSRF validation on mutations. Google issuer/subject identifies the login account.
Calendar authorization is an additional explicit consent flow for the same Google
subject. One connection and primary calendar per application user. Switching the
Calendar account requires signing into that account in the application instead.

Proposed HTTP surface: GET /api/auth/google/start, GET /api/auth/google/callback,
GET /api/auth/me, POST /api/auth/logout; GET /api/calendar/connection,
POST /api/calendar/google/connect, GET /api/calendar/google/callback,
DELETE /api/calendar/connection. OAuth initiation returns/redirects to provider
authorization; callbacks redirect to a fixed frontend destination. Connection
responses expose status/account display only. No raw token response.

Public anonymous demo user creation/listing and UUID switching are retired from
the web flow. Legacy data remains preserved but inaccessible through UUID spoofing.
Manual verified legacy linking is a separate future feature; no destructive
migration or reassignment. The existing local MCP process remains a trusted local
interface selected by ASSESSOR_MCP_USER_ID; it does not gain Google credentials.

Store events and Google connection/operation metadata in PostgreSQL; use existing
MongoDB infrastructure for expiring OAuth transactions and server-side sessions.
Credentials use authenticated encryption with a deployment-managed key and key ID.
No encryption key is stored alongside ciphertext. Retain local events and operation
receipts until an explicitly authorized future retention policy; expire OAuth
transactions after 10 minutes, one use only. Disconnect erases token material.

Operation IDs are issued by application execution context and persisted before
external I/O, never invented by the LLM. This release prevents duplicate tool
execution per operation; separate repeated user messages are new requests. Provider
exactly-once semantics are not promised. Single backend worker remains the supported
deployment; database owner-level serialization protects local check-and-create.

## Decisions and open questions

The user explicitly selected per-user Calendar connection, Google application
authentication, confirmation on conflicts and clarification of missing duration.
No blocking product questions remain. The following bounded defaults make the
scope actionable: primary calendar only; timed one-off events; separate Calendar
consent; local-first persistence; no automated retry after uncertain submission;
no automatic claims of legacy demo data; optional external agenda publication
deferred. These choices are reviewable specification decisions, not implemented
behavior or authorization to generate code.

External readiness is not verified: Cloud project/consent/client configuration,
preview access, write scopes, redirect URIs and secret provisioning must pass the
preflight task before real integration. Never assume the professor's setup exists.
MCP acceptance requires one verified MCP write; REST success alone is insufficient.

## Sources and completion criteria

Official sources checked on 2026-10-26:
- [Calendar MCP configuration](https://developers.google.com/workspace/calendar/api/guides/configure-mcp-server): preview and OAuth/service prerequisites.
- [MCP create_event](https://developers.google.com/workspace/calendar/api/v3/reference/mcp/tools_list/create_event): provider input/output contract.
- [Web OAuth](https://developers.google.com/identity/protocols/oauth2/web-server): server consent and token lifecycle.
- [REST events.insert](https://developers.google.com/workspace/calendar/api/v3/reference/events/insert): fallback contract and write scopes.

Completion requires all acceptance evidence in tasks.md, migration preservation,
two-user isolation, representative model evaluation and real MCP/Calendar readback.
Ready means no product questions block planning; it does not mean implemented,
externally provisioned or approved for code generation.
