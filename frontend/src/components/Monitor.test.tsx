// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fetchMonitor, MonitorAccessError, type MonitorSnapshot, type Usage } from '../api/monitor'
import { Monitor } from './Monitor'

vi.mock('../api/monitor', async (original) => ({ ...await original<typeof import('../api/monitor')>(), fetchMonitor: vi.fn() }))

const usage: Usage = { attempts: 0, successes: 0, failures: 0, input_tokens: 0, output_tokens: 0, total_tokens: 0, estimated_cost_usd: '0', cost_complete: true, missing_usage_calls: 0, unpriced_calls: 0, fallbacks: 0, most_used_model: null }
const empty: MonitorSnapshot = {
  generated_at: '2026-10-26T15:00:00Z', process_started_at: '2026-10-26T14:00:00Z', uptime_seconds: 3600,
  window_limit: 50, window_turns: 0, scope: 'operator_global', retention: 'process_window', price_catalog: '2026-10-26-standard-usd',
  service: { completed_turns: 0, in_progress: 0, blocked_turns: 0, error_turns: 0, cancelled_turns: 0, average_latency_ms: null, p95_latency_ms: null, error_rate: null },
  slo: { ok: null, state: 'no_data', latency_limit_ms: 8000, error_rate_limit: 0.05 },
  usage, turns: [], models: [], routes: [], series: [],
}

beforeEach(() => {
  vi.useFakeTimers()
  vi.spyOn(document, 'hidden', 'get').mockReturnValue(false)
  vi.mocked(fetchMonitor).mockResolvedValue(empty)
})
afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks(); vi.resetAllMocks() })

async function open() { await act(async () => { render(<Monitor onBack={vi.fn()} />) }) }

describe('Monitor', () => {
  it('shows no data, refreshes every four seconds and cleans up timers', async () => {
    await open()
    expect(screen.getByText('Sem turnos para avaliar o SLO.')).toBeTruthy()
    expect(fetchMonitor).toHaveBeenCalledTimes(1)
    await act(async () => { vi.advanceTimersByTime(4000) })
    expect(fetchMonitor).toHaveBeenCalledTimes(2)
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Atualizar' })) })
    expect(fetchMonitor).toHaveBeenCalledTimes(3)
    cleanup()
    await act(async () => { vi.advanceTimersByTime(8000) })
    expect(fetchMonitor).toHaveBeenCalledTimes(3)
  })

  it('keeps stale data on failure and clears it on expired login', async () => {
    await open()
    vi.mocked(fetchMonitor).mockRejectedValueOnce(new Error('Indisponível'))
    await act(async () => { vi.advanceTimersByTime(4000) })
    expect(screen.getByRole('alert').textContent).toContain('Dados desatualizados')
    expect(screen.getByText('Sem turnos para avaliar o SLO.')).toBeTruthy()
    vi.mocked(fetchMonitor).mockRejectedValueOnce(new MonitorAccessError(401))
    await act(async () => { vi.advanceTimersByTime(4000) })
    expect(screen.getByRole('alert').textContent).toContain('Sua sessão expirou')
    expect(screen.queryByText('Sem turnos para avaliar o SLO.')).toBeNull()
    await act(async () => { vi.advanceTimersByTime(8000) })
    expect(fetchMonitor).toHaveBeenCalledTimes(3)
  })

  it('does not overlap requests, pauses hidden tabs and aborts on unmount', async () => {
    let resolve!: (value: MonitorSnapshot) => void
    vi.mocked(fetchMonitor).mockReturnValueOnce(new Promise(r => { resolve = r }))
    await open()
    await act(async () => { vi.advanceTimersByTime(12000) })
    expect(fetchMonitor).toHaveBeenCalledTimes(1)
    await act(async () => { resolve(empty) })
    vi.spyOn(document, 'hidden', 'get').mockReturnValue(true)
    await act(async () => { vi.advanceTimersByTime(8000) })
    expect(fetchMonitor).toHaveBeenCalledTimes(1)
    vi.spyOn(document, 'hidden', 'get').mockReturnValue(false)
    vi.mocked(fetchMonitor).mockReturnValueOnce(new Promise(() => {}))
    await act(async () => { document.dispatchEvent(new Event('visibilitychange')) })
    const signal = vi.mocked(fetchMonitor).mock.calls[1][0]
    cleanup()
    expect(signal?.aborted).toBe(true)
  })

  it('renders populated charts, diagnostic nodes and partial price labels', async () => {
    vi.mocked(fetchMonitor).mockResolvedValue({ ...empty,
      service: { ...empty.service, completed_turns: 1, average_latency_ms: 9000, p95_latency_ms: 9000, error_rate: 0 },
      slo: { ...empty.slo, ok: false, state: 'breached' },
      usage: { ...usage, unpriced_calls: 1, cost_complete: false },
      turns: [{ turn_id: 'turn', user_id: 'owner', session_id: 'session', started_at: empty.generated_at, elapsed_ms: 9000, route: 'financial', status: 'ok', failure_category: null, nodes: [{ node: 'financial', elapsed_ms: 9000 }], calls: [], usage }],
      series: [{ turn_id: 'turn', started_at: empty.generated_at, latency_ms: 9000, cumulative_cost_usd: '0' }],
    })
    await open()
    expect(screen.getByText('SLO fora do objetivo')).toBeTruthy()
    expect(screen.getAllByRole('img')).toHaveLength(2)
    expect(screen.getByText(/Estimativa parcial:/)).toBeTruthy()
    expect(screen.getByText('Nós e chamadas')).toBeTruthy()
  })
})
