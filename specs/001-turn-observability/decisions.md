# Business decisions for review before code review

Implemented local monitoring scope, 2026-10-06. These are explicit choices for
the user to critique, rather than assumptions hidden in implementation.

| Decision | Delivered behavior | Tradeoff / alternative |
| --- | --- | --- |
| User-scoped visibility | Every metric and turn is filtered by the validated selected user; uptime is process metadata. | Does not give an operator a global view. Existing UUID selection remains demo identity, not authentication. |
| Short-lived retention | Last 50 terminal turns of the process, globally bounded, then filtered by user. Restart clears telemetry only. | Another user's activity can evict older observations. Per-user history or durable storage needs a separate retention/access policy. |
| Measurement boundary | SLO measures graph execution, including its internal tool/model work. | Session lock waiting and before/after persistence are excluded; a graph success can precede an HTTP persistence failure. |
| Safety versus service failure | Legitimate refusals are blocked. Classifier unavailability and indeterminate classification are operational errors, with existing safe chat responses preserved. | More informative than treating every safe refusal as healthy. |
| Cancellation | Cancelled turns stay visible, separately counted, and do not enter the SLO denominator or percentile. | Frequent client cancellation can hide slow abandoned work from the SLO; its separate count remains visible. |
| Teaching SLO | Nearest-rank p95 <= 8000 ms and operational error rate <= 5%, inclusive. Blocked turns enter the denominator/latencies; zero eligible turns yields insufficient data. | No SLA and no claim of statistical reliability for small windows. |
| Conservative accounting | Report known token/cost subtotals, with separate completeness flags. Failed attempts without usage are unknown, not free. Paid full text rates ignore cache discounts. | Estimates may exceed discounted billing or be lower bounds when evidence is missing. |
| Qwen fallback | Preserve the existing 429-only recovery and configured Qwen 3.6 identifier; record actual activations. Qwen remains unpriced. | Official current Groq docs list deprecation and omit its current rate. Model migration is deliberately a separate product/quality change. |
| Content privacy | Local telemetry stores identifiers, safe reason codes and numeric/model evidence, without prompts, responses, tool content or raw exceptions. | It explains timing and cost, not response content. Existing independently enabled SDK tracing is a separate data path. |
| Detail cap | Keep up to 1000 node observations and 1000 attempts per turn; truncate with an explicit incomplete flag and known subtotals. | Exceptional huge turns lose detailed accounting beyond the cap, while duration/status/fallback counts remain available. |
| Monitor refresh | Refresh on entry, manually and 4 seconds after the preceding request completes. Preserve last snapshot as stale on failure. | Actual cadence slows with request latency; prevents overlapping polls and uncontrolled request queues. |
| Chat continuity | Keep the selected user's chat mounted while visiting profile/monitor; switching user still selects that user's session. | An in-flight chat can finish while the monitor is visible. |
| External tracing | Local monitor is delivered without requiring or enabling LangSmith. Root graph run ID uses the local trace UUID for future correlation. | Optional redacted export/credential configuration remains deferred; no cloud trace has been validated. |

## Verified pricing references

- [Google Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing.md):
  Gemini 2.5 Flash full text rates USD 0.30 input / 2.50 output per million;
  output includes thinking tokens.
- [Groq supported models](https://console.groq.com/docs/models): GPT-OSS 120B
  USD 0.15 input / 0.60 output per million. Current table does not list Qwen 3.6.
- [Groq deprecations](https://console.groq.com/docs/deprecations): Qwen 3.6
  deprecation entry. No replacement was selected within this observability work.
