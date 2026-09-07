import { afterEach, describe, expect, it, vi } from 'vitest'
import { sendChatMessage } from './chat'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('sendChatMessage', () => {
  it('envia a mensagem e devolve a resposta textual', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          session_id: 'session-123',
          content: 'Resposta do assistente',
          called_agents: ['input_guardrail', 'router', 'financial', 'output_guardrail'],
        }),
        {
          status: 200,
          headers: { 'Content-Type': 'application/json', 'X-User-ID': 'user-123' },
        },
      ),
    )
    vi.stubGlobal('fetch', fetchMock)

    await expect(
      sendChatMessage('session-123', 'user-123', 'Minha pergunta'),
    ).resolves.toEqual({
      session_id: 'session-123',
      content: 'Resposta do assistente',
      called_agents: ['input_guardrail', 'router', 'financial', 'output_guardrail'],
    })
    expect(fetchMock).toHaveBeenCalledWith('/api/chat/session-123', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-User-ID': 'user-123' },
      body: JSON.stringify({ message: 'Minha pergunta' }),
    })
  })

  it('codifica o identificador da sessão antes de montar a URL', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          session_id: 'sessão 123',
          content: 'Resposta',
          called_agents: [],
        }),
        { status: 200 },
      ),
    )
    vi.stubGlobal('fetch', fetchMock)

    await sendChatMessage('sessão 123', 'user-123', 'Minha pergunta')

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/chat/sess%C3%A3o%20123',
      expect.any(Object),
    )
  })

  it('traduz falha de rede para uma mensagem pública', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')))

    await expect(
      sendChatMessage('session-123', 'user-123', 'Minha pergunta'),
    ).rejects.toThrow(
      'Não foi possível conectar ao assistente.',
    )
  })

  it('traduz resposta HTTP malsucedida para uma mensagem pública', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 500 })))

    await expect(
      sendChatMessage('session-123', 'user-123', 'Minha pergunta'),
    ).rejects.toThrow(
      'Não foi possível obter uma resposta do assistente.',
    )
  })

  it.each([undefined, null, 'financial', [42], [''], ['  ']])(
    'rejeita metadados de agentes inválidos: %j', async (calledAgents) => {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
        session_id: 'session-123', content: 'Resposta', called_agents: calledAgents,
      }), { status: 200 })))

      await expect(sendChatMessage('session-123', 'user-123', 'Pergunta')).rejects.toThrow(
        'O assistente retornou uma resposta em formato inválido.',
      )
    },
  )

  it.each([
    new Response('conteúdo inválido', { status: 200 }),
    new Response(JSON.stringify({ session_id: 'session-123' }), {
      status: 200,
      headers: { 'Content-Type': 'application/json', 'X-User-ID': 'user-123' },
    }),
    new Response(
      JSON.stringify({ session_id: 'outra-sessão', content: 'texto' }),
      {
        status: 200,
        headers: { 'Content-Type': 'application/json', 'X-User-ID': 'user-123' },
      },
    ),
    new Response(JSON.stringify({ session_id: 'session-123', content: 1 }), {
      status: 200,
      headers: { 'Content-Type': 'application/json', 'X-User-ID': 'user-123' },
    }),
  ])('rejeita resposta em formato inesperado', async (response) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response))

    await expect(
      sendChatMessage('session-123', 'user-123', 'Minha pergunta'),
    ).rejects.toThrow(
      'O assistente retornou uma resposta em formato inválido.',
    )
  })
})
