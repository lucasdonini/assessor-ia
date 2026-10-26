import { mutationHeaders } from './auth'

const PROFILE_ENDPOINT = '/api/profile'

export type RiskTolerance = 'LOW' | 'MEDIUM' | 'HIGH'

export type SaveProfileRequest = {
  monthly_revenue: number | null
  objective: string | null
  risk_tolerance: RiskTolerance | null
  preferences: string | null
}

export type SaveProfileResult = {
  ok: boolean
  status: number
  body: unknown
}

export async function saveProfile(
  _userId: string,
  profile: SaveProfileRequest,
): Promise<SaveProfileResult> {
  const response = await fetch(PROFILE_ENDPOINT, {
    method: 'POST',
    headers: mutationHeaders(),
    body: JSON.stringify(profile),
  })

  let body: unknown
  try {
    body = await response.json()
  } catch {
    body = { detail: 'a resposta não era JSON' }
  }

  return { ok: response.ok, status: response.status, body }
}
