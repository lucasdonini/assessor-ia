# [001] Implementation plan

Specification: [spec.md](spec.md)
Status: Local track delivered; user authorized implementation and stacked PR

## Boundaries and file map

Add files inside existing folders only; do not move modules or create a new layer.
Names below are proposed, not generated implementation.

| Location | Responsibility / requirements |
| --- | --- |
| `app/application/models/observability.py` | Typed immutable turn, node, attempt, outcome and snapshot records; FR-001 through FR-008. |
| `app/application/ports/observability.py` | Collection and snapshot protocols without LangChain/FastAPI imports; NFR-003. |
| `app/infrastructure/observability.py` | In-memory bounded store, task-local context, callback adapter, pricing normalization and atomic snapshots; FR-001, FR-002, FR-005, FR-008, NFR-001, NFR-002, NFR-004. |
| `app/services/monitoring_service.py` | User filtering and aggregation, nearest-rank p95, error denominator, completeness and series; FR-006, FR-007. |
| `app/bootstrap/providers/agent_graph.py`, `services.py`, existing composition | App-scoped collector and DI wiring to graph, monitoring service and model adapters; no global import-time callback mutation. |
| `app/infrastructure/agents/graph.py` | Reuse generated trace ID; open/close graph turn, reuse timed-node wrapper, capture selected edge and partial execution; FR-001 through FR-003. |
| `app/infrastructure/agents/_core/middleware.py` | Observe actual 429 activation without changing recovery conditions; FR-004. |
| `app/infrastructure/agents/guardrails/input_guardrail.py` | Emit explicit refusal/degradation evidence while keeping current public responses; FR-003. |
| `app/infrastructure/text_generator.py`, nested agent nodes as needed | Only add propagation where the spike proves necessary; include direct guardrail model calls. |
| `app/api/schemas/monitor.py`, `routes/monitor.py`, `dependencies.py`, `routes/__init__.py` | Typed serialization, validated user and route registry; FR-006. Existing `main.py` prefix/mount needs no assumed change. |
| `frontend/src/api/monitor.ts`, `components/Monitor.tsx`, `components/Monitor.css`, `App.tsx` | Typed client, monitor view, polling and existing navigation; FR-009. Preserve mounted chat state or lift state before conditional navigation. |
| Existing test folders and frontend colocated tests | Contract, isolation, boundary, concurrency and UI evidence. |

## Delivery order and decisions

1. Prove async callback propagation, parent/node association, model naming and usage
   shapes using installed dependencies and synthetic mocks. Check direct
   `LLMTextGenerator`, nested agents, middleware fallback and timeout cleanup.
2. Define typed protocols and immutable records; implement one app-scoped store.
   Task-local context binds the owning turn/node; explicit run IDs bind attempts.
   Protect atomic store mutations/snapshots; never hold a lock across await/network.
3. Instrument existing graph lifecycle and timing wrapper. Emit safe classification
   evidence and actual selected edge. Preserve trace/logging and checkpoint behavior.
4. Observe fallback activation in its existing middleware, accounting for failed
   primary attempts. Verify official provider prices; retain unknown completeness
   when evidence is missing. No model substitutions.
5. Deliver monitoring aggregation/service and `/api/monitor` through DI. Read one
   snapshot, filter first, calculate all sections from identical closed evidence.
6. Add React view with text/table alternatives for charts. Keep chat/session state
   alive across navigation. Abort stale requests and clean polling on unmount/user
   change; a completed request schedules the next poll to prevent overlap.
7. Validate synthetic outcomes and existing regressions, then document observed
   boundaries and limitations. Implementation and Git operations were explicitly
   authorized by the user on 2026-10-06.
8. Optional: after separate authorization for configuration, verify LangSmith SDK
   setup and export redaction. Prefer externally supplied process environment if
   viable. If dotenv-backed settings are needed, specify narrowly typed settings
   and explicit SDK wiring; no blanket acceptance of unknown dotenv fields.

## Verification strategy

Backend: collector/store unit tests, exact aggregation fixtures, fallback and
guardrail failure tests, API header/isolation tests, graph timeout/cancellation
tests and architecture checks. Check Ruff/format/MyPy using repository commands
and run affected existing suites. Avoid Docker integration checks unless a runtime
change reaches persistence contracts; no migrations are planned.

Frontend: Vitest/Testing Library fake timers and deferred responses for polling,
user switching, stale results, safe text rendering and session preservation;
existing chat/profile tests, lint, type checking and production build. Confirm
`/api/monitor` is JSON through both Vite proxy and built FastAPI serving.

Live model smoke tests are supplementary and use synthetic content; record actual
model identifiers, provider metadata and limitations. A live 429 need not be
provoked: deterministic middleware tests verify the trigger. Local exact cost
tests use fixture rates, not mutable public prices. LangSmith smoke validation is
optional and must not export private data.

## Recovery and risks

The feature introduces no durable data. Collector failures preserve existing chat
behavior and emit safe diagnostics; external tracing is independently disableable.
Do not change `.env`, deployment files, dependency configuration or credentials
without specific authorization. Commits and a stacked PR are authorized; deployment
and external tracing activation are not part of this delivery.

Primary risks: callback propagation, captured classifier errors, root trace PII,
unknown Qwen pricing/usage, late callbacks, snapshot races and React unmounts
resetting chat state. Acceptance scenarios explicitly cover these. Memory and SLO
are process-local; the feature is not a production reliability stack.
