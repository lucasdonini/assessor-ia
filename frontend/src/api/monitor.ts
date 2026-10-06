export type Usage = {
  input_tokens: number
  output_tokens: number
  known_cost_usd: number
  usage_complete: boolean
  cost_complete: boolean
}
export type ModelAttempt = {
  run_id: string; node: string; provider: string; model: string
  elapsed_ms: number; status: string; input_tokens: number | null
  output_tokens: number | null; cost_usd: number | null; fallback: boolean
}
export type Turn = {
  turn_id: string; session_id: string; ended_at: string; elapsed_ms: number
  route: string; status: string; reason: string | null; capture_complete: boolean
  detail_truncated: boolean; fallbacks: number
  nodes: { name: string; elapsed_ms: number; status: string }[]
  attempts: ModelAttempt[]
}
export type MonitorData = {
  window: { process_id: string; snapshot_at: string; uptime_seconds: number; capacity: number; sample_size: number; scope: string }
  slo: { p95_limit_ms: number; error_rate_limit: number; sample_size: number; ok: boolean | null }
  summary: {
    turns: number; eligible_turns: number; errors: number; blocked: number; cancelled: number
    in_flight: number; latency_mean_ms: number | null; latency_p95_ms: number | null
    error_rate: number | null; fallbacks: number; most_used_model: string | null; usage: Usage
  }
  turns: Turn[]
  by_model: { provider: string; model: string; attempts: number; errors: number; successful_latency_mean_ms: number | null; usage: Usage }[]
  by_route: { route: string; turns: number; errors: number; latency_mean_ms: number; usage: Usage }[]
  latency_series: { turn_id: string; timestamp: string; value: number }[]
  cost_series: { turn_id: string; timestamp: string; value: number }[]
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)
const isNumber = (value: unknown) => typeof value === 'number' && Number.isFinite(value) && value >= 0
const nullableNumber = (value: unknown) => value === null || isNumber(value)
const strings = (record: Record<string, unknown>, keys: string[]) => keys.every((key) => typeof record[key] === 'string')
const numbers = (record: Record<string, unknown>, keys: string[]) => keys.every((key) => isNumber(record[key]))
function isUsage(value: unknown): boolean {
  return isRecord(value) && numbers(value, ['input_tokens', 'output_tokens', 'known_cost_usd']) &&
    typeof value.usage_complete === 'boolean' && typeof value.cost_complete === 'boolean'
}
function validBody(body: unknown): body is MonitorData {
  if (!isRecord(body) || !isRecord(body.window) || !isRecord(body.slo) || !isRecord(body.summary)) return false
  const { window, slo, summary } = body
  if (!strings(window, ['process_id', 'snapshot_at', 'scope']) || !numbers(window, ['uptime_seconds', 'capacity', 'sample_size']) ||
    !numbers(slo, ['p95_limit_ms', 'error_rate_limit', 'sample_size']) || !(slo.ok === null || typeof slo.ok === 'boolean') ||
    !numbers(summary, ['turns', 'eligible_turns', 'errors', 'blocked', 'cancelled', 'in_flight', 'fallbacks']) ||
    !['latency_mean_ms', 'latency_p95_ms', 'error_rate'].every((key) => nullableNumber(summary[key])) ||
    !(summary.most_used_model === null || typeof summary.most_used_model === 'string') || !isUsage(summary.usage)) return false
  return Array.isArray(body.turns) && body.turns.every((turn: unknown) => isRecord(turn) &&
    strings(turn, ['turn_id', 'session_id', 'ended_at', 'route', 'status']) && isNumber(turn.elapsed_ms) &&
    ['ok', 'error', 'blocked', 'cancelled'].includes(turn.status as string) &&
    (turn.reason === null || typeof turn.reason === 'string') && typeof turn.capture_complete === 'boolean' &&
    typeof turn.detail_truncated === 'boolean' && isNumber(turn.fallbacks) &&
    Array.isArray(turn.nodes) && turn.nodes.every((node: unknown) => isRecord(node) && strings(node, ['name', 'status']) && isNumber(node.elapsed_ms)) &&
    Array.isArray(turn.attempts) && turn.attempts.every((attempt: unknown) => isRecord(attempt) &&
      strings(attempt, ['run_id', 'node', 'provider', 'model', 'status']) && isNumber(attempt.elapsed_ms) &&
      ['input_tokens', 'output_tokens', 'cost_usd'].every((key) => nullableNumber(attempt[key])) && typeof attempt.fallback === 'boolean')) &&
    Array.isArray(body.by_model) && body.by_model.every((model: unknown) => isRecord(model) && strings(model, ['provider', 'model']) &&
      numbers(model, ['attempts', 'errors']) && nullableNumber(model.successful_latency_mean_ms) && isUsage(model.usage)) &&
    Array.isArray(body.by_route) && body.by_route.every((route: unknown) => isRecord(route) && typeof route.route === 'string' &&
      numbers(route, ['turns', 'errors', 'latency_mean_ms']) && isUsage(route.usage)) &&
    [body.latency_series, body.cost_series].every((series) => Array.isArray(series) && series.every((point: unknown) =>
      isRecord(point) && strings(point, ['turn_id', 'timestamp']) && isNumber(point.value)))
}

export async function fetchMonitor(userId: string, signal: AbortSignal): Promise<MonitorData> {
  const response = await fetch('/api/monitor', { headers: { 'X-User-ID': userId }, signal })
  if (!response.ok) throw new Error('Não foi possível carregar o monitoramento.')
  const body: unknown = await response.json()
  if (!validBody(body)) throw new Error('O monitoramento retornou dados inválidos.')
  return body
}
