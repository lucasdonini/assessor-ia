# [004] Delivery tasks

Specification: [spec.md](spec.md)
Plan: [plan.md](plan.md)
Last updated: 2026-10-27

## Ordered work

- [x] T-001: Inspect the supplied HTML, architecture, relevant source/tests and
  existing SDD conventions; resolve product choices interactively.
  Evidence: decisions and source references in spec.md; documentation only.
- [x] T-002: After explicit implementation/configuration authorization, define typed
  judge/command/result contracts, settings injection and stage-specific rubric version 2.
  Depends on T-001. Evidence: architecture/type checks and reviewed fixtures.
- [x] T-003: Build the bounded asynchronous JEV adapter and decision policy.
  Depends on T-002. Evidence: controlled HTTP success/failure/strict parsing tests.
- [x] T-004: Capture invocation-local trusted input and typed tool evidence with
  minimization, byte budget and concurrency isolation.
  Depends on T-002. Evidence: nested-tool, cross-turn/user/session tests.
- [x] T-005: Enforce financial validation before mutation, explicit BRL on new
  amounts, legacy interpretation and complete-scope balance safeguards. Cover
  add/update/cancel/restore and direct MCP. Add truthful ordered operation outcomes
  and within-turn deduplication.
  Depends on T-003 and T-004. Evidence: service/tool tests and PostgreSQL effects.
- [x] T-006: Wire the final judge into every generated exit and deterministic
  financial/agenda receipt delivery. Eliminate post-graph generated-content
  replacement without changing agenda receipt semantics.
  Depends on T-005. Evidence: graph paths, exact text preservation, no-cycle and
  committed-write/refusal regression tests.
- [x] T-007: Record safe judge/model-call telemetry with old-document compatibility
  and honest usage/cost completeness.
  Depends on T-003 and T-006. Evidence: telemetry/monitor/persistence tests.
- [x] T-008: Run targeted checks and regressions; exercise the actual adapter via
  Postman simulations; run the fixed synthetic Portuguese evaluation with an own
  key; record model/rubric, outcomes, latency and limitations.
  Depends on T-003 through T-007. Evidence: command outputs and per-case report.
- [x] T-009: Update operational/MCP documentation and review evidence; retain
  Implemented only after the real-provider gate passes (now verified). The follow-up user request
  authorizes commits, push and a draft English PR.
  Evidence: README, this record and explicit delivery limitations.

## Requirement traceability

| Requirement | Acceptance | Tasks | Verification location | Result |
| --- | --- | --- | --- | --- |
| FR-001 | AC-001 | T-006 | tests/test_agents | Passed deterministic checks |
| FR-002 | AC-002 | T-003, T-006 | tests/test_infrastructure, tests/test_agents | Passed deterministic checks |
| FR-003 | AC-003 | T-004 | tests/test_tools, tests/test_agents | Passed deterministic checks |
| FR-004 | AC-004 | T-004, T-008 | Evidence fixtures and synthetic model evaluation | Passed contract checks and live gate |
| FR-005 | AC-005 | T-005 | tests/test_services, tests/test_tools | Passed deterministic checks |
| FR-006 | AC-006 | T-005 | Currency/amount unit and PostgreSQL integration tests | Passed deterministic checks |
| FR-007 | AC-007 | T-005, T-006 | Receipt graph and repository integration tests | Passed deterministic checks |
| FR-008 | AC-008 | T-005 | Legacy/mixed-currency balance integration fixtures | Passed deterministic checks |
| FR-009 | AC-009 | T-003, T-005 | HTTP failures, deadline, cancellation and zero-write tests | Passed deterministic checks |
| FR-010 | AC-010 | T-007 | Existing telemetry/monitor test areas | Passed deterministic checks |
| FR-011 | AC-011 | T-006 | tests/test_agents/test_agenda_receipts.py and graph tests | Passed deterministic checks |
| FR-012 | AC-012 | T-005 | tests/test_mcp_server.py | Passed deterministic checks |
| NFR-001 | AC-013 | T-002, T-008 | Typing, architecture, API and DI regressions | Passed deterministic checks |
| NFR-002 | AC-009, AC-014 | T-003, T-008 | Controlled deadlines, call counts and measured latency | Passed; live warm p95 511.6 ms |
| NFR-003 | AC-014 | T-008 | Fixed 24-case Portuguese dataset and results | Passed 24-case live gate; see results |

## Verification record

| Date | Procedure | Result | Evidence / limitation |
| --- | --- | --- | --- |
| 2026-10-27 | Read supplied HTML and inspect graph, composition, guardrails, schemas, services, repository, MCP, DI, telemetry and relevant tests | Completed | Source-based starting state; live model behavior not reproduced. |
| 2026-10-27 | Resolve scope, provider, currency, receipts, legacy treatment and outage behavior through interactive questions | Completed | User choices consolidated in spec.md; JEV supersedes the temporary open-model proposal. |
| 2026-10-27 | Check official TypeSafe API/model documentation | Completed | API contract and version pin documented; no credential used or authenticated call performed. |
| 2026-10-27 | Check local Markdown links, requirement coverage and whitespace | Passed | All local links resolve; all 15 requirements appear in traceability; no trailing whitespace. git diff --check reported no tracked-file issues; new untracked documents were checked separately. |
| 2026-10-27 | `.venv/Scripts/python.exe -m ruff check app tests` and `ruff format --check app tests` | Passed | All checked files clean/formatted; repository pre-commit Ruff hooks also passed. |
| 2026-10-27 | `.venv/Scripts/python.exe -m mypy app` | Passed | 168 source files; no typing issues. |
| 2026-10-27 | `.venv/Scripts/python.exe -m pytest -o addopts= -m "not integration" -q` | Passed | 532 passed, 96 deselected. Includes exact-text, all graph exits, privacy, command checks and receipt delivery. The final timeout trace adjustment also passed all 12 graph-execution cases and MyPy. |
| 2026-10-27 | `.venv/Scripts/python.exe -m pytest -o addopts= -m integration -q --maxfail=3` | Passed | 78 passed, 18 skipped. Optional external simulations and live evaluation were not enabled in this full-suite run. PostgreSQL/MongoDB containers were disposable. |
| 2026-10-27 | Targeted final currency/service/graph and PostgreSQL checks | Passed | 45 focused unit checks and 3 financial database checks passed after the foreign-legacy amount guard/message adjustment. |
| 2026-10-27 | Start Postman CLI 1.76.0 simulation; set JEV_SIMULATION_URL; run `pytest -o addopts= -m integration tests/integration/test_jev_http.py -q` | Passed | 8 passed; real httpx adapter over HTTP. Simulation request log showed all eight paths including 429, 500 and a response arriving after the client deadline. No private key/data used. |
| 2026-10-27 | Check only whether TYPESAFE_API_KEY is configured | Not configured | No own key present. The 24-case live semantic/latency evaluation was not run; no classroom key was read or used. |

## Deferred work and completion

Implementation, deterministic verification and the real-provider gate are
delivered. The feature is Implemented after the confirmation/rubric follow-up. No private
.env, production data, deployed resources or schema migrations were changed.
The new .env.example documents the optional startup key and fail-closed behavior.

The evaluation dataset is [evaluation-cases.json](evaluation-cases.json), with 12
development and 12 held-out cases, balanced by support and command/reply stage.
The opt-in runner is
[the live evaluation test](../../tests/integration/test_jev_evaluation.py).
It records each result and actual model/rubric/latency and enforces the original
gate without treating provider unavailability as a correct refusal.

Reproduce the completed gate with an own key: set RUN_JEV_EVALUATION=1
and run `uv run pytest -m integration tests/integration/test_jev_evaluation.py -s`.
The recorded rubric-2 run passed this gate; repeat it when the rubric or model changes.
This result is limited to the fixed synthetic dataset, not Portuguese quality in general.

Commit sequence: specification; JEV adapter/configuration/telemetry and HTTP
simulation; financial command validation/graph/receipts with regression tests;
evaluation fixtures and delivery documentation. All are authorized by the user.
The draft PR records the live results and the two observed false refusals explicitly.

Deferred deliberately: multi-currency storage/conversion, historical correction,
durable cross-request idempotency, outbox recovery, distributed isolation and
frontend redesign. These are excluded by the agreed scope; they do not silently
weaken the listed pre-write or receipt requirements.

## Confirmation regression follow-up (2026-10-27)

- Fixed the latest-message-only currency check and loss of original source_text.
  Tests cover the reported Sim / 120 / 120 continuation, unrelated intervening
  requests, different amounts/currencies, missing source and the six-message cap.
- Focused service/graph checks: 57 passed. PostgreSQL financial checks: 5 passed,
  including persisted amount and original purchase source after confirmation.
- Live rubric 1: failed the unchanged gate (4/12 supported approved, 0 false
  approvals; warm p95 410.8 ms). All supported commands were refused.
- Live rubric 2: passed (10/12 supported approved, 0/12 unsupported approved;
  warm p95 511.6 ms). Choice/noul threshold remains 0.70. The dataset was unchanged.
- Real TransactionService command validation with JEV and a fake repository:
  both confirmation continuations passed, without private data or actual writes.
- Final unit suite: 546 passed, 100 integration cases deselected. Ruff and MyPy
  passed. Full integration follow-up: 80 passed, 20 skipped (optional simulation/live
  prerequisites absent in that combined run). Live JEV cases passed separately.
- [Per-case live results](evaluation-results.json) retain only synthetic case IDs,
  decisions, model and timings. Opinion attribution and timezone conversion remain
  two observed false refusals. The held_out partition was previously exercised
  with rubric 1; this is a regression set, not an independent accuracy estimate.
