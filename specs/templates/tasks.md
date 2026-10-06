# [NNN] Delivery tasks

Specification: [spec.md](spec.md)
Plan: [plan.md](plan.md)
Last updated: [YYYY-MM-DD]

## Ordered work

Replace these example task descriptions with concrete deliverables. A checked task
means its completion criteria have been verified. These tasks do not authorize
implementation or commits; follow the current user request and `AGENTS.md`.

- [ ] T-001: Resolve blocking questions and confirm the inspected contracts.
  Requirements: [IDs]. Depends on: none. Completion evidence: [Decision or source].
- [ ] T-002: Deliver [bounded behavior] in [existing path] with relevant checks.
  Requirements: [IDs]. Depends on: T-001. Completion evidence: [Tests and result].
- [ ] T-003: Review contract compatibility and update affected documentation.
  Requirements: [IDs]. Depends on: T-002. Completion evidence: [Review and checks].

## Requirement traceability

| Requirement | Acceptance scenario | Task | Verification location | Result |
| --- | --- | --- | --- | --- |
| FR-001 | AC-001 | T-002 | [Test path or manual procedure] | Not run |
| NFR-001 | AC-002 | [Task ID] | [Check location] | Not run |

Every requirement in `spec.md` must have a row. Link evidence to observable
outcomes; a file existing or a task being checked is not sufficient proof.

## Verification record

| Date | Command or procedure | Result | Evidence / limitation |
| --- | --- | --- | --- |
| [YYYY-MM-DD] | [Exact check actually run] | [Passed / Failed / Blocked] | [Summary without private data] |

Keep unexecuted checks marked "Not run" in traceability. Report missing services
or tooling as limitations; never substitute an assumed pass.

## Commit sequence

| Order | Semantic commit subject | Deliverable / tasks |
| --- | --- | --- |
| 1 | docs([scope]): define [feature] requirements and plan | [Specification work] |
| 2 | feat([scope]): implement [observable behavior] | [Task IDs, including relevant tests] |
| 3 | docs([scope]): record [feature] verification and constraints | [Evidence and documentation] |

Adapt the sequence to the change; use `fix` for corrections and avoid empty or
artificial commits. Record final commit IDs here only when useful; a commit cannot
contain its own final hash.

## Deferred work and completion

[List deferred items with reasons and references. Record remaining limitations.
Update the status in `spec.md` only when its completion criteria are satisfied.]
