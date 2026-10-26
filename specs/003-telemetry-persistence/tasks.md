# [003] Delivery tasks

Specification: [spec.md](spec.md)
Plan: [plan.md](plan.md)

- [x] T-001: Inspect collector, MongoManager, providers and monitor contract; select MongoDB and document semantics.
- [x] T-002: Deliver repository, completed timestamps, warm restoration and bounded fail-safe persistence. FR-001–006, NFR-001.
- [x] T-003: Update dashboard retention/degradation states and documentation. FR-002/005/006.
- [x] T-004: Verify unit, HTTP/frontend, typing/lint and real Mongo integration; record evidence. All requirements.

## Verification

| Check | Result | Evidence |
| --- | --- | --- |
| `.venv/Scripts/pytest.exe -q` | Passed | 481 non-integration tests, including existing graph/API/privacy regressions. |
| `.venv/Scripts/pytest.exe -m integration tests/integration/test_mongodb_telemetry.py -q` | Passed | Real MongoDB 7 in a disposable Docker container: 51 stored documents, latest-50 restoration, UTC dates, duplicate prevention and no TTL. |
| `.venv/Scripts/ruff.exe check app tests` | Passed | Existing rules unchanged. |
| `.venv/Scripts/ruff.exe format --check app tests` | Passed | 257 files checked. |
| `.venv/Scripts/mypy.exe app` | Passed | 162 source files checked. |
| `npm run type-check` and `npm run lint` in frontend | Passed | TypeScript and Oxlint. |
| `npm test -- --pool=threads --maxWorkers=1` in frontend | Passed | 58 tests across 8 files. |
| `npm run build-only` in frontend | Passed | Vite production build. |

## Requirement traceability

| Requirement | Evidence | Result |
| --- | --- | --- |
| FR-001 | Unit save serialization and original-error tests; real Mongo round trip | Passed |
| FR-002 | Real Mongo 51-document count and fresh collector restore; no TTL index assertion | Passed |
| FR-003 | Native BSON date/schema-version unit test and timezone-aware integration read | Passed |
| FR-004 | Unique _id/setOnInsert unit assertion, lost-ack retry, timeout and real duplicate test | Passed |
| FR-005 | Startup-history failure, write failure, original exception preservation and degraded-panel test | Passed |
| FR-006 | Restart restoration, cancellation/shielded write and shutdown-drain tests | Passed |
| NFR-001 | Repository protocol, APP-scoped provider review, Ruff/MyPy and regressions | Passed |

The first container attempt timed out while opening a new driver connection;
the integration setup now initializes the connection first, matching the existing
production MongoManager lifecycle. The two-second telemetry deadline is unchanged.
Only the affected Mongo integration test was run; the full integration suite was
not repeated. Existing third-party deprecation/local-Qdrant warnings remain.

No application database or private environment was changed during validation.
Only the new telemetry collection/index is initialized by the application when
this implementation is deployed. Abrupt termination before acknowledgment or
prolonged MongoDB outage can still lose telemetry: there is no durable outbox.
