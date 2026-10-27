# [004] Delivery tasks

Specification: [spec.md](spec.md)
Plan: [plan.md](plan.md)
Last updated: 2026-10-27

## Ordered work

- [x] T-001: Inspect the supplied HTML, architecture, relevant source/tests and
  existing SDD conventions; resolve product choices interactively.
  Evidence: decisions and source references in spec.md; documentation only.
- [ ] T-002: After explicit implementation/configuration authorization, define typed
  judge/command/result contracts, settings injection and rubric version 1.
  Depends on T-001. Evidence: architecture/type checks and reviewed fixtures.
- [ ] T-003: Build the bounded asynchronous JEV adapter and decision policy.
  Depends on T-002. Evidence: controlled HTTP success/failure/strict parsing tests.
- [ ] T-004: Capture invocation-local trusted input and typed tool evidence with
  minimization, byte budget and concurrency isolation.
  Depends on T-002. Evidence: nested-tool, cross-turn/user/session tests.
- [ ] T-005: Enforce financial validation before mutation, explicit BRL on new
  amounts, legacy interpretation and complete-scope balance safeguards. Cover
  add/update/cancel/restore and direct MCP. Add truthful ordered operation outcomes
  and within-turn deduplication.
  Depends on T-003 and T-004. Evidence: service/tool tests and PostgreSQL effects.
- [ ] T-006: Wire the final judge into every generated exit and deterministic
  financial/agenda receipt delivery. Eliminate post-graph generated-content
  replacement without changing agenda receipt semantics.
  Depends on T-005. Evidence: graph paths, exact text preservation, no-cycle and
  committed-write/refusal regression tests.
- [ ] T-007: Record safe judge/model-call telemetry with old-document compatibility
  and honest usage/cost completeness.
  Depends on T-003 and T-006. Evidence: telemetry/monitor/persistence tests.
- [ ] T-008: Run targeted checks and regressions; exercise the actual adapter via
  Postman simulations; run the fixed synthetic Portuguese evaluation with an own
  key; record model/rubric, outcomes, latency and limitations.
  Depends on T-003 through T-007. Evidence: command outputs and per-case report.
- [ ] T-009: Update operational/MCP documentation and completion evidence; mark
  Implemented only after all gates pass. No commit/push without a separate request.
  Depends on T-008. Evidence: requirement traceability and reviewed final diff.

## Requirement traceability

| Requirement | Acceptance | Tasks | Verification location | Result |
| --- | --- | --- | --- | --- |
| FR-001 | AC-001 | T-006 | tests/test_agents | Not run |
| FR-002 | AC-002 | T-003, T-006 | tests/test_infrastructure, tests/test_agents | Not run |
| FR-003 | AC-003 | T-004 | tests/test_tools, tests/test_agents | Not run |
| FR-004 | AC-004 | T-004, T-008 | Evidence fixtures and synthetic model evaluation | Not run |
| FR-005 | AC-005 | T-005 | tests/test_services, tests/test_tools | Not run |
| FR-006 | AC-006 | T-005 | Currency/amount unit and PostgreSQL integration tests | Not run |
| FR-007 | AC-007 | T-005, T-006 | Receipt graph and repository integration tests | Not run |
| FR-008 | AC-008 | T-005 | Legacy/mixed-currency balance integration fixtures | Not run |
| FR-009 | AC-009 | T-003, T-005 | HTTP failures, deadline, cancellation and zero-write tests | Not run |
| FR-010 | AC-010 | T-007 | Existing telemetry/monitor test areas | Not run |
| FR-011 | AC-011 | T-006 | tests/test_agents/test_agenda_receipts.py and graph tests | Not run |
| FR-012 | AC-012 | T-005 | tests/test_mcp_server.py | Not run |
| NFR-001 | AC-013 | T-002, T-008 | Typing, architecture, API and DI regressions | Not run |
| NFR-002 | AC-009, AC-014 | T-003, T-008 | Controlled deadlines, call counts and measured latency | Not run |
| NFR-003 | AC-014 | T-008 | Fixed 24-case Portuguese dataset and results | Not run |

## Verification record

| Date | Procedure | Result | Evidence / limitation |
| --- | --- | --- | --- |
| 2026-10-27 | Read supplied HTML and inspect graph, composition, guardrails, schemas, services, repository, MCP, DI, telemetry and relevant tests | Completed | Source-based starting state; live model behavior not reproduced. |
| 2026-10-27 | Resolve scope, provider, currency, receipts, legacy treatment and outage behavior through interactive questions | Completed | User choices consolidated in spec.md; JEV supersedes the temporary open-model proposal. |
| 2026-10-27 | Check official TypeSafe API/model documentation | Completed | API contract and version pin documented; no credential used or authenticated call performed. |
| 2026-10-27 | Check local Markdown links, requirement coverage and whitespace | Passed | All local links resolve; all 15 requirements appear in traceability; no trailing whitespace. git diff --check reported no tracked-file issues; new untracked documents were checked separately. |
| 2026-10-27 | Runtime tests, Postman simulation and live JEV evaluation | Not run | Documentation-only task; implementation and runtime configuration unchanged. |

## Deferred work and completion

Only T-001 and specification authoring are complete. No application code,
configuration, environment values, database rows or external resources were
modified. No commits or pushes were made.

Deferred deliberately: multi-currency storage/conversion, historical correction,
durable cross-request idempotency, outbox recovery, distributed isolation and
frontend redesign. These are excluded by the agreed scope; they do not silently
weaken the listed pre-write or receipt requirements.
