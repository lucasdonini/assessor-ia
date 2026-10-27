# [004] Implementation plan

Specification: [spec.md](spec.md)
Last updated: 2026-10-27

## Approach and affected layers

Preserve the repository layout and dependency direction. Add narrowly scoped files
inside existing directories; do not relocate modules or introduce a new service.
No runtime work is authorized by this plan.

| Requirements | Existing area | Planned responsibility |
| --- | --- | --- |
| FR-002, FR-005, FR-009 | app/application/models and app/application/ports | Typed judgment input/result and evidence-validator protocol; typed validated financial command and operation result contracts. No LangGraph/httpx/vendor imports in application contracts. |
| FR-002, FR-009, NFR-002 | app/infrastructure | Asynchronous httpx JEV adapter, strict response parsing, bounded deadline, versioned rubric and fixed safe message. Reuse one APP-scoped client with managed shutdown. |
| FR-003, FR-004 | app/infrastructure/agents/_core and existing tool base | Invocation-local evidence collector using a scoped ContextVar, reset in finally; collect typed outcomes at the execution boundary rather than scraping full checkpoint history. Record tool arguments as proposals, not successful effects. |
| FR-001, FR-011 | graph.py, composition.py, _core/state.py, guardrails | Inject an AgentNode-compatible evidence_judge; reroute FAQ and direct router answers; normal generated path follows output_guardrail then judge then END. Keep blocked input terminal. Final judge handles deterministic receipts without a provider call. Remove redundant post-graph content substitution after proving receipt parity. |
| FR-005 to FR-008, FR-012 | app/services/transaction_service.py and application contracts | Centralize command validation and currency rules before mutation. Require a typed validated command at the write boundary; do not allow an unvalidated raw transaction to bypass it. Reuse existing ownership, ambiguity and not-found errors. |
| FR-005 to FR-008 | existing financial tools, schemas, repository protocol/adapter | Pass trusted evidence, normalize proposed action, obtain pre-write approval, execute once, record actual outcome. Preserve source text provenance. Read complete balance scope for legacy currency checks. No persisted schema change. |
| FR-007, FR-011 | existing output guardrail and receipt helpers | Extend the agenda pattern to financial operations. Fixed receipts take precedence over generated text; no post-commit judge dependency or generative commentary. |
| FR-012 | app/mcp_server.py | Require explicit operation evidence for write tools; bind invocation-local context for direct MCP execution; share service validation. Keep read contracts and confirmation instructions. |
| FR-010 | application observability models, infrastructure telemetry, monitor service | Add optional judgment metadata with backward-compatible defaults and manual HTTP model-call observations. Existing LangChain callbacks do not automatically observe httpx. Preserve historical Mongo telemetry loading. |
| NFR-001 | bootstrap providers, infrastructure settings/config | Inject validator, configuration, HTTP client and receipt context through Dishka. Document proposed setting/example edits; obtain configuration-change authorization before making them. |

## Decisions and implementation sequence

1. Establish typed contracts, rubric version 1 and deterministic fixtures first.
2. Deliver the adapter and exact decision table with a controlled HTTP transport.
3. Capture evidence at tool execution, including router history searches and nested
   agent tools. Use unique invocation IDs so repeated identical valid reads are
   distinguishable. Do not persist the collector in checkpoints or telemetry.
4. Deliver financial pre-write validation and receipt results before wiring the
   final judge, so the original write/refusal bug is not introduced temporarily.
5. Wire all generated exits and receipt paths, then telemetry and documentation.
6. Run targeted tests, regressions and a small frozen model evaluation.

Prefer two bounded judgment stages over staging database transactions until after
text generation. Pre-write checking protects proposed mutations; final checking
protects generated statements. Deterministic receipts report confirmed side
effects without gambling on a second model call after commit. This adapts the
lesson's outcome rather than copying its code or recreating its known defect.

No multi-provider abstraction beyond one application port, automatic retries,
message regeneration loops, multi-currency support, queue or distributed unit of
work is needed. The class exercise comparing judge-before/after compliance becomes
a deterministic regression case rather than an alternate runtime mode.

## Evidence and financial validation details

The collector receives a trusted request envelope from graph execution or the MCP
entry point and per-tool typed results from the shared tool boundary. Services
receive explicit typed command evidence, avoiding application dependencies on
ContextVar or LangChain. AgentTool owns context plumbing only.

Use current original human input plus bounded previous human clarification
messages. Filter by user/session on the server. Never count prior tools as fresh
database evidence. A quoted untrusted instruction inside source_text remains data.
For pre-write checks, normalize the requested action and fields into short facts;
the rubric asks whether the user requested that operation with those facts. This
does not make the judge an authorization mechanism: ownership stays deterministic.

Currency parsing is conservative: recognize the explicit BRL markers in spec.md
and foreign indicators such as USD/dollar/dólar, EUR/euro, US$ and €; an isolated
$ or conflicting markers is ambiguous. Unknown/unsupported wording triggers
clarification. Test decimal separators and amounts rather than accepting any
number in a sentence. For legacy rows, lack of a foreign indication defaults to
BRL by the user's decision. This heuristic cannot reconstruct all historical
currency changes and must be documented as such.

Use repository reads covering the entire requested balance scope to detect foreign
legacy records before presenting a BRL total. Do not change repository-wide date,
timezone or cancellation semantics as incidental cleanup. Do not relabel mixed
data as a total simply because the SQL sum is available.

Within an invocation, retain executed-command fingerprints and ordered outcomes.
Repeated identical proposed writes return the previous outcome rather than
executing again. Different commands execute sequentially; after the first failed
validation/operation, subsequent writes are not attempted. Read-after-write may
proceed, but only deterministic operation outcomes are delivered for that turn.

## JEV adapter and error behavior

One POST carries both choice and noul questions, using jev-1.14.0 and threshold
0.70. Use response validation that rejects bools/numeric strings, nonfinite or
out-of-range scores and missing/wrong question types. Decision parsing does not
require usage data to be present. Record unknown usage/cost honestly.

The 5-second request budget covers connection, pool, write and read time together;
an outer asynchronous deadline bounds the entire HTTP attempt. It remains inside
the existing graph timeout; the earlier deadline wins. Direct MCP requests use
the same per-validation bound. Do not catch cancellation as ordinary unavailability.

Missing configuration, unsafe/oversized input, vendor failures and invalid
responses produce stable internal reason codes, with safe public wording. Do not
include raw response bodies or exceptions in logs. No JEV call is necessary for a
confirmed receipt, a deterministic clarification or a rejected command template.

Data minimization is required at this new external boundary. Reuse the existing
PII rules where applicable, adding a consistent mapping across all input fields;
do not mistake public FAQ numbers for private contacts. The decision text remains
unchanged on approval; redaction applies to the outbound judgment copy. No private
payloads enter traces. Never send real records during automated/live evaluation.

## Observability and compatibility

Add optional judgment metadata with stage command/reply, decision/reason, score,
resolved model and latency, defaulting to empty on old telemetry documents. Record
actual HTTP calls as provider typesafe without fabricating LangChain callbacks or
usage. A supported HTTP response rejected for factual support is a successful
provider call and a refused judgment, not a transport failure. Use turn status
blocked for factual refusal and error for validator unavailability; preserve the
route and confirmed receipt outcome. A turn with a confirmed receipt is not
classified as wholly refused because a later operation failed; retain per-operation
reasons in safe metadata. Keep existing agenda outcome semantics.

Do not hard-code a new vendor price from the HTML. Until a verified catalog entry
is intentionally added, show JEV as unpriced/incomplete using existing monitor
behavior. No new dashboard components or public chat fields are required.

## Verification strategy

| Area | Planned verification | Environment |
| --- | --- | --- |
| Decision rule and HTTP | 0.70 boundary; strict malformed schema/numbers; 401/429/5xx; timeout/cancel; no retries; one request contains both questions | Unit tests with httpx controlled transport |
| Evidence provenance | Two users, two simultaneous sessions, subsequent turn, nested tools, argument-only proposal, empty/error, bounded prior clarification, byte cap and PII markers | Unit/graph tests |
| Financial guards | Zero mutation on foreign/missing/invented amount or failed JEV; correct reference/ownership; updates without amount; MCP parity | Service/tool tests |
| Actual effects | BRL add/update/cancel/restore; foreign row untouched; deterministic receipts; sequential partial success; duplicate within a turn; uncertain acknowledgment | Existing PostgreSQL integration fixtures |
| Graph exits | financial, agenda, FAQ, direct router, blocked input; no cycle; no rewrite or replacement after final judgment | tests/test_agents |
| Agenda preservation | Existing local/Google partial failure receipt checks plus graph-level delivery | Existing agenda receipt/service tests |
| Telemetry | Old document compatibility, safe metadata, manual model-call accounting, missing usage/unpriced behavior | Existing observability/telemetry/monitor tests |
| Boundary checks | Ruff, format, MyPy, relevant unit suite, then integration suite if Docker available | Existing Python 3.14 environment |
| External provider path | Run real application adapter against saved JEV failure/success simulations | Postman simulation, synthetic inputs only |
| Model semantics | Frozen evaluation described below | Explicit live evaluation with synthetic evidence |

Do not run the make check target for read-only verification because it formats and
fixes files. During implementation use uv run ruff check ., uv run ruff format
--check ., uv run mypy app and uv run pytest, with focused tests first. Run relevant
integration cases explicitly with the integration marker and record unavailable
Docker as a limitation. Frontend build/tests are only needed if frontend changes
become necessary. During this documentation-only task, check files/links and diff
whitespace; runtime suites cannot validate an unimplemented feature.

### Model evaluation gate

Create 24 synthetic Portuguese cases before tuning: 12 supported and 12 unsupported,
split equally between command validation and reply validation. Include the HTML's
Zara, missing price, currency swap, empty Ferrari/agenda/history, public FAQ number,
stale FAQ, arithmetic, timezone conversion, opinion attribution and tool-error
cases. Keep six cases per class/stage split where applicable; no private data.

Use 12 cases for rubric development and 12 held-out cases, balanced by support and
stage. Gate: zero false approvals across the 12 unsupported cases, at least 10/12
supported cases approved, and no false approval on held-out cases. Additionally,
all deterministic currency/value checks must pass regardless of JEV output.
Record per-case outcomes, threshold, rubric version, resolved model and warm/cold
latency. A small gate is regression evidence, not a statistical reliability claim.

Warm p95 added latency target is <=2 seconds per validation on the evaluation set;
the hard deadline is 5 seconds. Do not assume vendor latency. Failure of semantic
or latency gates blocks marking the feature Implemented; adjust the rubric or
document a proposed requirement change for user review, without silently lowering
the acceptance criteria.

## Delivery, prerequisites and recovery

An explicit code-generation request and authorization for the listed configuration
edits are required before implementation. A separately supplied own JEV key and
network access are required for live evaluation. No paid resource provisioning,
publishing or commits are part of this task.

Roll out contracts/adapter, financial validation/receipts, graph integration and
observability in that order. No migration or data reset. Existing records remain.
If JEV fails, retain the specified safe behavior rather than disabling checks.
Code rollback must not silently re-enable unsafe writes; keep financial writes
unavailable until the validated path is restored. No automatic data compensation.

## Risks and limits

- Model errors remain possible, particularly Portuguese numbers, negation and
  opinion attribution. Deterministic amount/currency rules and frozen evaluation
  mitigate them; no judge guarantees truth.
- Existing records may contain wrong numbers/currencies that source_text cannot
  reconstruct. The approved legacy BRL assumption preserves compatibility, not
  historical correctness. No cleanup is authorized.
- Independent repository commits, chat storage and HTTP delivery leave a crash
  window; durable idempotency/outbox recovery is deferred explicitly.
- Cross-session writes retain current last-writer behavior; prevalidation does
  not establish distributed isolation or reserve a target.
- MCP operation evidence is a caller assertion, not authenticated proof of the
  human's wording. Existing confirmation and local-user trust remain.
- Live access and evaluation are unverified. Orbit discovery was attempted during
  research but its hostname did not resolve; official TypeSafe documentation was
  used for the contract. No Postman workspace was initialized or published.

These are explicit operating limitations and delivery prerequisites; no unresolved
design choice remains.
