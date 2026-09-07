export type User = { id: string; created_at: string }

function parseUser(value: unknown): User {
  if (typeof value !== 'object' || value === null ||
      !('id' in value) || typeof value.id !== 'string' ||
      !('created_at' in value) || typeof value.created_at !== 'string') {
    throw new Error('O servidor retornou um usuário inválido.')
  }
  return { id: value.id, created_at: value.created_at }
}

export async function listUsers(): Promise<User[]> {
  const response = await fetch('/api/users')
  if (!response.ok) throw new Error('Não foi possível carregar os usuários.')
  const body: unknown = await response.json()
  if (!Array.isArray(body)) throw new Error('Lista de usuários inválida.')
  return body.map(parseUser)
}

export async function createUser(): Promise<User> {
  const response = await fetch('/api/users', { method: 'POST' })
  if (!response.ok) throw new Error('Não foi possível criar o usuário.')
  return parseUser(await response.json())
}
