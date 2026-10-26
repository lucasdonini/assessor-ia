# [003] Implementation plan

Specification: [spec.md](spec.md)

Use the existing MongoManager database and raw asynchronous PyMongo adapter,
consistent with existing infrastructure adapters. The application repository
protocol defines initialize/save/latest. No new service or provider hierarchy
is required. Add only files inside existing directories.

TurnTelemetry retains its sync collector for callbacks and unit fixtures. The
graph uses an async persisted_turn scope: close local recording first, then save
the immutable completed observation. A shielded, tracked task survives caller
cancellation and is drained by the APP-scoped provider before Mongo disposal.
Persistence has a total two-second deadline and one idempotent retry.

Warm the existing bounded deque from repository.latest(50) before graph delivery.
The Mongo adapter stores dates as UTC BSON datetimes, and embedded observations
as ordinary documents. _id provides uniqueness; descending completed_at/_id
ordering handles deterministic restoration without modifying business records.

Add persistence health to the snapshot and propagate it through MonitorService
to the existing operator endpoint and React view. Failures use fixed diagnostic
messages, never raw database exceptions or credentials.

Verify repository serialization/ordering/upsert behavior, timeout and duplicate
semantics, restoration into a fresh collector, original-error preservation,
cancellation and shutdown draining. Run a real Mongo test in a disposable
container if Docker is available; record limitations explicitly otherwise.
