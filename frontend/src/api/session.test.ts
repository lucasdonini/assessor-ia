import { afterEach, describe, expect, it, vi } from 'vitest'
import { finalizeSession } from './session'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('finalizeSession', () => {
  it('encerra a sessão e devolve seu resumo', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          session_id: 'session-123',
          session_summary: 'Resumo da sessão',
        }),
        { status: 200 },
      ),
    )
    vi.stubGlobal('fetch', fetchMock)

    await expect(finalizeSession('session-123', 'user-123')).resolves.toEqual({
      session_id: 'session-123',
      session_summary: 'Resumo da sessão',
    })
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/session/session-123/finalize',
      { method: 'POST', headers: { 'X-User-ID': 'user-123' } },
    )
  })

  it('aceita resumo nulo para uma sessão sem mensagens', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({ session_id: 'session-123', session_summary: null }),
          { status: 200 },
        ),
      ),
    )

    await expect(finalizeSession('session-123', 'user-123')).resolves.toEqual({
      session_id: 'session-123',
      session_summary: null,
    })
  })

  it('codifica o identificador antes de montar a URL', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ session_id: 'sessão 123', session_summary: null }),
        { status: 200 },
      ),
    )
    vi.stubGlobal('fetch', fetchMock)

    await finalizeSession('sessão 123', 'user-123')

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/session/sess%C3%A3o%20123/finalize',
      { method: 'POST', headers: { 'X-User-ID': 'user-123' } },
    )
  })

  it('traduz falha de rede para uma mensagem pública', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')))

    await expect(finalizeSession('session-123', 'user-123')).rejects.toThrow(
      'Não foi possível conectar ao assistente.',
    )
  })

  it('traduz resposta HTTP malsucedida para uma mensagem pública', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response(null, { status: 500 })),
    )

    await expect(finalizeSession('session-123', 'user-123')).rejects.toThrow(
      'Não foi possível encerrar a sessão.',
    )
  })

  it.each([
    new Response('conteúdo inválido', { status: 200 }),
    new Response(JSON.stringify({ session_id: 'session-123' }), { status: 200 }),
    new Response(
      JSON.stringify({ session_id: 'outra-sessão', session_summary: null }),
      { status: 200 },
    ),
    new Response(
      JSON.stringify({ session_id: 'session-123', session_summary: 1 }),
      { status: 200 },
    ),
  ])('rejeita resposta em formato inesperado', async (response) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response))

    await expect(finalizeSession('session-123', 'user-123')).rejects.toThrow(
      'O assistente retornou uma resposta em formato inválido.',
    )
  })
})
