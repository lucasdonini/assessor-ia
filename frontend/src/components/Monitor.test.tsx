// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { fetchMonitor, type MonitorData } from '../api/monitor'
import { Monitor } from './Monitor'

vi.mock('../api/monitor', () => ({ fetchMonitor: vi.fn() }))

export const emptyMonitor: MonitorData = {
  window: { process_id: 'process', snapshot_at: '2026-10-06T12:00:00Z', uptime_seconds: 10, capacity: 50, sample_size: 0, scope: 'graph_turn' },
  slo: { p95_limit_ms: 8000, error_rate_limit: 0.05, sample_size: 0, ok: null },
  summary: { turns: 0, eligible_turns: 0, errors: 0, blocked: 0, cancelled: 0, in_flight: 0, latency_mean_ms: null, latency_p95_ms: null, error_rate: null, fallbacks: 0, most_used_model: null, usage: { input_tokens: 0, output_tokens: 0, known_cost_usd: 0, usage_complete: true, cost_complete: true } },
  turns: [], by_model: [], by_route: [], latency_series: [], cost_series: [],
}

afterEach(() => { cleanup(); vi.useRealTimers(); vi.resetAllMocks() })

it('shows the empty window, polls without overlap, and cleans up', async () => {
  vi.useFakeTimers()
  vi.mocked(fetchMonitor).mockResolvedValue(emptyMonitor)
  let view!: ReturnType<typeof render>
  await act(async () => { view = render(<Monitor userId="a" onBack={vi.fn()} />) })
  expect(screen.getByText('Sem amostras para avaliar o SLO')).toBeTruthy()
  expect(fetchMonitor).toHaveBeenCalledTimes(1)
  await act(async () => { await vi.advanceTimersByTimeAsync(4000) })
  expect(fetchMonitor).toHaveBeenCalledTimes(2)
  view.unmount()
  await act(async () => { await vi.advanceTimersByTimeAsync(8000) })
  expect(fetchMonitor).toHaveBeenCalledTimes(2)
})

it('retains a stale snapshot and allows a manual retry', async () => {
  vi.mocked(fetchMonitor).mockResolvedValueOnce(emptyMonitor).mockRejectedValueOnce(new Error('PRIVATE')).mockResolvedValue(emptyMonitor)
  render(<Monitor userId="a" onBack={vi.fn()} />)
  await act(async () => {})
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Atualizar' })) })
  expect(screen.getByRole('alert').textContent).toContain('desatualizados')
  expect(screen.queryByText('PRIVATE')).toBeNull()
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Atualizar' })) })
  expect(screen.queryByRole('alert')).toBeNull()
})

it('aborts and ignores previous-user responses and prevents overlapping refreshes', async () => {
  let resolve!: (data: MonitorData) => void
  vi.mocked(fetchMonitor).mockImplementationOnce(() => new Promise((done) => { resolve = done })).mockResolvedValue(emptyMonitor)
  const view = render(<Monitor userId="a" onBack={vi.fn()} />)
  fireEvent.click(screen.getByRole('button', { name: 'Atualizar' }))
  expect(fetchMonitor).toHaveBeenCalledTimes(1)
  const signal = vi.mocked(fetchMonitor).mock.calls[0][1]
  await act(async () => { view.rerender(<Monitor userId="b" onBack={vi.fn()} />) })
  expect(signal.aborted).toBe(true)
  await act(async () => { resolve({ ...emptyMonitor, summary: { ...emptyMonitor.summary, most_used_model: 'FOREIGN MODEL' } }) })
  expect(screen.queryByText('FOREIGN MODEL')).toBeNull()
  expect(fetchMonitor).toHaveBeenLastCalledWith('b', expect.any(AbortSignal))
})

it('renders untrusted session and model names as text', async () => {
  const injection = '<img src=x onerror=alert(1)>'
  vi.mocked(fetchMonitor).mockResolvedValue({ ...emptyMonitor, summary: { ...emptyMonitor.summary, most_used_model: injection } })
  render(<Monitor userId="a" onBack={vi.fn()} />)
  expect(await screen.findByText(injection)).toBeTruthy()
  expect(document.querySelector('img')).toBeNull()
})
