# 001 Delivery tasks

Specification: [spec.md](spec.md)
Plan: [plan.md](plan.md)
Last updated: 2026-10-26

## Ordered work

- [x] T-001: Inspect source/reference and resolve product decisions. Evidence:
  current-state findings in spec.md and user's choices for per-user Google login,
  conflict confirmation and missing-duration clarification.
- [ ] T-002: Verify external Cloud/OAuth prerequisites and sanitized current MCP
  schema. Select maintained compatible libraries and least-privilege write scopes.
  Depends on T-001. No live mutation or Cloud configuration without authorization.
- [ ] T-003: Deliver authenticated owner resolution, sessions and Calendar consent
  lifecycle; protect existing private routes. Depends on T-002.
- [ ] T-004: Add event domain/contracts, additive migrations and repositories.
  Verify existing-data preservation and scoped filters. Depends on T-003.
- [ ] T-005: Add conflict proposals, serialized check/create, operation receipts
  and local-first export workflow. Depends on T-004.
- [ ] T-006: Deliver async OAuth credential/provider adapters, MCP discovery and
  create, classified fallback, refresh serialization and uncertain-outcome handling.
  Depends on T-002/T-003/T-005.
- [ ] T-007: Compose agenda tools and typed write evidence; update agenda and
  orchestration prompts; preserve conversational history. Depends on T-005/T-006.
- [ ] T-008: Add frontend login/logout/Calendar connection controls and replace
  UUID selection; update client auth and CSRF handling. Depends on T-003/T-007.
- [ ] T-009: Run deterministic, disposable-database, simulated-provider, regression
  and representative model checks. Depends on T-003 through T-008.
- [ ] T-010: Verify real two-account ownership and MCP write/readback; document
  setup, operational recovery, limitations and legacy-account behavior. Depends on
  T-009. Mark Implemented only when required evidence exists.

## Requirement traceability

| Requirement | Acceptance | Tasks | Planned evidence | Result |
| --- | --- | --- | --- | --- |
| FR-001 | AC-001 | T-003/008/009 | OAuth/session and existing route ownership tests | Not run |
| FR-002 | AC-002 | T-003/006/008/010 | Consent/disconnect and two-account evaluation | Not run |
| FR-003 | AC-003 | T-004/005/009 | Validation and database readback | Not run |
| FR-004 | AC-004 | T-004/009 | PostgreSQL filters and timezone boundaries | Not run |
| FR-005 | AC-005 | T-005/009 | Conflict confirmation and concurrent creation | Not run |
| FR-006 | AC-006 | T-005/006/010 | Local-first trace and both destination readbacks | Not run |
| FR-007 | AC-007 | T-002/006/009/010 | Protocol discovery, failure simulation and real MCP | Not run |
| FR-008 | AC-008 | T-005/006/009 | Partial failure, cancellation and crash recovery | Not run |
| FR-009 | AC-009 | T-007/009 | Typed receipt validation and Portuguese model evaluation | Not run |
| FR-010 | AC-010 | T-005/006/009 | Repeated calls, unknown-state retry suppression | Not run |
| NFR-001 | AC-011 | T-004/007/009 | Architecture review, typing/lint and regressions | Not run |
| NFR-002 | AC-002/012 | T-003/006/009 | Encryption, redaction, CSRF and refresh/disconnect races | Not run |
| NFR-003 | AC-001/011 | T-003/004/009 | Populated previous-schema migration and ownership | Not run |
| NFR-004 | AC-007/008 | T-006/009 | Total deadline and propagated cancellation | Not run |

## Verification record

| Date | Procedure | Result | Limitation |
| --- | --- | --- | --- |
| 2026-10-26 | Read supplied HTML, relevant source, tests, migrations and project instructions | Completed | Static assessment; no application or DB mutation |
| 2026-10-26 | Read official Google MCP configuration/create contract and web OAuth/REST insert references | Completed | Public documentation only; no credentials or live calls |
| 2026-10-26 | Resolve four user-facing scope decisions | Completed | Remaining detailed defaults explicitly recorded in spec |
| 2026-10-26 | Runtime suites and Google end-to-end checks | Not run | Documentation-only task; implementation absent |

## Authorization and deferred work

Only specification documents are delivered. No implementation, configuration,
Cloud provisioning, secret changes, commits or pushes are authorized or performed.
Future code generation still requires the explicit request required by AGENTS.md.
No commit sequence is scheduled because commits were not requested.

Deferred: legacy-account claim/migration UI, two-way sync, recurrence, event
editing/deletion, automatic remote retries, external agenda-tool publication and
multi-worker deployment. These do not block the stated initial release.
