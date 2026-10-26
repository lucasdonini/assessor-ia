import { afterEach, expect, it, vi } from 'vitest'
import { fetchMonitor, MonitorAccessError } from './monitor'

afterEach(() => vi.unstubAllGlobals())

it.each([401, 403])('handles access failure %s without returning private data', async (status) => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ status, ok: false }))
  await expect(fetchMonitor()).rejects.toBeInstanceOf(MonitorAccessError)
})

it('rejects an invalid monitor response', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ status: 200, ok: true, json: async () => ({}) }))
  await expect(fetchMonitor()).rejects.toThrow('Resposta de monitoramento inválida.')
})
