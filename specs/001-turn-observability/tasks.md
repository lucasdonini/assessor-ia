# [001] Delivery tasks

Specification: [spec.md](spec.md)
Plan: [plan.md](plan.md)
Last updated: 2026-10-06

## Ordered work

- [ ] T-001: Verify callback propagation and usage/model shapes in installed code;
  resolve Q-002 with deterministic nested/direct/fallback/cancellation evidence.
- [ ] T-002: Define typed records/ports and injected bounded store, context and
  atomic snapshots. Depends on T-001.
- [ ] T-003: Instrument graph lifecycle/nodes/selected edge and guardrail outcome
  reasons without changing chat behavior. Depends on T-002.
- [ ] T-004: Observe 429 fallback and implement complete/partial usage accounting;
  verify exact provider/model pricing with dated primary sources. Depends on T-003.
- [ ] T-005: Implement user-scoped aggregation, schemas, DI and API registry;
  verify thresholds, empty window, eviction and ownership. Depends on T-004.
- [ ] T-006: Implement React API client/view/navigation, safe rendering, polling
  lifecycle, charts and node detail; preserve chat state. Depends on T-005.
- [ ] T-007: Run relevant regressions and static checks; update contracts,
  limitations and evidence; review all requirements. Depends on T-006.
- [ ] T-008: Optional separately authorized LangSmith configuration, SDK/redaction
  validation and correlated synthetic trace; resolve Q-003. Depends on T-007.

Tasks are proposed implementation work. None is marked complete by this
documentation delivery; tests have not been run and code generation is not granted.

## Requirement traceability

| Requirement | Scenario | Task | Verification location / procedure | Result |
| --- | --- | --- | --- | --- |
| FR-001 | AC-001, AC-003 | T-003 | Graph tests and collector lifecycle tests | Not run |
| FR-002 | AC-001, AC-004 | T-001, T-003, T-004 | Nested/direct callback and graph node fixtures | Not run |
| FR-003 | AC-002, AC-003 | T-003 | Guardrail, graph timeout and cancellation tests | Not run |
| FR-004 | AC-004 | T-004 | Middleware 429/non-429/multiple activation tests | Not run |
| FR-005 | AC-005 | T-004 | Usage normalization and pricing fixture tests | Not run |
| FR-006 | AC-001, AC-006, AC-007 | T-005 | Monitor API and service tests | Not run |
| FR-007 | AC-002, AC-007 | T-005 | Exact p95/denominator/threshold fixtures | Not run |
| FR-008 | AC-006, AC-007 | T-002, T-005 | Eviction, restart and coherent snapshot tests | Not run |
| FR-009 | AC-008 | T-006 | React fake timer, switching and chat preservation tests | Not run |
| FR-010 | AC-009 | T-007, T-008 | Local tracing-disabled test; optional synthetic export audit | Not run |
| NFR-001 | AC-003, AC-010 | T-002, T-003 | Failure injection and duplicate cleanup tests | Not run |
| NFR-002 | AC-006, AC-010 | T-002, T-005 | Concurrent users and late callback fixtures | Not run |
| NFR-003 | AC-011 | T-007 | Architecture, existing regressions, Ruff/MyPy/frontend checks | Not run |
| NFR-004 | AC-006, AC-009 | T-005, T-006, T-008 | Snapshot deny-list, safe rendering and export audit | Not run |

## Verification record

| Date | Procedure | Result / limitation |
| --- | --- | --- |
| 2026-10-06 | Read lesson HTML and relevant graph, LLM, middleware, guardrail, API, DI, logging, settings and frontend sources | Compatibility map grounded in source inspection; no live provider or SDK behavior verified. |
| 2026-10-06 | Review specifications for requirement/scenario/task coverage and relative links | Documentation review only; runtime checks remain Not run. |

## Deferred work and completion

Optional external tracing remains pending authorization and export validation.
Production authentication, operator-global monitoring, distributed/durable storage,
Prometheus/Grafana, alerting and answer evaluation are outside scope. Runtime
configuration changes, commits and pushes remain unauthorized. The feature stays
Draft until implementation decisions and blocking technical spikes are resolved.
