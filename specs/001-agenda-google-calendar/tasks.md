# 001 Delivery tasks

Specification: [spec.md](spec.md)
Plan: [plan.md](plan.md)
Last updated: 2026-10-26

## Ordered work

- [x] T-001: Inspect source/reference and resolve product decisions. Evidence:
  current-state findings in spec.md and user's choices for per-user Google login,
  conflict confirmation and missing-duration clarification.
- [ ] T-002: Verify external Cloud/OAuth prerequisites for REST; optional sanitized MCP
  schema. Select maintained compatible libraries and least-privilege write scopes.
  Depends on T-001. No live mutation or Cloud configuration without authorization.
- [x] T-003: Deliver authenticated owner resolution, sessions and Calendar consent
  lifecycle; protect existing private routes. Depends on T-002.
- [x] T-004: Add event domain/contracts, additive migrations and repositories.
  Verify existing-data preservation and scoped filters. Depends on T-003.
- [x] T-005: Add conflict proposals, serialized check/create, operation receipts
  and local-first export workflow. Depends on T-004.
- [x] T-006: Deliver async OAuth credential/provider adapters, MCP discovery and
  create, classified fallback, refresh serialization and uncertain-outcome handling.
  Depends on T-002/T-003/T-005.
- [x] T-007: Compose agenda tools and typed write evidence; update agenda and
  orchestration prompts; preserve conversational history. Depends on T-005/T-006.
- [x] T-008: Add frontend login/logout/Calendar connection controls and replace
  UUID selection; update client auth and CSRF handling. Depends on T-003/T-007.
- [ ] T-009: Run deterministic, disposable-database, simulated-provider, regression
  and representative model checks. Depends on T-003 through T-008.
- [ ] T-010: Verify real two-account ownership and REST write/readback; document
  setup, operational recovery, limitations and legacy-account behavior. Depends on
  T-009. Mark Implemented only when required evidence exists.

## Requirement traceability

| Requirement | Acceptance | Tasks | Planned evidence | Result |
| --- | --- | --- | --- | --- |
| FR-001 | AC-001 | T-003/008/009 | OAuth/session and existing route ownership tests | Passed controlled OAuth/session/forged-header checks; real login pending |
| FR-002 | AC-002 | T-003/006/008/010 | Consent/disconnect and two-account evaluation | Passed controlled consent/isolation/disconnect; real consent pending |
| FR-003 | AC-003 | T-004/005/009 | Validation and database readback | Passed input validation and PostgreSQL creation |
| FR-004 | AC-004 | T-004/009 | PostgreSQL filters and timezone boundaries | Passed controlled queries, date boundaries and owner filters |
| FR-005 | AC-005 | T-005/009 | Conflict confirmation and concurrent creation | Passed concurrent conflict, changed proposal and confirmation checks |
| FR-006 | AC-006 | T-005/006/010 | Local-first trace and both destination readbacks | Passed local-first and simulated provider readback; real readback pending |
| FR-007 | AC-007 | T-002/006/009/010 | REST default, optional protocol discovery, failure simulation and live readback | Passed nine HTTP simulation cases; real REST readback pending |
| FR-008 | AC-008 | T-005/006/009 | Partial failure, cancellation and crash recovery | Passed local retention, timeout, cancellation and uncertain response checks |
| FR-009 | AC-009 | T-007/009 | Typed receipt validation and Portuguese model evaluation | Passed deterministic receipt protection; live-model evaluation pending |
| FR-010 | AC-010 | T-005/006/009 | Repeated calls, unknown-state retry suppression | Passed repeated operation/confirmation and uncertain-response checks |
| NFR-001 | AC-011 | T-004/007/009 | Architecture review, typing/lint and regressions | Passed architecture regression, Ruff and MyPy |
| NFR-002 | AC-002/012 | T-003/006/009 | Encryption, redaction, CSRF and refresh/disconnect races | Passed encryption, signature, state replay, CSRF and race checks |
| NFR-003 | AC-001/011 | T-003/004/009 | Populated previous-schema migration and ownership | Passed populated previous-schema migration and legacy-owner preservation |
| NFR-004 | AC-007/008 | T-006/009 | Total deadline and propagated cancellation | Passed service timeout/cancellation checks; five HTTP failure cases |

## Verification record

All procedures below ran on 2026-10-26. Dependency deprecation warnings remain;
there were no test failures in the final successful runs.

| Procedure | Result | Evidence / limitation |
| --- | --- | --- |
| `python -m ruff check .` and `python -m ruff format --check .` | Passed | Repository checks; 243 Python files formatted |
| `python -m mypy .` | Passed | 153 application source files |
| `python -m pytest -q --junitxml=.pytest_cache/agenda-final-unit.xml` | Passed | 445 unit tests; synthetic identities, signed-token rejection, safe final receipts, existing MCP regressions |
| `python -m pytest -m integration --ignore=tests/integration/test_google_calendar_http.py -q` | Passed | Disposable PostgreSQL/MongoDB, local Qdrant; concurrency, owner filters, OAuth state and populated previous-schema migration |
| `python -m pytest tests/integration/test_google_calendar_http.py -m integration -q` with CALENDAR_SIMULATION_URL | Passed | Five real-HTTP client cases against Postman; request events verified; actual Google not contacted |
| `npm run --prefix frontend test` | Passed | 50 tests, including logout privacy and explicit conflict confirmation |
| Frontend `type-check`, `lint`, and `build` | Passed | TypeScript, Oxlint and production Vite bundle |
| `git diff --check` | Passed | No whitespace errors |
| Cloud preflight, real OAuth consent and Google/MCP event readback | Not run | Deployment credentials and preview configuration are not provisioned by this change |
| Representative live-model evaluation | Not run | Deterministic receipt protection is tested; actual tool selection/clarification still needs evaluation |

Windows sandbox restrictions initially blocked async test execution and Postman
state files; authorized runs outside those restrictions passed. Orbit discovery
failed DNS; Postman owner-mock search required a login. The local synthetic mock
uses official contract subsets and was not published.

## Authorization and deferred work

### Follow-up runtime diagnosis, 2026-10-26

The user reported internal IDs in confirmations and a failed Calendar export.
The ID originated in the trusted creation template and frontend conflict notice;
both now omit local, operation and remote identifiers. Receipts keep internal IDs.

Read-only inspection found an existing mcp_tool_error receipt. A live read-only
MCP probe returned an explicit Developer Preview enrollment requirement for the
configured Cloud project. OAuth test-user membership and enabling the APIs do
not enroll a project in this program. No Google event creation or update was
attempted during diagnosis; no application records or credentials were modified.

Tool errors now retain only a fixed error_category label, with a warning diagnostic
and safe preview-specific user wording. Old JSON receipts remain compatible.
Third-party MCP/httpx2 debug payload logs are suppressed. The preview restriction
does not enable REST fallback; the existing service-disabled-only policy remains.

Follow-up verification: 42 focused Python tests, six Postman HTTP scenarios and
all 50 frontend tests passed; Ruff, formatting, MyPy and frontend type checking
passed. The frontend parallel-fork run timed out during worker startup and is
not counted as a pass; retrying with --maxWorkers=1 --pool=threads passed.
Live MCP creation remains blocked until the configured project is enrolled.

The user authorized implementation, semantic commits and a draft PR after the
specification delivery. Code and example configuration are now delivered; no live
credentials, Cloud resources or application databases were changed. T-002 remains
open for external preflight; T-009 is locally verified but live-model evaluation
remains open; T-010 requires real user consent and MCP readback.

Semantic delivery commits:
- 3dae4d3: docs(sdd), initial specification.
- 7ef58b2: feat(agenda), authenticated backend, persistence and controlled tests.
- 880200c: feat(web), login/connection/conflict UI and frontend regressions.
- 23b5a9f: test(calendar), local HTTP simulation and run context.

Do not mark the feature Implemented before the real-service and model-evaluation
gates pass. A draft PR is for review and explicitly does not imply release readiness.

Deferred: legacy-account claim/migration UI, two-way sync, recurrence, event
editing/deletion, automatic remote retries, external agenda-tool publication and
multi-worker deployment. These do not block the stated initial release.


## Approved REST default (2026-10-26)

The user approved using REST as the main path because their project cannot join
Workspace Developer Preview. This supersedes the earlier MCP readiness gate for
the default integration. GOOGLE_CALENDAR_TRANSPORT defaults to rest; mcp is opt-in
and retains the restrictive service-disabled fallback. No historical event is
re-exported, and neither transport automatically retries uncertain writes.

Verification: nine actual HTTP simulation cases passed (three default REST cases,
six optional MCP cases), with zero MCP calls for REST. REST denial created no
remote record; commit-then-500 retained exactly one record and returned unknown.
35 related unit tests, Ruff and MyPy (153 application files) passed. Live REST
creation/readback and two-account validation remain pending; no Google write was
performed by these checks.
