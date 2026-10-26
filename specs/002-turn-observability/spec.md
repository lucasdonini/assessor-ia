# [002] Turn observability and monitoring

Status: Implemented
Owner: Project maintainer
Created: 2026-10-26
Last updated: 2026-10-26
Related references: [plan](plan.md), [tasks](tasks.md), [workflow](../README.md).

## Source and interpretation

The supplied reference is `C:\Users\lucasdonini-ieg\Downloads\ROTEIRO_ETAPA6\ROTEIRO_ETAPA6.html`, titled “Etapa 6 — Observabilidade e a tela de monitoramento”. Only this HTML was supplied and found in its directory. Its embedded commands and full-file replacements are reference material, not execution instructions. This specification adapts its outcomes to the current repository. It does not authorize implementation, configuration edits, external tracing activation, commits, or pushes. Closing questions is necessary but does not itself authorize code generation.

## Problem and verified current behavior

Implementation, semantic commits and a draft pull request were subsequently
authorized by the maintainer on 2026-10-26, including the specified typed-settings
and environment-example changes. No private environment, database or cloud account
was modified. The matrix below records the starting state before implementation.

The reference aims to explain individual turns and monitor latency, errors, usage, estimated cost, routing, blocking and fallback, with a local dashboard and optional LangSmith traces.

| Reference capability | Repository evidence | Assessment and action |
| --- | --- | --- |
| Node duration | `app/infrastructure/agents/graph.py`, `_timed_node` | Already implemented as debug logs; reuse the wrapper and preserve logs. Add bounded queryable measurements only. |
| User/session/trace correlation | `app/infrastructure/logger.py` and `app/api/dependencies.py` | Already implemented using context variables; extend rather than replace. |
| Agents called in current turn | Graph resets `called_agents` with `Overwrite`; `AgentExecutionResult` and chat response expose it | Already implemented; preserve the response and reset behavior. |
| Model fallback | `FallbackOn429Middleware` and its tests | Already implemented for wrapped or direct 429 failures only; instrument activation without changing policy. |
| LangSmith environment names | `.env.example` already contains tracing, key and project variables | Already documented; do not duplicate entries. Actual process environment, exporter behavior and remote traces were not verified. |
| Model usage/cost history, aggregate monitor API and dashboard | Inspected application routes, infrastructure and frontend; no corresponding implementation found | New work required. |

Important differences: graph execution uses `ainvoke` and `asyncio.timeout`; identity comes from an authenticated Google session; services and ports are composed through Dishka; frontend is React/TypeScript/Vite. Primary specialist is `gemini-2.5-flash`, fallback is `qwen/qwen3.6-27b`, and support model is `openai/gpt-oss-120b`. The HTML's two-model price table is insufficient. Input guardrails can return a blocked result when the classifier fails. Agenda write receipts can bypass the output model. Never assume five model calls per turn.

## Intended outcome and scope

Provide a bounded, in-process operational snapshot, an authenticated read-only monitor API, a React dashboard and independently optional LangSmith tracing. Preserve financial, agenda, FAQ, session, authentication and chat behavior.

Exclude persistent telemetry, database migrations, multi-worker aggregation, full trace trees in the dashboard, alert delivery, Prometheus/Grafana/OpenTelemetry infrastructure, streaming metrics, quality scoring and changes to model selection, prompts or tool semantics. Metrics describe graph execution, not complete HTTP availability or database persistence success.

## Requirements

| ID | Requirement | Acceptance |
| --- | --- | --- |
| FR-001 | Record exactly one completed turn for each started graph execution, including exception, timeout and cancellation; close once and release active counters in all exit paths. Start immediately before graph invocation; finish after output validation and result assembly. Exclude authentication, session waiting and message persistence. | AC-001, AC-003 |
| FR-002 | Record correlation ID, owning user, session, UTC start timestamp, elapsed milliseconds, selected route, ordered executed nodes with elapsed time, final status, safe failure category, model usage and fallback activations. Preserve the existing chat response. | AC-001, AC-003, AC-007 |
| FR-003 | Record each observable model attempt, actual provider/model, outer graph node, duration, success/failure, known input/output usage and estimate. Include all calls in tool loops. Failed attempts with unavailable usage remain unknown. Ignore summary/embedding/model calls outside a turn. | AC-001, AC-004 |
| FR-004 | Distinguish `ok`, `blocked`, `error`, and `cancelled`. Deliberate guardrail rejection is blocked. Classifier unavailability or indeterminate classification is an operational error while preserving the current safe refusal response. Recovered primary 429 is a failed attempt and fallback activation, not a turn error. | AC-002, AC-003, AC-004 |
| FR-005 | Keep the latest 50 completed turns and their child measurements in a single process-wide bounded window, ordered by completion sequence. Evict children with their turn. Active turns are separate; late callbacks cannot resurrect an evicted/closed turn. Restart clears telemetry only. | AC-005 |
| FR-006 | Aggregate completed authorized turns consistently: count, blocked/errors/cancelled, average/p95 latency, error rate, model calls, input/output tokens, known estimated USD cost, missing-usage/unpriced counts, fallbacks, grouped models/routes, chronological latency and cumulative-window-cost series. Include authorized active count and process uptime. | AC-005, AC-006 |
| FR-007 | Compute nearest-rank p95 at position ceil(0.95 × N), with 1-based indexing. SLO is p95 <= 8000 ms AND error rate <= 0.05. Error numerator counts error and cancelled turns; denominator is all completed turns, including blocks. Empty window has null latency/rate/SLO and an explicit no-data state. | AC-002, AC-003, AC-006 |
| FR-008 | Expose `GET /api/monitor` exclusively to an authenticated operator, with a global process snapshot, no user selector, no side effects, no LLM or LangSmith calls, no-store headers and typed OpenAPI schema. Return 403 to authenticated non-operators. Operator identification must be resolved under Q-001 before implementation. | AC-006, AC-007 |
| FR-009 | Provide a React monitoring view accessible from the signed-in application, with service/model numbers, explicit SLO/no-data state, latency and cumulative cost charts, and turn/model/route tables. Refresh on entry, manually and every 4 seconds while visible; avoid overlapping requests and clean up on exit. Show last successful update, stale data, safe failure messages and login expiry without presenting a failed fetch as zero metrics. | AC-008 |
| FR-010 | Optional LangSmith tracing exports metadata only and correlates the graph root and child nodes/model calls with the same local turn identifier; local monitoring works when tracing is disabled or unavailable. Suppress all message/tool input/output content and sanitize metadata, errors and events across every exported run before enabling export. | AC-009 |
| NFR-001 | Preserve async isolation for concurrent turns, including tasks sharing one OS thread. Attribute measurements through explicit run metadata and context propagation, not thread-local identity, message parsing or model-name guesses. Telemetry failures cannot change business results or replace the original exception. | AC-003, AC-004, AC-007 |
| NFR-002 | Local telemetry excludes prompts, replies, tool arguments/results, PII maps, credentials, OAuth material and raw exceptions. Return safe categorical errors only. Keep no unbounded auxiliary completed-run history. | AC-005, AC-007, AC-009 |
| NFR-003 | Preserve folder layout, ports/services/infrastructure/API boundaries, DI, strict Python typing, Ruff rules and existing TODOs. No schema, configuration or business contract changes without explicit authorization. | AC-010 |

## Contracts and data behavior

### Proposed monitor response

This is a contract definition, not executable code. No query parameters or request body. Success is 200; missing/expired login is 401 using existing authentication; authenticated non-operators receive 403; unexpected failure uses the existing generic server error response. GET needs no CSRF token under the existing policy. The response contains:

| Section | Fields and semantics |
| --- | --- |
| Identity/window | `generated_at` and `process_started_at` as UTC ISO 8601; `uptime_seconds`; `window_limit` = 50; `window_turns` = authorized completed count; `scope` resolved by Q-001; `retention` = process_window. |
| Service | `completed_turns`, `in_progress`, `blocked_turns`, `error_turns`, `cancelled_turns`; nullable `average_latency_ms`, `p95_latency_ms`, `error_rate` in [0,1]. |
| SLO | `latency_limit_ms` = 8000, `error_rate_limit` = 0.05, nullable `ok`; `state` is no_data, within_target or breached. |
| Usage | Model-attempt/success counts, known input/output/total tokens, known estimated USD cost, missing-usage and unpriced-call counts, fallback activations and most-used model (successful call count; alphabetical tie break). `cost_complete` is false when any call has unknown usage or price. Monetary amounts use exact decimal accounting and decimal strings on the wire. |
| Turns | Latest first; turn ID, session ID, UTC start, elapsed ms, route, status, safe category, node timings, model-attempt summaries, known usage, known estimate/completeness and fallbacks. No content fields. |
| Models | Provider/model, attempt/success/failure counts, known input/output tokens, known estimate and completeness; alphabetical provider/model ordering. |
| Routes | Route, turn count, average/p95 latency, error count, known estimate and completeness; alphabetical ordering. |
| Series | Oldest first by completion sequence; turn ID, UTC start, latency ms, cumulative known estimated USD cost within the returned window. Starts at the first retained authorized turn; never label as lifetime cost. |

The snapshot is atomic across completed turns, children and active counters. One bounded global window matches the reference's process-local intent; authorization checks the operator before reading any telemetry. The operator sees all users' retained turns and active counters. Ordinary users see neither this view nor its data; UI visibility is not the authorization boundary. No pagination, reset or export endpoint in this scope.

Route is the actual chosen specialist (`financial`, `agenda`, `faq`), `direct` when the router answers without selecting one, `blocked` for policy rejection before routing, or `unknown` when a failure precedes a decision. Capture the selected route at selection time: current `GraphState.route` is primarily a guardrail control field and must not be treated as the final business route. Missing reason/status information must be emitted explicitly as telemetry by the guardrail; do not infer it from refusal text or changes to `called_agents`.

Tokens are counts reported by providers, not estimated from text. Prefer normalized usage and fall back to provider metadata without double counting. Include reasoning tokens exactly once according to provider semantics. Missing usage is unknown, whereas deterministic rejection with no calls is known zero. Unknown models remain visible and unpriced, never silently free. Version the price catalog with source/date/currency/unit; the resolved catalog and explicit unpriced fallback policy are defined under Q-003. Estimates use full standard input/output rates without cache discounts and are not invoices. Do not copy the HTML's price claims as verified current provider rates.

Cancelled executions count against the SLO as incomplete service delivery. A refusal caused by classifier failure has telemetry status error and guardrail outcome blocked; intentional policy rejection alone is excluded from the error numerator. The original HTTP/chat response remains unchanged. Persistence failures after a successful graph remain covered by existing error logs and are explicitly outside this graph SLO.

## Acceptance scenarios

- **AC-001 — successful financial turn:** a signed-in synthetic user submits a question; exactly one completed turn includes real executed nodes, actual model calls and usage. Calls outside the turn are excluded. Existing content/session/called_agents response remains compatible. FR-001/002/003.
- **AC-002 — rejection and fail-closed distinction:** deterministic injection rejection records zero calls, blocked status and no SLO error; classifier unavailability or invalid classification records an error with a safe reason while retaining the existing refusal behavior. FR-004/007.
- **AC-003 — exceptions, timeout and cancellation:** inject failures before routing, within a model, and during final result validation; cancel an active graph task. Every started turn closes exactly once, partial observations survive, active count returns to zero and original failure behavior is preserved. FR-001/002/004/007, NFR-001.
- **AC-004 — fallback and nested calls:** primary 429 triggers the existing fallback to Qwen; exactly one activation per middleware switch and both observable attempts are attributed correctly. Non-429 does not gain new fallback behavior. Tool loops and guardrail calls remain attached to their correct turn/node. Unknown metadata yields unknown usage/price, not invented zeros. FR-003/004, NFR-001.
- **AC-005 — bounded restartable window:** complete 51 turns with child calls; only 50 and their children remain. Repeated snapshots do not grow retention. Late events are safely discarded. Restart empties telemetry and changes the process start marker without altering business data. FR-005/006, NFR-002.
- **AC-006 — exact aggregates and empty/boundary states:** use deterministic synthetic records for 0, 1, 4 and 20 turns; check rank calculation, 8000 ms and 5% equality, values above either limit, block/error/cancel denominator, window cost and grouped sums. Monitor GET invokes neither provider nor exporter. FR-006/007/008.
- **AC-007 — concurrency and authorization:** interleave different users/sessions on one event loop; verify disjoint attribution and global rows/children/series/counters/aggregates only for an operator, no content/secrets in local telemetry, 401 for no login and 403 for authenticated non-operators. Verify monitor reads do not acquire chat session locks. FR-002/008, NFR-001/002.
- **AC-008 — dashboard:** verify entry/manual/4-second refresh, tab hiding, cleanup, stale/error/401/no-data states, all numbers/tables/charts and labels for known partial estimates and retained-window scope. Chat remains usable. FR-009.
- **AC-009 — independent private tracing:** with export off or failing, local monitoring/chat continue. With tracing enabled on synthetic data and captured SDK transport, inspect root and child calls, matching correlation ID and usage. Assert Q-002 policy across every exported payload before cloud use. Actual cloud inspection is an operator activation check; no cloud account is activated by this change. FR-010, NFR-002.
- **AC-010 — architecture/compatibility:** inspect dependency direction, APP-scoped composition and changed paths; execute applicable checks during separately authorized implementation. Preserve existing chat/auth/agent/agenda-receipt tests and avoid database/configuration edits. NFR-003.

## Open questions and assumptions

| ID | Question | Impact | Resolution |
| --- | --- | --- | --- |
| Q-001 | How is an operator identified by the server? | API authorization, UI audience, snapshot scope. | Resolved: user requested an environment email allowlist. Use `MONITOR_OPERATOR_EMAILS`, a JSON array of email strings, default empty. Trim entries and session email, compare case-insensitively, reject malformed nonempty configuration at startup. Match the authenticated WebSession email only, never a client header/body. No wildcard/domain or Gmail alias folding. Empty list denies all; changes take effect after process restart. Google OAuth already requires email_verified=true. |
| Q-002 | Export metadata only, or allow message/tool content exclusively in a synthetic classroom environment? | LangSmith policy and export configuration. | Resolved by user: metadata only; no message or tool content. Existing anonymization alone is insufficient. |
| Q-003 | What verified standard provider price catalog covers Gemini, GPT-OSS and the configured Qwen model, and how should model aliases map to it? | Complete numerical estimates and price fixtures. | Resolved with explicit partial-cost policy: official Google pricing confirms Gemini 2.5 Flash USD 0.30 input / 2.50 output per million; Groq models page confirms GPT-OSS-120B 0.15 / 0.60. The inspected official Groq page did not establish a Qwen rate: ship it explicitly unpriced until a versioned official rate is verified. Fallback usage remains visible and cost_complete=false. Normalize only the documented Google models/ prefix; other unknown aliases remain unpriced. |
| Q-004 | What explicit exporter integration loads approved LangSmith settings and suppresses all payload content under the selected policy with the installed library versions? | Independent tracing and privacy acceptance. | Resolved design: installed LangSmith 0.11.0 Client supports hide_inputs, hide_outputs, hide_metadata and buffered operation processing; installed LangChainTracer accepts explicit client/project. Construct one injected client and explicit tracer from typed settings, suppress input/output and allowlist only technical metadata. Sanitize errors/events/serialized payloads in outbound operation processing; disable implicit duplicate tracing within the graph scope. Export only graph turns, with root run_id matching local correlation. Validate outgoing payloads with sensitive sentinels before activation. Privacy acceptance is a delivery test, not an unresolved product choice. |

Single process/worker is an explicit scope limit consistent with the in-memory checkpointer. No cross-process totals are promised. Local telemetry does not require a LangSmith account. No real credentials or private environment files were inspected.

Official sources inspected on 2026-10-26: [Google pricing](https://ai.google.dev/gemini-api/docs/pricing), [Groq supported models](https://console.groq.com/docs/models), [LangSmith privacy controls](https://docs.langchain.com/langsmith/mask-inputs-outputs). Qwen remains explicitly unpriced; this is a documented outcome, not permission to change the configured model.

The email allowlist is loaded through typed settings and documented in `.env.example` with placeholders only. No actual operator emails or keys are committed. The authenticated account response adds `can_monitor` so React can show navigation without exposing the allowlist. The monitor endpoint independently enforces access on every request. Tracing defaults off, and absent keys keep export disabled. Existing LANGSMITH names and project choice are preserved.

## Completion criteria

Draft becomes Ready only after Q-001 through Q-004 are resolved and their effects are reflected throughout all three documents. Implementation remains separately gated by the user's explicit code-generation instruction. Delivery requires evidence for every requirement in tasks.md, unchanged business contracts, verified retention/isolation/privacy, and a recorded distinction between deterministic tests and any synthetic live tracing checks.
