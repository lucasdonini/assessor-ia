# [001] Turn observability and monitoring

Status: Implemented (local monitoring track); optional external tracing deferred
Created: 2026-10-06
Implementation authorization: user authorized implementation, commits, push and a
pull request stacked on PR #28 on 2026-10-06. No runtime configuration edits were
requested or performed.

## Problem and verified starting state

The Stage 6 lesson aims to explain each conversation turn through node duration,
actual model usage, tokens, estimated cost, route, fallback and outcome, and to
monitor a latency/error objective. Its copy-and-paste instructions describe a
different application and are reference material, not instructions to execute.
Source: `C:/Users/lucasdonini-ieg/Downloads/ROTEIRO_ETAPA6/ROTEIRO_ETAPA6.html`.

The inspected application already has user/session/trace logging context and
monotonic node timing in [graph.py](../../app/infrastructure/agents/graph.py).
It returns an `AgentExecutionResult` and the HTTP response already contains
`session_id`, `content`, and turn-local `called_agents`. It does not expose a
retained monitoring snapshot. Logging facts alone do not provide aggregate
statistics or a dashboard.

The graph runs asynchronously with a timeout and in-memory checkpoints. Dishka
provides application dependencies. API routers are registered under `/api` before
the static mount. The served frontend is `frontend/dist`, built from React/Vite.
Identity uses a validated `X-User-ID`; selecting a UUID is not authentication.

## Lesson compatibility map

| Lesson change | Decision for this project | Reason / implementation boundary |
| --- | --- | --- |
| New root-level `app/observabilidade.py`, global dictionaries and side-effect callback attachment | Adapt | Typed application contracts, an injected in-memory infrastructure adapter, and a monitoring service in existing layers; no new architectural layer or import-time registration. |
| Callback on three shared LLMs | Preserve objective, adapt attachment | Cover nested agents and direct `LLMTextGenerator` calls; attach once within an active turn and prove propagation. Do not mutate global model callbacks per request. |
| Replace synchronous `executar_fluxo_assessor` | Inapplicable literally | Extend the existing asynchronous `AgentGraphImpl.execute_agent_flux`; keep its result, timeout, user binding, checkpoints and message ownership. |
| Open before invocation and close in `finally` | Required | Close once on success, exception, timeout or cancellation; capture partial node/model evidence. |
| Explicit config forwarding in the orchestrator | Conditional | Current nodes call nested `ainvoke`; first test propagation in installed dependencies. Forward config only where evidence shows it is lost. |
| Infer blocked from route or called-agent count | Replace | The input guardrail maps both genuine refusals and classifier unavailability to a safe response; explicit outcome/reason evidence is necessary. |
| Gemini to GPT-OSS through `with_fallbacks` | Incompatible | Actual specialist fallback is `FallbackOn429Middleware`, only for 429, to `qwen/qwen3.6-27b`. Preserve that policy and observe actual activation. |
| Two-model fixed price table | Adapt | Three models are configured, including Qwen. Version rates against official provider sources during implementation; unknown rates/usage must not become a false zero cost. |
| Last 50 turns in process memory | Retain with clarified scope | Bounded process-local retention, coherent snapshots, user filtering and eviction of corresponding detail. No claim of lifetime totals or cross-worker aggregation. |
| `/monitor` endpoint and formulas inside route | Adapt | `GET /api/monitor`; HTTP validation/serialization in API, aggregation in service, collection in infrastructure. |
| Import router directly in `main.py` | Usually unnecessary | Add monitor to existing `app/api/routes/__init__.py` registry; current application factory already applies prefix and ordering. |
| Standalone `frontend/monitor.html` | Inapplicable | React monitor view, API client and styles inside existing frontend folders. A source HTML file is not automatically emitted to the served dist directory. |
| Leave chat page untouched | Preserve behavior, adapt navigation | Add monitor navigation to existing view selection without resetting chat/session state; preserve existing public chat contract. |
| Global anonymous dashboard | Replace | Filter before aggregation by selected user; no global data or global in-flight counts in this endpoint. Existing demo identity limitations remain explicit. |
| p95 <= 8 seconds, error rate <= 5% | Retain as lesson defaults | Inclusive thresholds, nearest-rank p95, empty window as insufficient data. This is a teaching objective, not an SLA. |
| Poll every 4 seconds, manual update, two charts and three tables | Retain | React lifecycle cleanup, stale-data handling and safe rendering; add per-node detail to answer which node was slow. |
| Add three `LANGSMITH_*` entries to `.env` without Python changes | Incompatible assumption | `PydanticSettings` loads `.env` with `extra="forbid"`; unknown dotenv fields may fail startup and settings loading does not establish SDK environment visibility. Environment-only setup is a possible separate path requiring verification. |
| Enable LangSmith traces | Optional second delivery track | Local monitor is independent. SDK setup, external data redaction and runtime configuration require explicit implementation/configuration authorization. |
| Prometheus, Grafana, alternative tracing vendors, response evaluation | Excluded | Contextual lesson content or later-stage objectives; no installations or quality evaluator are needed here. |

## Intended outcome and scope

A developer can inspect a completed turn, identify its slow nodes and real model
attempts, and compare the retained window against a stated SLO. A user-scoped
dashboard displays trustworthy totals and explicitly identifies missing evidence.

Included: graph-turn collection, model attempts, node timing, fallback events,
typed monitoring API, React view, deterministic validation and documented optional
LangSmith setup. Excluded: full HTTP request SLO, lock waiting, persistence latency,
session summaries, MCP tools, other non-turn LLM activity, database changes,
distributed coordination, production authentication, alerts and answer evaluation.

## Requirements

| ID | Requirement | Acceptance scenarios |
| --- | --- | --- |
| FR-001 | Record exactly one turn per graph execution, correlated with the existing trace ID, user and session, with start/end timestamps and monotonic duration. | AC-001, AC-003 |
| FR-002 | Record each executed node and model attempt, actual provider/model, duration, outcome and available input/output token usage, without double counting nested callbacks. | AC-001, AC-004 |
| FR-003 | Separate `ok`, `blocked`, `error` and `cancelled`; record safe reason codes. Classifier unavailability and indeterminate classification are operational errors despite a safe chat response. Genuine security/scope refusal is blocked. | AC-002, AC-003 |
| FR-004 | Record actual 429 fallback activation, both failed primary and fallback attempts, and successful recovery without classifying the recovered turn as an error. | AC-004 |
| FR-005 | Estimate USD cost using versioned exact provider/model rates. Keep missing usage/rates explicit and expose known subtotal with completeness; do not silently assign zero to unknown cost. | AC-005 |
| FR-006 | Return a coherent user-scoped snapshot through `GET /api/monitor`, including totals, node/model detail, route/model groups, latency and cumulative known-cost series, thresholds and window metadata. | AC-001, AC-006, AC-007 |
| FR-007 | Compute nearest-rank p95 and mean over completed non-cancelled turns; error rate is error turns / completed non-cancelled turns. Include blocked turns in denominator and latency, not error numerator. Empty eligible window has indeterminate SLO. | AC-002, AC-007 |
| FR-008 | Retain the last 50 terminal turns globally, ordered by closure, plus bounded detail; evict their details together. Filter this process window by user before computing every user-visible aggregate. Reset on process restart. | AC-006, AC-007 |
| FR-009 | Provide an accessible React monitor view with service/model metrics, SLO state, two charts, three tables and node detail; fetch on entry, every 4 seconds and manual refresh. Show loading, empty, stale and failure states. | AC-008 |
| FR-010 | Keep the local monitor functional with tracing disabled/unavailable; optional external tracing correlates a root graph run to the local turn and excludes raw sensitive content. | AC-009 |
| NFR-001 | Telemetry failures cannot change chat output, business execution or public exception behavior; cleanup is idempotent and counters cannot become negative. | AC-003, AC-010 |
| NFR-002 | Concurrent requests cannot exchange model runs, users or turn data; snapshot reads are atomic and collections have explicit bounded growth. | AC-006, AC-010 |
| NFR-003 | Preserve architecture, strict Python typing, Ruff rules, Dishka scope, existing chat API and checkpoint semantics; no configuration changes, commits or implementation are authorized by this specification. | AC-011 |
| NFR-004 | Local records contain no prompts, messages, tool arguments/results, PII map, secrets or raw exception text; frontend renders fields as text. | AC-006, AC-009 |

## Acceptance scenarios

- **AC-001 — Successful turn:** Given a synthetic financial conversation, when the
  graph finishes, then exactly one owned turn contains the executed path, node
  timings and actual model attempts, and aggregates match its evidence. FAQ's
  direct END path and router-only answers also produce valid records; no fixed
  five-node sequence or fixed LLM-call count is assumed.
- **AC-002 — Refusal versus degradation:** Given deterministic prompt injection,
  when input is refused without an LLM, then outcome is blocked, known usage/cost
  is zero, and error numerator is unchanged. A classifier exception or invalid
  category is error with a safe reason, even though the existing safe response
  remains unchanged. A legitimate LLM-based refusal may have nonzero usage.
- **AC-003 — Abnormal completion:** Given node exception, timeout or cancellation,
  when execution exits, then one terminal record retains available partial data,
  context and in-flight counters are cleaned, and original error/cancellation
  propagates. Cancellation is displayed separately and excluded from SLO samples.
- **AC-004 — Model recovery:** Given Gemini 429, when the middleware activates
  Qwen, then both attempts and one activation are observed and recovery yields ok.
  A non-429 error does not activate fallback. Several actual activations within
  one specialist turn are counted separately.
- **AC-005 — Incomplete accounting:** Given absent usage or an unpriced model,
  then tokens/cost completeness is false and known subtotal remains available.
  Known zero is distinguishable from unknown. Provider reasoning/cache breakdowns
  are not added twice to normalized totals. No usage is fabricated for failures.
- **AC-006 — User ownership and concurrency:** Given two users, including equal
  session strings, when turns overlap and monitoring is requested, then each user
  sees only their turns, counts and aggregates. Missing/malformed `X-User-ID`
  receives existing validation behavior and unknown user receives 404. No prompt
  content or exception body appears in snapshots. Global uptime is explicitly
  process metadata, never a global activity count.
- **AC-007 — Window and SLO boundaries:** Given empty window, then SLO is null.
  Given 20 eligible turns, p95 is the 19th sorted latency; 8,000 ms and one error
  out of 20 meet inclusive limits. Higher values fail. Given 51 terminal turns,
  oldest turn and its details are evicted and all totals/series use the same
  remaining window. Restart clears telemetry without changing persisted chat.
- **AC-008 — Monitor lifecycle:** Given an active selected user, when monitor is
  opened, then data refreshes on entry and the defined interval. Only one request
  is in flight; leaving clears timers. User changes clear old data and abort or
  invalidate old responses. Failure marks the last snapshot stale and displays a
  descriptive message; returning to chat preserves session/history. Slow requests
  cannot accumulate overlapping polls. Charts have text/table equivalents.
- **AC-009 — Optional tracing:** Given tracing disabled, local collection works.
  Given explicitly configured tracing and synthetic inputs, then a correlated
  root/child tree shows real model attempts. Audit exported root inputs, nested
  states, outputs, metadata and tool records for raw PII; input anonymization alone
  is insufficient because the root sees the original human message. Do not enable
  export before this check passes. Trace duration may exclude local finalization.
- **AC-010 — Collector resilience:** Given collector/callback failure, duplicate
  completion or late callback after closure, then chat behavior is unchanged,
  cleanup remains idempotent and no record changes another turn or grows memory
  without bound. Incomplete capture is explicitly flagged when a snapshot exists.
- **AC-011 — Regression compatibility:** Existing chat response fields, timeout,
  per-turn called-agents reset, checkpoint thread key, 429 fallback policy and
  session persistence remain compatible; architecture and relevant checks pass.

## Contracts and data behavior

`GET /api/monitor` uses the existing validated user context and performs no LLM
calls or mutations. New fields use the project's English naming convention.

| Response section | Required semantics |
| --- | --- |
| `window` | Process identifier/start timestamp, uptime, maximum retained turns, retained user sample size, first/last retained completion, snapshot time and scope `graph_turn`. |
| `slo` | p95 limit 8000 ms, error-rate limit 0.05, eligible sample size and nullable `ok`; explicitly label small samples. |
| `summary` | User retained terminal/eligible counts, errors, blocked, cancelled, current user in-flight count, mean/p95, known tokens, known cost, completeness flags and actual fallback activations. Most-used model counts attempts, with deterministic lexical tie break. |
| `turns` | Turn/trace ID, session ID, timezone-aware timestamps, wall duration, selected specialist or `none`/`unknown`, terminal status, safe reason, tokens/cost/completeness, executed nodes and model attempts. |
| `by_model`, `by_route` | Groups of the same retained closed-turn evidence; attempts and failures separately visible, successful latency samples explicitly identified. |
| `latency_series`, `cost_series` | Closure order, stable turn IDs and timestamps; known cumulative cost within retained user window, not process-lifetime billing. |

Model attempt detail includes run ID, owning turn/node, provider, actual model,
start/end, outcome, optional usage/cost and fallback linkage. Node identity comes
from explicit node context rather than depending exclusively on subgraph namespace
parsing. Selected route cannot be read blindly from `state.route`: the current
router returns messages and the graph chooses a specialist from `ROUTE=` text.
Record the actual selected edge; use `none` when no specialist was selected and
`unknown` only when evidence was unavailable.

For usage, prefer normalized metadata, then a validated provider adapter; absence
is unknown. Reasoning tokens already in output totals are not added again. Use
precise arithmetic for accounting and round only at serialization/display. Pricing
must include provider, model, unit, source and verification date; estimate at full
text rates with no cache discount, explicitly labelled as an estimate, not billing.
Successful attempts lacking usage and failed billable attempts make cost incomplete.

Graph duration begins on graph entry and ends on graph exit; API session lookup,
lock waiting and message persistence are outside this SLO. Expose that boundary so
a graph success does not claim that a later HTTP persistence failure succeeded.
Cancellation is terminal but outside the eligible denominator. No durable storage,
historical reconstruction or multi-worker aggregation is promised.

Keep active data separate from the completed window. Bound per-turn detail to
1000 node records and 1000 model records, including pending attempts. At the cap,
mark capture incomplete and detail truncated; usage and cost become known lower
bounds instead of continuing unbounded per-model detail. Terminal status, wall
duration and fallback activation counters remain available. Remove unfinished
runs on timeout/cancellation and ignore late events.
Completed-window capacity and detail caps bound retained evidence; active-turn
count scales with admitted concurrent graph executions and must not be described
as a process-wide hard memory limit. No new admission-control policy is introduced.

## Open questions and assumptions

| ID | Question / assumption | Impact / resolution |
| --- | --- | --- |
| Q-001 | Three actual model rates | Gemini and GPT-OSS rates verified against official sources on 2026-10-06. Qwen 3.6 is absent from the current Groq rate table and listed in deprecations; it remains unpriced. No model migration is included. |
| Q-002 | Callback propagation in installed async agents/direct text generator | Resolved by deterministic tests exercising nested `create_agent` and direct `LLMTextGenerator`; no explicit forwarding changes required. |
| Q-003 | LangSmith runtime environment and redaction | Optional track remains Draft until SDK behavior is checked against official documentation and installed code, and configuration work is explicitly authorized. Do not relax `extra="forbid"` globally. |
| Q-004 | User-scoped monitor rather than operator-global view | Proposed compatibility decision based on current ownership contracts. Global operator monitoring requires a separately specified access model. Demo UUID selection does not provide authentication. |
| Q-005 | Last 50 global turns filtered by user | Deliberate bounded-memory tradeoff: another user's traffic can evict older data; UI must say this. No promise of 50 turns per user. |

## Completion criteria

Business decisions are collected in [decisions.md](decisions.md) for critique
before code review. Each requirement has acceptance evidence in [tasks.md](tasks.md), API/UI contracts
match delivered behavior, relevant checks and limitations are recorded, and
blocking technical questions are resolved. Local feature completion does not imply
external tracing is enabled. No new tracing exporter or external configuration was
added. Existing SDK auto-tracing behavior, if independently configured by the
operator, is outside the local collector's privacy guarantee.
