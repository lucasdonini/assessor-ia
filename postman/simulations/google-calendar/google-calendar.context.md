# Google Calendar HTTP simulation

Created 2026-10-26. Local synthetic mock based on the official
[MCP create_event](https://developers.google.com/workspace/calendar/api/v3/reference/mcp/tools_list/create_event)
and [REST events.insert](https://developers.google.com/workspace/calendar/api/v3/reference/events/insert)
contract subsets. Owner mock search was unavailable because Postman was signed out;
Orbit lookup also failed DNS. Nothing was published or deployed.

## Purpose

Run the actual Python MCP/REST adapter over HTTP without real credentials or
calendar writes. The one member, google-calendar, models initialization, discovery,
creation and bounded failure cases; unsupported operations answer 501.

## Execution

From the repository root, start `postman simulation run
postman/simulations/google-calendar/google-calendar.sim.yaml --port 4900
--output ndjson --no-history`. The listening event must identify /google.
Set CALENDAR_SIMULATION_URL=http://localhost:4900/google and run
`uv run pytest -m integration tests/integration/test_google_calendar_http.py`.
Inspect request events for /mcp/success, /mcp/disabled and /calendars/primary/events;
the tests also verify record counts via /records. Stop the foreground run with Ctrl+C.

## Assumptions

- pm.state is shared locally; tests reset /records and must run serially.
  (Observed 2026-10-26.) SyntheticAuth bypasses OAuth only; HTTP transport is real.
- Preview eligibility, live OAuth consent, write scope approval, provider changes
  and real-account isolation are not established by this mock. (Scope, 2026-10-26.)
- A generic rejection or uncertain write is not permission to retry via REST.
  The handler models commit followed by 500 to make duplication observable.
  (Observed 2026-10-26, test_google_calendar_http.py.)

## Observations

<!-- begin:observations -->
2026-10-26: Final five-case run passed. The google member received MCP and REST
traffic; no member stayed silent. REST occurred only for SERVICE_DISABLED;
the commit-then-500 case retained one remote record and returned unknown.
<!-- end:observations -->

## What didn't work

- 2026-10-26: Windows sandbox denied Postman dataset files under ~/.postman;
  running the local simulation with authorized filesystem access resolved startup.
  The MCP SDK converts HTTP rejections to MCPError; response hooks retain the
  structured service-disabled evidence without matching arbitrary error text.
