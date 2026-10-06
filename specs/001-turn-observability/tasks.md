# [001] Delivery tasks

Specification: [spec.md](spec.md)
Plan: [plan.md](plan.md)
Last updated: 2026-10-06

## Ordered work

- [x] T-001: Verify callback propagation and usage/model shapes in installed code;
  resolve Q-002 with deterministic nested/direct/fallback/cancellation evidence.
- [x] T-002: Define typed records/ports and injected bounded store, context and
  atomic snapshots. Depends on T-001.
- [x] T-003: Instrument graph lifecycle/nodes/selected edge and guardrail outcome
  reasons without changing chat behavior. Depends on T-002.
- [x] T-004: Observe 429 fallback and implement complete/partial usage accounting;
  verify exact provider/model pricing with dated primary sources. Depends on T-003.
- [x] T-005: Implement user-scoped aggregation, schemas, DI and API registry;
  verify thresholds, empty window, eviction and ownership. Depends on T-004.
- [x] T-006: Implement React API client/view/navigation, safe rendering, polling
  lifecycle, charts and node detail; preserve chat state. Depends on T-005.
- [x] T-007: Run relevant regressions and static checks; update contracts,
  limitations and evidence; review all requirements. Depends on T-006.
- [ ] T-008: Optional separately authorized LangSmith configuration, SDK/redaction
  validation and correlated synthetic trace; resolve Q-003. Depends on T-007.

Local implementation and commits were authorized by the user. Completed tasks
have deterministic evidence below. T-008 remains deferred; no external trace was
enabled or validated.

## Requirement traceability

| Requirement | Scenario | Task | Verification location / procedure | Result |
| --- | --- | --- | --- | --- |
| FR-001 | AC-001, AC-003 | T-003 | Graph tests and collector lifecycle tests | Passed (local track) |
| FR-002 | AC-001, AC-004 | T-001, T-003, T-004 | Nested/direct callback and graph node fixtures | Passed (local track) |
| FR-003 | AC-002, AC-003 | T-003 | Guardrail, graph timeout and cancellation tests | Passed (local track) |
| FR-004 | AC-004 | T-004 | Middleware 429/non-429/multiple activation tests | Passed (local track) |
| FR-005 | AC-005 | T-004 | Usage normalization and pricing fixture tests | Passed (local track) |
| FR-006 | AC-001, AC-006, AC-007 | T-005 | Monitor API and service tests | Passed (local track) |
| FR-007 | AC-002, AC-007 | T-005 | Exact p95/denominator/threshold fixtures | Passed (local track) |
| FR-008 | AC-006, AC-007 | T-002, T-005 | Eviction, restart and coherent snapshot tests | Passed (local track) |
| FR-009 | AC-008 | T-006 | React fake timer, switching and chat preservation tests | Passed (local track) |
| FR-010 | AC-009 | T-007, T-008 | Local collection tests without an exporter | Local independence passed; external export deferred |
| NFR-001 | AC-003, AC-010 | T-002, T-003 | Failure injection and duplicate cleanup tests | Passed (local track) |
| NFR-002 | AC-006, AC-010 | T-002, T-005 | Concurrent users and late callback fixtures | Passed (local track) |
| NFR-003 | AC-011 | T-007 | Architecture, existing regressions, Ruff/MyPy/frontend checks | Passed (local track) |
| NFR-004 | AC-006, AC-009 | T-005, T-006, T-008 | Content-free snapshot assertions and React text rendering | Local privacy passed; external export audit deferred |

## Verification record

| Date | Procedure | Result / limitation |
| --- | --- | --- |
| 2026-10-06 | Read lesson HTML and relevant graph, LLM, middleware, guardrail, API, DI, logging, settings and frontend sources | Compatibility map grounded in source inspection; no live provider or SDK behavior verified. |
| 2026-10-06 | `.venv/Scripts/python.exe -m pytest -q` | Full non-integration suite passed; existing dependency deprecation and Qdrant warnings. |
| 2026-10-06 | Targeted graph, collector, service, API and architecture tests after final refinements | 23 tests passed, including nested create_agent/direct generator propagation, late callbacks and graph timeout/cancellation. |
| 2026-10-06 | `.venv/Scripts/ruff.exe check .` and `ruff.exe format --check .` | Passed. |
| 2026-10-06 | `.venv/Scripts/python.exe -m mypy .` | Passed for 137 source files. |
| 2026-10-06 | `npm test` in frontend | 55 tests passed across 8 files; polling, stale responses, safe rendering and chat continuity included. |
| 2026-10-06 | `npm run lint` and `npm run build` in frontend | Passed; production build includes TypeScript type checking. |
| 2026-10-06 | Documentation links, requirement/scenario/task coverage and `git diff --check` | Reviewed. |

Tests were run outside the Windows sandbox after sandboxed async tests stalled.
The standard frontend lint also passed outside the sandbox; its restricted run
had incorrectly traversed dependency files. No configuration workaround was added.
Docker-backed integration tests and live provider/Cloud tracing smoke tests were
not run: this feature does not change persistence or model selection.

## Commits

| Commit | Deliverable |
| --- | --- |
| `2173fbe` | Specification, plan and ordered tasks. |
| `968179f` | Backend collection, monitoring API, DI and deterministic tests. |
| `afaf9f5` | React dashboard, navigation and frontend tests. |
| Final documentation commit | Business decisions, delivered contracts and verification evidence. |

## Deferred work and completion

Optional external tracing remains pending authorization and export validation.
Production authentication, operator-global monitoring, distributed/durable storage,
Prometheus/Grafana, alerting and answer evaluation are outside scope. Runtime
configuration changes and deployment are outside this delivery. The user authorized
implementation, commits, push and a PR stacked on #28. Local monitoring is delivered;
external tracing remains optional and deferred. See [decisions.md](decisions.md)
for the business review requested before code review.
