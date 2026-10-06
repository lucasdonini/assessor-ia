import { afterEach, expect, it, vi } from 'vitest'
import { fetchMonitor } from './monitor'

afterEach(() => { vi.unstubAllGlobals() })

it('uses the user header and cancellation signal', async () => {
  const fetch = vi.fn().mockResolvedValue({ ok: false })
  vi.stubGlobal('fetch', fetch)
  const signal = new AbortController().signal
  await expect(fetchMonitor('owner', signal)).rejects.toThrow('Não foi possível')
  expect(fetch).toHaveBeenCalledWith('/api/monitor', { headers: { 'X-User-ID': 'owner' }, signal })
})

it('rejects malformed monitor responses', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ window: {}, slo: {}, summary: {}, turns: [] }) }))
  await expect(fetchMonitor('owner', new AbortController().signal)).rejects.toThrow('dados inválidos')
})
