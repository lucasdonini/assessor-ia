# [NNN] [Feature title]

Status: Draft
Owner: [Person responsible for the change]
Created: [YYYY-MM-DD]
Last updated: [YYYY-MM-DD]
Related references: [Source files, issues, or existing specifications]

Template instructions: replace bracketed guidance, remove unused optional rows,
and mark non-applicable sections with a reason. Do not mark unresolved behavior as
implemented. This file describes outcomes; implementation choices belong in the plan.

## Problem and current behavior

[Who encounters the problem, under which conditions, and what happens today?
Link source or test evidence. Distinguish verified behavior from assumptions.]

## Intended outcome

[Describe the observable improvement and how success will be assessed.]

## Scope

Included: [Behaviors covered by this change.]

Excluded: [Adjacent work intentionally deferred.]

## Requirements

Use stable IDs local to this feature. Each requirement must be independently
verifiable; include edge cases and failures rather than only the successful path.

| ID | Requirement | Acceptance scenarios |
| --- | --- | --- |
| FR-001 | [Observable functional behavior] | AC-001 |
| NFR-001 | [Measurable quality or operational constraint] | AC-002 |

## Acceptance scenarios

### AC-001: [Successful user outcome]

- Given: [Initial state and acting user.]
- When: [Concrete trigger.]
- Then: [Observable result and persisted effects.]
- Requirements: FR-001.

### AC-002: [Boundary, failure, or quality outcome]

- Given: [Failure condition or measurable operating conditions.]
- When: [Concrete trigger.]
- Then: [Expected response, permitted side effects, and measurable bound if relevant.]
- Requirements: NFR-001.

Add scenarios for invalid input, unavailable dependencies, cross-user access,
repeated requests, and concurrent execution when they affect the feature.

## Contracts and data behavior

[Public inputs/outputs, compatibility, ownership, retention, and invariants.
For mutations, define cancellation, restoration, idempotency, and partial failures
as applicable. Never include real user IDs, secrets, or private financial records.]

## Open questions and assumptions

| ID | Question or assumption | Impact | Resolution |
| --- | --- | --- | --- |
| Q-001 | [Unknown behavior] | [Affected requirement] | [Unresolved or evidence-based answer] |

## Completion criteria

- Every requirement has acceptance evidence linked from `tasks.md`.
- Scope and contracts match the delivered behavior.
- Relevant checks and remaining limitations are recorded.
- Blocking questions are resolved; deferred work is explicitly identified.
