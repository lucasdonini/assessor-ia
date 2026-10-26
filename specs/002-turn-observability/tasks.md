# [002] Delivery tasks

Specification: [spec.md](spec.md)
Plan: [plan.md](plan.md)
Last updated: 2026-10-26

## Ordered work

- [x] T-001: Compare the supplied HTML with current source/tests. Preserve existing logging, node timing, agent-chain responses and fallback policy.
- [x] T-002: Resolve operator email allowlist, metadata-only export, verified/unknown prices and installed SDK integration. Evidence: spec.md Q-001 through Q-004.
- [x] T-003: Obtain implementation, semantic-commit and draft-PR authorization. Evidence: maintainer request on 2026-10-26.
- [x] T-004: Deliver typed observations, reader port, APP-scoped store, turn lifecycle and node/model/guardrail/fallback collection.
- [x] T-005: Deliver decimal aggregation, price catalog, authenticated monitor endpoint and OpenAPI schema.
- [x] T-006: Deliver operator React navigation, charts/tables, polling and safe failure states.
- [x] T-007: Deliver optional private exporter and verify installed SDK topology, usage, correlation and outbound filtering with captured transport. Cloud activation remains an operator deployment step.
- [x] T-008: Complete quality checks and record evidence. No migration, private environment edit, database reset or deployment was performed.

## Requirement traceability

Paths are relative to the repository root. Tests use synthetic data without paid model calls.

| Requirement | Acceptance | Task | Verification evidence | Result |
| --- | --- | --- | --- | --- |
| FR-001 | AC-001/003 | T-004 | tests/test_agents/test_graph_execution.py: success, exception, timeout and cancellation; tests/test_infrastructure/test_observability.py | Passed |
| FR-002 | AC-001/003/007 | T-004 | Selected-route, node attribution and concurrent-user graph tests | Passed |
| FR-003 | AC-001/004 | T-004 | Nested Runnable callbacks including LLMTextGenerator, unknown usage and outside-turn exclusion | Passed |
| FR-004 | AC-002/003/004 | T-004 | Real guardrail failure/refusal; tests/test_agents/test_middleware.py actual 429 fallback count | Passed |
| FR-005 | AC-005 | T-004 | 51-turn eviction, duplicate closure, late callback, empty fresh store and run cleanup | Passed |
| FR-006 | AC-005/006 | T-005 | Decimal price, unpriced-model, grouped and chronological snapshot tests | Passed |
| FR-007 | AC-002/003/006 | T-005 | Rank fixtures, inclusive 8000 ms / 5% SLO boundary and breach | Passed |
| FR-008 | AC-006/007 | T-005 | tests/test_api/test_monitor_route.py: 200/401/403, forged header, account capability, no-store and OpenAPI | Passed |
| FR-009 | AC-008 | T-006 | frontend/src/components/Monitor.test.tsx; frontend/src/api/monitor.test.ts; existing App regressions | Passed |
| FR-010 | AC-009 | T-007 | Actual Client/LangChainTracer with captured transport: root/parent IDs, usage and sentinel removal; disabled exporter | Passed locally; cloud activation not run |
| NFR-001 | AC-003/004/007 | T-004 | Interleaved tasks, nested callbacks, cancellation cleanup and telemetry-construction failure isolation | Passed |
| NFR-002 | AC-005/007/009 | T-004/T-007 | Local/outbound sentinel exclusion, bounded retention and operator authorization | Passed |
| NFR-003 | AC-010 | T-008 | Architecture/regression tests, Ruff, MyPy; existing folders/DI and unchanged TODOs/schema | Passed |

## Verification record

| Date | Command or procedure | Result | Evidence / limitation |
| --- | --- | --- | --- |
| 2026-10-26 | Read HTML, current source/tests, SDD workflow, official prices and installed SDK | Completed | Qwen explicitly unpriced. No private .env or real key read. |
| 2026-10-26 | `.venv/Scripts/pytest.exe -q` | Passed | 476 tests without integration marker; existing third-party deprecation/local-Qdrant warnings. |
| 2026-10-26 | Targeted observability, monitor, graph and middleware tests | Passed | 31 tests including real SDK with captured transport; no remote HTTP calls. |
| 2026-10-26 | `.venv/Scripts/ruff.exe check app tests` | Passed | Existing rules unchanged. |
| 2026-10-26 | `.venv/Scripts/ruff.exe format --check app tests` | Passed | 253 files checked. |
| 2026-10-26 | `.venv/Scripts/mypy.exe app` | Passed | 160 source files checked. |
| 2026-10-26 | `npm run type-check` and `npm run lint` in frontend | Passed | TypeScript and Oxlint. |
| 2026-10-26 | `npm test -- --pool=threads --maxWorkers=1` in frontend | Passed | 57 tests in 8 files. |
| 2026-10-26 | `npm run build-only` in frontend | Passed | Vite production build; dist not committed. |
| 2026-10-26 | Documentation links and whitespace review | Passed | Spec/plan/tasks relative links and git whitespace checks. |

Initial sandbox frontend execution failed before tests because temporary-file
renames/workers were denied; checks passed outside that sandbox. Initial sandbox
Python runs were stopped after stalling. Completed evidence above comes from
unsandboxed local test runs. No Docker-backed integration or live cloud smoke test
was run: this feature introduces no schema or business-persistence change, and no
real model/tracing account was activated.

## Commit sequence

- `d14d8fb` — `docs(sdd): specify turn observability and operator monitoring`.
- `99db8e1` — `feat(observability): record graph turns and expose operator monitoring`.
- `8287d21` — `feat(frontend): add operator monitoring dashboard` — UI and tests.
- `docs(observability): document operator setup and validation evidence` — this record and operational instructions.

## Deferred work and completion

Implementation is complete for the single-process scope. Verify a synthetic trace
in the actual LangSmith project when an operator chooses to enable export. Cloud
permissions/billing are not established by local tests. Persistent telemetry,
distributed aggregation, database-backed roles, quality evaluation and external
alerts remain outside scope. No merge is requested; the PR must remain draft.
