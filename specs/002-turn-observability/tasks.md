# [002] Delivery tasks

Specification: [spec.md](spec.md)
Plan: [plan.md](plan.md)
Last updated: 2026-10-26

## Ordered work

- [x] T-001: Read the supplied HTML and compare its outcomes against current source and existing tests. Evidence: verified capability matrix in spec.md; no implementation changes.
- [x] T-002: Resolve Q-001/Q-002 with the maintainer; verify official prices/model aliases and installed SDK/export behavior for Q-003/Q-004; update contracts, plan and acceptance scenarios. Completed in spec.md Q-001 through Q-004: operator email allowlist, metadata-only export, verified/unknown price policy and installed SDK integration.
- [ ] T-003: After T-002, obtain explicit code-generation authorization under AGENTS.md. Ready status alone is not permission.
- [ ] T-004: Deliver typed contracts, APP-scoped bounded store, exactly-once lifecycle and node/model/guardrail/fallback observations with concurrency and privacy evidence. Depends on T-003.
- [ ] T-005: Deliver exact aggregation, versioned catalog, authenticated `/api/monitor` and OpenAPI contracts with deterministic boundary/auth tests. Depends on T-004.
- [ ] T-006: Deliver React monitoring view, signed-in navigation, charts, tables and polling/error-state tests. Depends on T-005.
- [ ] T-007: Deliver optional tracing under the selected privacy policy, verify synthetic root/child correlation and document approved activation procedure. Depends on T-004 and resolved Q-002/Q-004. Configuration edits require explicit authorization if needed.
- [ ] T-008: Run relevant checks, inspect compatibility and record evidence/limitations; update documentation and feature status only when acceptance is established. Depends on T-005/T-006/T-007.

## Requirement traceability

| Requirement | Acceptance | Task | Planned verification | Result |
| --- | --- | --- | --- | --- |
| FR-001 | AC-001/003 | T-004 | Graph lifecycle tests: success, validation, timeout, cancel | Not run |
| FR-002 | AC-001/003/007 | T-004 | Node timing/route/correlation and chat contract regression | Not run |
| FR-003 | AC-001/004 | T-004 | Nested model callbacks, metadata fixtures, out-of-turn calls | Not run |
| FR-004 | AC-002/003/004 | T-004 | Guardrail failure distinction and existing 429 middleware tests | Not run |
| FR-005 | AC-005 | T-004 | Retention, duplicate/late callbacks, reset and bounded children | Not run |
| FR-006 | AC-005/006 | T-005 | Filtered aggregation and exact cost/group/series fixtures | Not run |
| FR-007 | AC-002/003/006 | T-005 | Rank/SLO equality and empty-data fixtures | Not run |
| FR-008 | AC-006/007 | T-005 | HTTP auth, no-store, OpenAPI, no external calls | Not run |
| FR-009 | AC-008 | T-006 | Frontend timers, states, UI and build verification | Not run |
| FR-010 | AC-009 | T-007 | Export-payload checks and synthetic remote smoke check | Not run |
| NFR-001 | AC-003/004/007 | T-004 | Async interleaving, actual nested propagation, fail-safe collector | Not run |
| NFR-002 | AC-005/007/009 | T-004/T-007 | Sensitive-data sentinels, snapshot isolation, exporter policy | Not run |
| NFR-003 | AC-010 | T-008 | Dependency review, relevant backend/frontend checks and diff review | Not run |

## Verification record

| Date | Procedure | Result | Limitations |
| --- | --- | --- | --- |
| 2026-10-26 | Read local HTML, inventory repository and inspect relevant source/tests/SDD templates | Completed | Static evidence only; tests were read, not executed. |
| 2026-10-26 | Inspect `.env.example` LangSmith names and configured model/fallback source | Completed | No private `.env`, account or remote traces inspected. Official public pricing and local SDK source were subsequently inspected. |

No runtime suites or live integrations were executed because this delivery changes documentation only. Proposed tests remain Not run. Documentation relative links and whitespace were checked after authoring.

## Deferred work and completion

Persistent telemetry, distributed snapshots, operator authorization infrastructure, quality evaluation and external alerting are excluded. Q-001 through Q-004 are resolved; status is Ready for review, without code-generation authorization. No implementation, configuration edit, commit, push or cloud publication is part of this delivery. A future authorized commit could use `docs(sdd): specify turn observability`; no commit has been made.
