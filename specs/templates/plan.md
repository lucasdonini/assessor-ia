# [NNN] Implementation plan

Specification: [spec.md](spec.md)
Last updated: [YYYY-MM-DD]

## Verified context

[List inspected source files and tests. Identify existing behavior to preserve,
dependency boundaries, and assumptions that still require investigation.]

## Approach and affected layers

| Requirement | Existing layer / path | Planned responsibility | Contract impact |
| --- | --- | --- | --- |
| FR-001 | [Existing path] | [Smallest necessary change] | [Change or none] |

Preserve the current layout. Use existing application ports and dependency
injection boundaries. Explain any proposed architectural change and the explicit
authorization it requires before including it in implementation tasks.

## Decisions

| Decision | Rationale | Alternatives and tradeoffs |
| --- | --- | --- |
| [Selected approach] | [Constraint or evidence] | [Relevant alternative and cost] |

## Data, identity, and concurrency

[State user scoping, storage effects, atomicity boundaries, repeated-operation
behavior, and process/worker assumptions. If no data changes occur, say so.
For migrations, describe existing-data compatibility, rollout, and recovery without
assuming permission for destructive commands.]

## Errors and observability

[Describe application exceptions, safe public responses, internal diagnostics,
and how failures or incomplete writes become visible. Avoid exposing secrets or
technical exception details to application users.]

## Verification strategy

| Scenario / requirement | Check and location | Environment | Expected evidence |
| --- | --- | --- | --- |
| AC-001 / FR-001 | [Meaningful test or manual check] | [Unit, container, or local] | [Observable outcome] |
| AC-002 / NFR-001 | [Failure or quality check] | [Controlled conditions] | [Expected result] |

Select checks appropriate to affected behavior. Backend options include Ruff,
format checking, MyPy, pytest, and container-backed integration tests. Frontend
options include lint, type checking, tests, and build. Use the repository's existing
commands and configuration. Record actual execution results in `tasks.md`.

For LLM or retrieval behavior, separate deterministic contract checks from
representative model evaluation; record dataset, model, conditions, and limitations
when such evaluation is necessary. Avoid real private data in committed evidence.

## Delivery and recovery

[Ordered rollout, compatibility requirements, semantic commit boundaries, and a
recovery approach if applicable. Identify external services or configuration work
that requires separate authorization.]

## Unresolved risks

[Risk, affected requirement, mitigation, and whether it blocks implementation.
Use "None identified" only after reviewing the relevant behavior.]
