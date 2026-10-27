# [004] Evidence validation and truthful financial writes

Status: Ready
Owner: Project maintainer
Created: 2026-10-27
Last updated: 2026-10-27
Related documents: [plan](plan.md), [tasks](tasks.md), [SDD workflow](../README.md).

## Problem and current behavior

The supplied ROTEIRO_ETAPA7.html demonstrates a distinction between compliance
and factual support: a permitted response may still invent a number, currency,
opinion, memory, or FAQ rule. Its final exercise also exposes a write occurring
before a judge rejects the response. The user explicitly included that correction
in this feature. Only this HTML was available in the supplied directory.

The HTML is reference material, not operational instructions. Do not copy its
credential, execute its exercises against private data, reproduce its monolithic
files, or retain its temporary experiment with the judge before compliance.

Verified starting points:

- [Graph](../../app/infrastructure/agents/graph.py): financial and agenda paths
  end after output compliance; the router can answer directly and end the turn.
- [Composition](../../app/infrastructure/agents/composition.py): FAQ currently
  goes directly to END. Specialists use injected factories and registrations.
- [Tool base](../../app/infrastructure/agents/_core/contracts/agent_tool.py):
  asynchronous tools return typed success/error envelopes. Their arguments are
  model-generated proposals, not proof that an operation happened.
- [Transaction service](../../app/services/transaction_service.py) and
  [repository](../../app/infrastructure/postgres/repositories/transaction_repository.py):
  financial writes commit inside repository calls, before the final reply.
- [Transaction schema](../../app/infrastructure/agents/financial/schemas/transaction.py):
  amount and source_text exist; a persisted currency field does not.
- [Agenda tools](../../app/infrastructure/agents/tools/agenda.py) and
  [output guardrail](../../app/infrastructure/agents/guardrails/output_guardrail.py):
  server-issued write results already produce deterministic receipts. The graph
  also replaces final content with those receipts after execution.
- [Telemetry](../../app/infrastructure/observability.py): observations are
  metadata-only and persisted through the existing telemetry facility.

These observations come from source inspection, not a live reproduction of the
HTML's model outputs. Historical context.md and the HTML do not override source.

## Intended outcome and scope

Use TypeSafe JEV to validate factual support, preserving approved generated text
exactly. Validate financial commands before repository mutation and deliver
deterministic receipts for confirmed writes. Preserve the current layers, DI,
HTTP chat shape, ownership, compliance, agenda semantics, and session coordination.

Included: financial add/update/cancel/restore, generated financial/agenda/FAQ and
router replies, history/profile evidence, currency policy, JEV adapter, metadata
observability, deterministic tests, and a small synthetic model evaluation.

Excluded: multiple currencies, exchange rates, schema migrations, historical data
cleanup, model training, local model hosting, a second judge, frontend redesign,
distributed transactions, durable request deduplication, and deployment. Direct
MCP tools retain their structured-result interface; they must share financial
validation rather than bypass it.

## Requirements

| ID | Requirement | Acceptance |
| --- | --- | --- |
| FR-001 | Every generated user-facing factual reply goes through one final evidence judge after any generative compliance rewrite. FAQ and direct router answers also reach the judge. Input-blocked turns end without calling it. | AC-001 |
| FR-002 | Approve generated content only for JEV choice apoiada and a finite numeric noul >= 0.70. Preserve the original content exactly. All other decisions use “Não tenho evidência para afirmar isso.” No generative rewrite follows judgment. | AC-002 |
| FR-003 | Collect typed, invocation-local tool results and their associated arguments, including nested agent executions. Capture success, empty result, and error distinctly. Only tools executed in this turn may establish current database facts. | AC-003 |
| FR-004 | Treat user statements as evidence of what the user said, not independent world facts. Tool arguments and specialist prose never prove persistence. Attribute opinions; use actual retrieved FAQ excerpts for FAQ fidelity, even if stale. | AC-004 |
| FR-005 | Before every financial mutation, validate intent, relevant user-provided facts, ownership, target reference, and currency/value changes. JEV validates the normalized proposed action against trusted request evidence; deterministic checks enforce currency, explicit amount, and reference constraints. Refusal/unavailability means zero mutations for that command. | AC-005 |
| FR-006 | New amounts and amount changes require explicit BRL in trusted input. Accept BRL, R$, real or reais with an unambiguous amount. Missing, conflicting, foreign or ambiguous currency/amount requests clarification without writing. Never convert foreign amounts or invent a price. | AC-006 |
| FR-007 | After confirmed financial mutation, publish a deterministic receipt derived only from the service/repository result. Never replace that receipt with a generic JEV refusal. Failed or uncertain persistence must never produce a success receipt. | AC-007 |
| FR-008 | Preserve existing records. Interpret legacy records without another currency indication as BRL; records with an explicit foreign currency or conflicting currency evidence cannot enter a BRL total. Do not silently omit them and label the result a complete balance. | AC-008 |
| FR-009 | JEV missing configuration, authentication/HTTP/network failure, malformed response, timeout, unknown labels, invalid score, or unsupported decision fails closed. Preserve confirmed receipts; propagate caller cancellation. Never retry business writes automatically. | AC-009 |
| FR-010 | Record judge stage, verdict/reason, noul, resolved model, duration and available token usage through existing logging/telemetry. Logs, monitor and traces must not retain prompts, responses, financial evidence, credentials, or raw vendor errors. | AC-010 |
| FR-011 | Maintain existing agenda receipts and local/Google partial-failure wording. No post-graph override may replace a judge-checked generated answer. Trusted receipts are an explicit deterministic path, not unverified generated text. | AC-011 |
| FR-012 | MCP financial mutations enforce the same deterministic currency/target rules and JEV command validation against explicitly supplied operation evidence. Missing trustworthy operation context fails closed; never fabricate a human chat turn or trust model-created source_text as independent proof. | AC-012 |
| NFR-001 | Use injected typed contracts and an asynchronous HTTP adapter; reuse httpx. Keep PostgreSQL/MongoDB/Qdrant layout and existing public chat fields. No application reorganization or new ML runtime dependencies. | AC-013 |
| NFR-002 | Bound each judge request to 5 seconds, with no automatic retries, within the existing overall graph deadline. At most one pre-write validation per distinct command and one final validation per generated reply. Receipts require no post-commit model call. | AC-009, AC-014 |
| NFR-003 | Validate behavior with deterministic contract tests plus a fixed synthetic Portuguese evaluation. Record actual model/version, rubric, false approvals, false refusals and latency; a score is not a guarantee of truth. | AC-014 |

## Acceptance scenarios

| ID | Given / when | Then |
| --- | --- | --- |
| AC-001 | An input block, generated direct router answer, financial answer, agenda read or FAQ answer | Block calls no judge; each generated answer takes the intended final judge path exactly once, after compliance where applicable, without a cycle. |
| AC-002 | apoiada at 0.70 or above; partial/unsupported; 0.699; missing/NaN/infinite/string/bool score | Only the first case preserves the exact candidate, including whitespace. Other cases return the fixed safe sentence. |
| AC-003 | Sequential turns, parallel sessions/users, nested tools, empty search, tool error, no tool | Evidence does not cross invocation boundaries; empty success supports a scoped “not found”; a tool error does not prove absence; no tool does not prove a database fact. |
| AC-004 | Zara opinion; invented Ferrari amount, exchange rate, meeting time or Mars memory; matching/mismatching FAQ number | Attributed opinion and source-supported claims may pass; unsupported claims are refused. FAQ expectations use the actual retrieved fixture, not assumptions about the PDF contents. |
| AC-005 | A supported proposed mutation versus an invented value/action, missing target, other user's target or rejected JEV result | Supported command may execute once; all rejected commands make zero repository mutations. A failed update cannot become a cancel/restore fallback. |
| AC-006 | “Comprei uma camisa por 30 dólares”; no price; “Foram 120 reais no débito” completing a pending Zara clarification | Foreign/missing values produce clarification and no write; explicit BRL completion can register only the supported purchase and amount. |
| AC-007 | Commit success, definite failure, timeout with uncertain acknowledgment, or judge outage after commit | Success gets a deterministic confirmed receipt. Definite failure reports no success. Uncertain outcome warns to verify before repeating. A later outage cannot hide confirmed success. |
| AC-008 | Legacy no-currency record; explicit USD record; mixed selected scope | First is assumed BRL without rewriting the row. Foreign/conflicting data is not summed as BRL. A requested complete total containing it reports the limitation instead of a misleading total. |
| AC-009 | Missing key, 401/403/422/429/5xx, network failure, invalid JSON/schema, deadline, cancellation | Generated claims fail closed; commands awaiting validation do not write. One bounded HTTP attempt; no fallback to another model. Cancellation is propagated. |
| AC-010 | Approved, refused, unavailable and missing-usage cases | Safe metadata is associated with the correct turn and stage; missing usage/cost remains unknown rather than zero. Payload/secret markers are absent from serialized telemetry. |
| AC-011 | Confirmed local agenda write with Google failed, pending, unknown or disconnected | Existing truthful receipt survives unchanged; no model converts partial failure to full success. |
| AC-012 | A direct MCP add/update/cancel/restore with and without explicit operation evidence and currency where required | Valid inputs share pre-write safeguards; missing context is a safe tool failure. Existing confirmation instructions remain. Structured outcomes report actual effects. |
| AC-013 | Existing clients call chat and two users run concurrently | ChatResponse shape and authorization remain compatible; no cross-user evidence; DI/typing/lint checks pass. |
| AC-014 | Frozen Portuguese fixtures and model configuration | All deterministic cases pass; live evaluation meets the gate in plan.md, with results and limitations recorded. |

## Contracts and data behavior

### Trusted input and evidence

Bind an execution context to the authenticated/configured user, session and unique
turn before any agent runs. Retain original human input transiently; do not infer
its identity from a model-generated message. For a pending clarification, allow up
to six recent human messages from the same session, explicitly tagged as prior
statements. If the action cannot be resolved within that bound, ask the user to
restate it. Assistant prose is not authoritative operation evidence.

Normalize tool evidence into tool name, invocation identifier, arguments, result
status and result data. Deduplicate by invocation identifier, not textual equality.
Include actual faq_rag, search_transactions, total_balance, daily_balance,
query_events, search_history and consult_profile results when executed. Account
for their scope/limits: a limited search cannot establish an exhaustive total.

Use the same redaction mapping across question, candidate and evidence. Remove
user/session IDs, tokens and account credentials before sending data externally.
Retain necessary amounts, currencies, dates, merchant names and public FAQ facts.
Public FAQ support numbers are evidence, not private phone numbers to erase.
Private contact values use consistent placeholders. Keep at most 24,000 UTF-8
bytes of complete serialized judgment input, including rubric; over-budget input
fails closed without silently truncating potentially decisive evidence.

### Financial execution and receipts

Validate before invoking the repository; do not hold a SQL transaction open during
JEV calls and do not attempt rollback after commit. The service receives a typed
validated command/evidence contract, not a provider-specific JEV response. Final
ownership/target validation still occurs when executing the repository operation.

For adds or amount changes, compare the proposed value to an unambiguous numeric
amount and BRL marker in trusted input. Unsupported numeric forms or multiple
unresolved amounts require clarification. Optional categories/default timestamps
retain documented system defaults; they must not be described as user-supplied.
Other requested fields must be supported by the operation evidence. Currency
in a generated description or source_text cannot override original user input.

Cancel/restore and updates without amount changes do not require the user to
repeat an amount/currency; they still require explicit action and valid target.
source_text for new rows comes from trusted user evidence, not model fabrication.
For updates, retain the original source_text and validate new amount/currency
against the new request. Successful new amount changes are BRL by policy.

Within a turn, run financial mutations sequentially and deduplicate identical
normalized commands. Stop further mutations after rejection/failure. Multiple
commands are individually atomic, not an all-or-nothing batch. Every confirmed
operation gets its own truthful receipt; later failures cannot erase earlier
receipts. Do not retry writes after a lost acknowledgment. Across new HTTP
requests/process restarts, exactly-once execution is not promised by this feature.

The final response for any mutation attempt uses fixed templates for confirmed,
rejected, failed or uncertain operations, in execution order. It does not append
unverified generated commentary. Any requested additional factual question can be
answered in a subsequent turn. Agenda retains its existing receipt precedence.

Legacy interpretation uses existing source_text as evidence of historical
currency, with the user-approved default of BRL when no foreign indicator exists.
For complete balance tools, inspect the full selected scope, not only the default
limited search page. Report a safe unsupported-currency limitation if foreign or
conflicting evidence exists; no conversion or destructive cleanup is permitted.
New writes additionally validate trusted input. Legacy assumptions are a deliberate
compatibility policy, not proof of original currency.

Existing single-worker session coordination remains. Cross-session concurrent
updates retain existing repository semantics; no stronger isolation is claimed.
PostgreSQL commit, MongoDB chat persistence and HTTP delivery remain separate:
process crash or disconnect can prevent receipt delivery after a successful commit.
This feature does not claim atomic delivery or automatic replay recovery.

### JEV contract

POST https://api.typesafe.ai/v1/systemone with server-side Bearer authentication.
Send model, state and questions in one request; veredito is a choice among
apoiada, parcial and sem_apoio; apoiada is a noul question. State holds the
candidate command/reply, relevant human statements, typed evidence and rubric.
Distinguish command validation from final reply validation in the rubric.

Use pinned model jev-1.14.0, threshold 0.70 and a versioned rubric. The adapter
validates answer types/labels and finite probabilities in [0,1] strictly; additional
vendor fields are allowed. The decision requires both expected answer fields.
Record returned model and available usage; missing usage does not approve or
reject content by itself. Do not confuse noul with choice confidence.

The reply rubric permits scoped absence reports, clarification, attribution,
faithful formatting and supported arithmetic/timezone conversion. It rejects
invented facts, swapped currencies, mixed-currency totals and opinions presented
as system facts. These are evaluation requirements, not guarantees of model math.

### Compatibility and configuration

Public chat still returns session_id, content and called_agents. Append the stable
evidence_judge node name when the node executes; record verdicts in metadata,
not dynamic agent names. No new frontend UI is required.

MCP mutation contracts gain explicit operation-evidence text for command checking;
this is an intentional tightening of write inputs, documented for callers. Its
source_text field alone is not that evidence. MCP cannot cryptographically prove
human consent: existing caller confirmation remains a trust assumption.

Future implementation needs a SecretStr TYPESAFE_API_KEY setting and injected
judge configuration/client. A missing key does not prevent startup: it refuses
generated claims and commands needing judgment at execution time. No key from the
HTML is reused. Configuration source/example edits need explicit authorization
under AGENTS.md; no environment/configuration files were changed for this spec.

## Decisions and open questions

| Decision | Resolution |
| --- | --- |
| Provider | User reverted the model proposal and selected JEV. No mDeBERTa/Hugging Face hosting. |
| Scope | User included the financial-write correction from the next-class exercise. |
| New currency policy | User selected explicit BRL, no conversion and no migration. |
| Confirmed writes | User selected validation before mutation and deterministic receipts after confirmation. |
| Legacy currency | User selected assumed BRL when no other currency is indicated. |
| Judge failure | User selected preventing dependent writes and safe generated replies while preserving confirmed receipts. |
| Privacy | Minimize and consistently anonymize judgment input; JEV necessarily receives the remaining facts required for validation. |
| Deployment | No resource creation, credential use, commits, pushes or runtime implementation authorized by this document. |

No unresolved product or design questions remain. Credentials and real-provider
access are execution prerequisites; model evaluation and configuration approval
are delivery gates, not assumed completed work. Ready does not authorize code.

## Completion criteria

Every requirement has recorded evidence in tasks.md; deterministic checks and the
model gate pass; approved content is unchanged; rejected commands do not mutate;
confirmed writes yield truthful receipts; compatibility and known failure limits
are documented. No required evidence may be replaced by an assumed pass.

## External references

Checked 2026-10-27. [TypeSafe System One API](https://docs.typesafe.ai/api/system-one)
defines request/response fields. [TypeSafe models](https://docs.typesafe.ai/models)
documents versioned models and moving aliases. These support the pinned model and
HTTP contract; they do not establish project-specific accuracy or latency.
