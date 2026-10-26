export type Usage = {
  attempts: number; successes: number; failures: number
  input_tokens: number; output_tokens: number; total_tokens: number
  estimated_cost_usd: string; cost_complete: boolean
  missing_usage_calls: number; unpriced_calls: number
  fallbacks: number; most_used_model: string | null
}
export type MonitorSnapshot = {
  generated_at: string; process_started_at: string; uptime_seconds: number
  window_limit: number; window_turns: number; scope: 'operator_global'
  retention: 'process_window' | 'mongo_window'; price_catalog: string
  persistence?: { enabled: boolean; history_loaded: boolean; pending_writes: number; failed_writes: number; degraded: boolean }
  service: {
    completed_turns: number; in_progress: number; blocked_turns: number
    error_turns: number; cancelled_turns: number
    average_latency_ms: number | null; p95_latency_ms: number | null
    error_rate: number | null
  }
  slo: { ok: boolean | null; state: 'no_data' | 'within_target' | 'breached'; latency_limit_ms: number; error_rate_limit: number }
  usage: Usage
  turns: {
    turn_id: string; user_id: string; session_id: string; started_at: string
    elapsed_ms: number; route: string; status: string; failure_category: string | null
    nodes: { node: string; elapsed_ms: number }[]
    calls: { provider: string; model: string; node: string; elapsed_ms: number; success: boolean; input_tokens: number | null; output_tokens: number | null; usage: Usage }[]
    usage: Usage
  }[]
  models: { provider: string; model: string; usage: Usage }[]
  routes: { route: string; turns: number; average_latency_ms: number; p95_latency_ms: number; errors: number; usage: Usage }[]
  series: { turn_id: string; started_at: string; latency_ms: number; cumulative_cost_usd: string }[]
}

export class MonitorAccessError extends Error {
  readonly status: number
  constructor(status: number) {
    super(status === 401 ? 'Sua sessão expirou. Entre novamente com Google.' : 'Acesso restrito à operação.')
    this.status = status
  }
}

export async function fetchMonitor(signal?: AbortSignal): Promise<MonitorSnapshot> {
  const response = await fetch('/api/monitor', { credentials: 'same-origin', cache: 'no-store', signal })
  if (response.status === 401 || response.status === 403) throw new MonitorAccessError(response.status)
  if (!response.ok) throw new Error('Não foi possível consultar o monitoramento.')
  const value: unknown = await response.json()
  if (!value || typeof value !== 'object' || !('scope' in value) || value.scope !== 'operator_global' ||
      !('service' in value) || !value.service || typeof value.service !== 'object' ||
      !('slo' in value) || !value.slo || typeof value.slo !== 'object' ||
      !('usage' in value) || !value.usage || typeof value.usage !== 'object' ||
      !('turns' in value) || !Array.isArray(value.turns) ||
      !('models' in value) || !Array.isArray(value.models) ||
      !('routes' in value) || !Array.isArray(value.routes) ||
      !('series' in value) || !Array.isArray(value.series)) {
    throw new Error('Resposta de monitoramento inválida.')
  }
  return value as MonitorSnapshot
}
