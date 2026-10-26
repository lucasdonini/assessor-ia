export type Account = { id: string; email: string; csrf: string; can_monitor?: boolean }
export type CalendarConnection = {
  connected: boolean; email: string | null; reconnect_required: boolean
}

let csrf = ''

export function mutationHeaders(): Record<string, string> {
  return { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }
}

export async function currentAccount(): Promise<Account | null> {
  const response = await fetch('/api/auth/me', { credentials: 'same-origin' })
  if (response.status === 401) { csrf = ''; return null }
  if (!response.ok) throw new Error('Não foi possível verificar a conta.')
  const value: unknown = await response.json()
  if (!value || typeof value !== 'object' || !('id' in value) ||
      typeof value.id !== 'string' || !('email' in value) ||
      typeof value.email !== 'string' || !('csrf' in value) || typeof value.csrf !== 'string') {
    throw new Error('Resposta de autenticação inválida.')
  }
  csrf = value.csrf
  return { id: value.id, email: value.email, csrf, can_monitor: 'can_monitor' in value && value.can_monitor === true }
}

export async function logout(): Promise<void> {
  const response = await fetch('/api/auth/logout', { method: 'POST', headers: mutationHeaders() })
  if (!response.ok) throw new Error('Não foi possível sair.')
  csrf = ''
}

export async function calendarConnection(): Promise<CalendarConnection> {
  const response = await fetch('/api/calendar/connection')
  if (!response.ok) throw new Error('Não foi possível consultar o vínculo Google.')
  return response.json() as Promise<CalendarConnection>
}

export async function connectCalendar(): Promise<void> {
  const response = await fetch('/api/calendar/google/connect', {
    method: 'POST', headers: mutationHeaders(),
  })
  if (!response.ok) throw new Error('Não foi possível iniciar a conexão Google.')
  const result = await response.json() as { url: string }
  const destination = new URL(result.url)
  if (destination.origin !== 'https://accounts.google.com') throw new Error('Destino OAuth inválido.')
  window.location.assign(destination.href)
}

export async function disconnectCalendar(): Promise<void> {
  const response = await fetch('/api/calendar/connection', { method: 'DELETE', headers: mutationHeaders() })
  if (!response.ok) throw new Error('Não foi possível desconectar o calendário.')
}

export type EventProposal = {
  operation_id: string
  proposal: { title: string; start_time: string; end_time: string }
  conflicts: { id: string; title: string; start_time: string; end_time: string }[]
  requires_confirmation: boolean
  event: { id: string } | null
  google: { state: 'not_connected' | 'pending' | 'succeeded' | 'failed' | 'unknown' }
}

export async function eventProposals(): Promise<EventProposal[]> {
  const response = await fetch('/api/agenda/proposals')
  if (!response.ok) throw new Error('Não foi possível consultar propostas pendentes.')
  return response.json() as Promise<EventProposal[]>
}

export async function confirmProposal(id: string): Promise<EventProposal> {
  const response = await fetch(`/api/agenda/proposals/${encodeURIComponent(id)}/confirm`, {
    method: 'POST', headers: mutationHeaders(),
  })
  if (!response.ok) throw new Error('Proposta expirada ou indisponível. Solicite novamente.')
  return response.json() as Promise<EventProposal>
}
