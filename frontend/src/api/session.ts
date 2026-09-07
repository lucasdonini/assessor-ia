const SESSION_ENDPOINT = '/api/session'

export type SessionFinalizationResponse = {
  session_id: string
  session_summary: string | null
}

export async function finalizeSession(
  sessionId: string,
  userId: string,
): Promise<SessionFinalizationResponse> {
  let apiResponse: Response

  try {
    apiResponse = await fetch(
      `${SESSION_ENDPOINT}/${encodeURIComponent(sessionId)}/finalize`,
      { method: 'POST', headers: { 'X-User-ID': userId } },
    )
  } catch {
    throw new Error('Não foi possível conectar ao assistente.')
  }

  if (!apiResponse.ok) {
    throw new Error('Não foi possível encerrar a sessão.')
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
    session_summary: sessionSummary,
  } = responseBody as Record<string, unknown>
  if (
    typeof responseSessionId !== 'string' ||
    responseSessionId !== sessionId ||
    (typeof sessionSummary !== 'string' && sessionSummary !== null)
  ) {
    throw new Error('O assistente retornou uma resposta em formato inválido.')
  }

  return {
    session_id: responseSessionId,
    session_summary: sessionSummary,
  }
}
