# JEV adapter simulation

The mock implements the TypeSafe System One contract subset used by the adapter.
No owner's mock was imported; this is a local synthetic contract fixture, not
vendor accuracy evidence. No workspace binding or publication is required.

Run from the repository root:

- postman simulation run postman/simulations/jev/jev.sim.yaml --port 4911 --no-history --output ndjson
- Set JEV_SIMULATION_URL to http://127.0.0.1:4911/jev in the test process.
- Run pytest -m integration tests/integration/test_jev_http.py.

The tests invoke the real asynchronous application adapter over HTTP with a fake
key. Outcome paths select approval, rejection, partial/low support, malformed
response, rate limit, server error and a response exceeding the five-second
deadline. Other paths return 501. Do not send private data or real credentials.

Execution evidence is recorded in specs/004-evidence-validation/tasks.md. The
simulation proves transport/decision/failure behavior, not Portuguese fidelity.

Verified 2026-10-27 with Postman CLI 1.76.0: all eight adapter cases passed.
The request log showed this member serving every outcome path; no member was
silent. The hanging fixture answered after six seconds while the adapter had
already refused within its five-second deadline. No real vendor call was made.
