# [003] Durable turn telemetry

Status: Implemented
Created: 2026-10-26
Owner: Project maintainer
References: [previous feature](../002-turn-observability/spec.md), [plan](plan.md), [tasks](tasks.md).

## Problem and intended outcome

The previous feature keeps 50 completed turns in RAM, losing them on restart.
The maintainer requested persistence and delegated the database choice. Use
MongoDB: a turn and its model/node observations form one atomic document, and
the application already provides an asynchronous MongoDB connection.

This specification supersedes feature 002's process-only retention and restart
reset requirements. Operator authentication and metadata-only privacy remain.

## Requirements and acceptance

| ID | Requirement | Acceptance evidence |
| --- | --- | --- |
| FR-001 | Save every newly completed turn, including blocked/error/cancelled turns, as one immutable versioned document keyed uniquely by turn_id. | Save/retry tests and Mongo integration round trip. |
| FR-002 | Retain all saved turns without TTL or automatic deletion. Load the latest 50 by completed_at/_id at startup, oldest first for existing aggregation; the dashboard remains a 50-turn window across restarts. | 51-turn restart test; no deletion/index TTL operations. |
| FR-003 | Preserve existing safe telemetry fields and add UTC completed_at. Store native BSON dates and schema_version=1; no prompts/replies/tool payloads/raw exceptions. | Serialized-document checks and round trip. |
| FR-004 | Journal-acknowledged, idempotent upsert; one retry within a total two-second persistence deadline. Never repeat business operations. | Lost acknowledgment, duplicate and timeout tests. |
| FR-005 | Persistence failure cannot fail a successful graph or replace its original exception. Keep local observations and expose process-local failed/pending write counts, degraded state and whether history loaded. Startup history failure is visible and does not independently stop the application. | Failure/cancel tests and dashboard degradation UI. |
| FR-006 | Graceful shutdown drains writes before closing MongoDB. Restart changes uptime but restores recorded history; active graphs are not restored. | Lifecycle and fresh-instance restoration tests. |
| NFR-001 | Preserve dependency direction using an application repository protocol, Mongo adapter and APP-scoped Dishka wiring. No PostgreSQL migration or private environment change. | Typing/lint/regression checks. |

## Contract and failure semantics

Collection: telemetry_turns in the existing application MongoDB database. _id is
the turn UUID string; a descending compound index covers completed_at and _id.
Duplicate delivery uses setOnInsert and cannot rewrite an existing observation.
Documents are retained indefinitely until a separately authorized retention policy.
Completed_at is the graph completion time, excluding database persistence latency.
There is no durable outbox: abrupt process termination before acknowledgment or
database outage beyond the bounded retry can lose a turn. The panel explicitly
reports degradation; no exactly-once durability during outages is promised.

GET /api/monitor keeps its existing fields and adds persistence with enabled,
history_loaded, pending_writes, failed_writes and degraded. Retention is mongo_window
with repository wiring, process_window for isolated in-memory test instances.
The UI explains cross-restart retention and warns on missing history or writes.
The repository is never exposed directly to unprivileged API consumers.

MongoDB is already an application dependency: this does not promise full startup
when the existing MongoManager cannot initialize. Turns that existed only in RAM
before this deployment cannot be recovered retroactively. Historical prices remain
derived from stored model usage using the current versioned estimate catalog.

## Open questions

None. No automatic expiry or history-export UI is introduced. Multi-worker graph
coordination remains outside scope; the application still uses one worker.
