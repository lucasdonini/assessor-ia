const CHAT_ENDPOINT = '/api/chat'

type ChatRequest = {
  message: string
}

export type ChatResponse = {
  session_id: string
  content: string
  called_agents: string[]
}

export async function sendChatMessage(
  sessionId: string,
  userId: string,
  message: string,
): Promise<ChatResponse> {
  let apiResponse: Response

  try {
    apiResponse = await fetch(
      `${CHAT_ENDPOINT}/${encodeURIComponent(sessionId)}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-User-ID': userId },
        body: JSON.stringify({ message } satisfies ChatRequest),
      },
    )
  } catch {
    throw new Error('Não foi possível conectar ao assistente.')
  }

  if (!apiResponse.ok) {
    throw new Error('Não foi possível obter uma resposta do assistente.')
  }

  let responseBody: unknown

  try {
    responseBody = await apiResponse.json()
  } catch {
    throw new Error('O assistente retornou uma resposta em formato inválido.')
  }

  if (typeof responseBody !== 'object' || responseBody === null) {
    throw new Error('O assistente retornou uma resposta em formato inválido.')
  }

  const {
    session_id: responseSessionId,
    content,
    called_agents,
  } = responseBody as Record<string, unknown>
  if (
    typeof responseSessionId !== 'string' ||
    responseSessionId !== sessionId ||
    typeof content !== 'string' ||
    !Array.isArray(called_agents) ||
    !called_agents.every(
      (agent: unknown) => typeof agent === 'string' && agent.trim().length > 0,
    )
  ) {
    throw new Error('O assistente retornou uma resposta em formato inválido.')
  }

  return { session_id: responseSessionId, content, called_agents }
}
