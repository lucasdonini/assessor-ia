# [002] Implementation plan

Specification: [spec.md](spec.md)
Last updated: 2026-10-26
Status: Implemented; authorized by the maintainer on 2026-10-26.

## Verified context

Inspected graph, state, execution result, composition, model definitions, fallback middleware, input/output guardrails, text generator, chat routes, API authentication/dependencies, main application, Dishka graph/services providers, logging, settings, frontend App, existing graph/middleware tests, environment example and SDD conventions. Existing documents can be historical: `context.md` describes older chat/session behavior; source is authoritative for this feature.

## Approach and affected layers

The implementation adds the following files inside existing layer directories without restructuring them.

| Requirements | Existing or proposed path | Responsibility |
| --- | --- | --- |
| FR-001/002/004, NFR-001 | `app/infrastructure/agents/graph.py` | Own turn lifecycle, correlation, selected-route capture and node timing using existing wrapper. Capture final validation errors and cancellation. |
| FR-002/003/005, NFR-001/002 | Proposed `app/application/models/observability.py`, `app/application/ports/observability.py` | Typed immutable observations, recording/snapshot contracts without LangChain, HTTP or infrastructure dependencies. |
| FR-003/005, NFR-001/002 | Proposed `app/infrastructure/observability.py` | Per-application bounded store, context propagation, provider callback adapter, safe normalization and atomic snapshots. Separate per-run correlation from completed retention and remove it on all terminal events. |
| FR-003/004 | `app/infrastructure/agents/_core/middleware.py`, `composition.py`, guardrails and existing Runnable call sites as needed | Emit explicit fallback and guardrail outcomes; propagate callbacks/metadata to nested `ainvoke`, including `LLMTextGenerator`, without changing its string return contract. |
| FR-006/007 | Proposed `app/services/monitor_service.py` | Operator-only global snapshot aggregation, nearest-rank SLO, exact cost calculation, versioned price catalog and grouping. Keep formulas out of API/UI. |
| FR-008 | Proposed `app/api/routes/monitor.py`, `app/api/schemas/monitor.py`; existing dependencies and `routes/__init__.py` | Thin authenticated endpoint with typed schema, registered with other API routes before static mount. FastAPI OpenAPI remains authoritative; do not create a competing collection solely for this document. |
| FR-001–008, NFR-003 | Existing bootstrap provider files/container | APP-scoped collector/store shared between graph and monitor service; inject contracts. Avoid mutable process module singletons and global callback mutation. |
| FR-009 | Proposed `frontend/src/components/Monitor.tsx`, `Monitor.css`, `frontend/src/api/monitor.ts`; existing `App.tsx` | Operator-only navigation and conditional view using current app conventions; CSS/SVG or canvas charts without a new chart dependency. No standalone HTML or Vite entry changes. |
| FR-010 | Infrastructure/composition integration and README | Optional exporter according to Q-002/Q-004, linked by the existing trace ID. Reuse environment names already in `.env.example`; no environment edits in this task. |

## Decisions and tradeoffs

- Keep graph timing distinct from HTTP request timing, matching the reference lifecycle and avoiding a misleading end-to-end availability claim.
- Extend existing timing/logging rather than duplicate instrumentation. Aggregate in a service so HTTP and React remain presentation boundaries.
- Carry explicit turn/run/node metadata through async callbacks. Do not copy reference `threading.local`: concurrent tasks share threads. Test the actual nested LangGraph/LangChain propagation, including inherited context in task creation.
- Record every observable attempt and successful call separately. A fallback activation is emitted where the middleware switches, not inferred because a provider/model differs from Gemini.
- Do not inject extra monitoring fields into conversation state/checkpoints when turn-local telemetry can carry them. Capture guardrail reason explicitly; if any state addition proves necessary, document its reset and checkpoint compatibility before implementing it.
- One atomic snapshot backs all response sections. Check the authenticated verified email against MONITOR_OPERATOR_EMAILS before exposing global telemetry. A process-global 50-turn window bounds memory; only operators can read it.
- Completed history is bounded. Active bookkeeping follows actual active executions and is cleaned on timeout/cancellation; no new queue or admission-control policy is introduced.
- Price configuration is a versioned technical catalog, not a model-selection change. Unknown usage/rates remain explicit. Use verified Gemini/GPT-OSS rates and explicitly unpriced Qwen as resolved in Q-003.
- Optional tracing must satisfy privacy at all exported levels; disabling local content storage alone does not secure cloud traces. Q-004 selects an explicit injected LangSmith client/tracer after installed SDK inspection.

## Data, identity and concurrency

No PostgreSQL/MongoDB/Qdrant writes, migrations or resets for telemetry. Existing business writes remain unchanged. Turn closure and snapshot retention are atomic in the store; no lock is held across provider calls. Closing a turn is idempotent. Ignore terminal duplicate/late events without resurrecting state. Counters and retained records are scoped according to Q-001. Single worker only; deployment restart is a telemetry reset and must be visible through process metadata.

## Errors and observability

Store safe fixed categories for timeout, cancellation, classifier unavailable, classification indeterminate, model failure and invalid graph result. Preserve original errors and existing HTTP translation. Collector/export errors produce sanitized diagnostics through existing LoggerFactory; they must not leak exception messages, recursively instrument themselves or fail a chat. Dashboard fetch failure retains the last good snapshot marked stale. An unavailable exporter never makes `/api/monitor` call it.

## Verification strategy

Deterministic tests cover lifecycle, rank boundaries, exact decimal costs, actual provider metadata shapes, async interleaving, callback propagation, nested loops, eviction, unknown data, privacy and auth. Extend existing graph/fallback tests to preserve business semantics. Use fake run/usage fixtures for aggregation; no paid provider calls are needed for those checks. Frontend tests cover all fetching states, timers, visibility/cleanup and series labels. Verify schema with HTTP contract tests and existing `/docs` generation. Relevant Ruff, MyPy, Pytest, frontend lint/type/tests/build checks run only during authorized implementation. The installed SDK was exercised with captured outbound operations for root/child correlation, usage and privacy. Actual cloud inspection remains an operator activation check; local tests do not establish remote account permissions.

## Delivery and recovery

All specification questions are resolved in spec.md. The maintainer authorized implementation, semantic commits and a draft PR. Backend recording/API, React UI and documentation are separate commits. Existing chat response and business behavior remain compatible. Turning off the exporter leaves local monitoring functional; restart clears telemetry only. The authorized settings/example changes document the email allowlist and optional private tracing. The actual private environment and remote tracing configuration remain untouched.

## Delivery risks

No specification questions remain open. Installed SDK support was inspected statically; privacy suppression and nested callback propagation still require the acceptance tests in AC-009 during authorized implementation. Qwen pricing remains deliberately unknown and visible as incomplete cost, without blocking local monitoring. Trace content must never be exported before the payload-policy tests pass. No live activation or cloud account changes were performed.
