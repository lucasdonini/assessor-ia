# Specification-Driven Development

SDD means Specification-Driven Development in this repository. Describe the
intended behavior, plan its implementation, and connect delivery evidence to the
requirements. All new SDD documents are written in English.

## Structure

- `README.md`: workflow and review conventions.
- `baseline.md`: navigation to existing behavior and constraints; not a new feature.
- `templates/spec.md`: problem, scope, requirements, and acceptance scenarios.
- `templates/plan.md`: implementation boundaries, decisions, and verification.
- `templates/tasks.md`: ordered work and requirement-to-evidence traceability.
- `NNN-short-feature-name/`: one directory per future change, containing
  `spec.md`, `plan.md`, and `tasks.md` copied from the templates.

Choose the next unused three-digit number. Feature directories are created only
when a concrete change is requested. Templates are scaffolding, not approved work.

## Workflow

1. Read `../AGENTS.md`, relevant source files, tests, and existing documentation.
   Use [the baseline](baseline.md) to find starting points. Verify historical
   notes against source before treating them as current behavior.
2. Write `spec.md`: define the problem, observable outcomes, explicit exclusions,
   uniquely identified requirements, and acceptance scenarios. Record unresolved
   questions instead of silently inventing product behavior.
3. Write `plan.md`: map requirements to existing layers and contracts, document
   data and concurrency implications, and select meaningful verification.
4. Write `tasks.md`: order small deliverables, record dependencies, and map each
   requirement to a task and verification evidence.
5. Follow the user's authorization for review and implementation. SDD documents
   do not grant permission to generate code, change configuration or architecture,
   delete data, commit, or push. Explicit instructions in the current request
   control whether a review checkpoint is needed.
6. During authorized implementation, update the documents when scope changes.
   Record results and limitations; mark work complete only with evidence.

Use `Draft`, `Ready`, `In progress`, `Implemented`, or `Superseded` as the feature
status in `spec.md`. `Ready` means the specification is actionable, not that the
user has authorized code generation. A superseded specification links to its
replacement. Keep requirement IDs stable once tasks or tests refer to them.

## Project constraints

Preserve the current application layout and dependency boundaries. Python work
uses strict type hints, dependency injection, existing Ruff rules, and safe public
errors with technical details confined to logs. Keep TODO comments and do not
rewrite the existing backlog as part of adopting SDD.

Financial and session changes must state user ownership, failure behavior, and
concurrency assumptions. Any schema change needs an explicit treatment of existing
data; a destructive reset must never be an implicit implementation step. Document
changes to external model behavior with representative evaluation evidence where
deterministic tests alone cannot establish the outcome.

## Semantic commits and review

When commits are authorized, keep them small and use Conventional Commit subjects:
`docs(sdd): ...` for specifications and workflow, `feat(scope): ...` for new
behavior, `fix(scope): ...` for corrections, and `test(scope): ...` for independent
test changes. Include tests with the behavior they verify when that produces a
coherent commit; do not force a split that leaves intermediate commits broken.

A review should be able to follow requirement -> task -> implementation ->
evidence. In the review description, link the feature directory, describe the
observable change, list checks actually run, and identify remaining limitations.
For documentation-only work, inspect links, placeholders, and whitespace; runtime
test suites are needed only when runtime behavior or unresolved risks justify them.
