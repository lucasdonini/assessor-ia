import { afterEach, describe, expect, it, vi } from 'vitest'
import { saveProfile, type SaveProfileRequest } from './profile'

afterEach(() => {
  vi.unstubAllGlobals()
})

const PROFILE: SaveProfileRequest = {
  monthly_revenue: 4200,
  objective: 'Save for a trip',
  risk_tolerance: 'LOW',
  preferences: 'No aggressive investments.',
}

describe('saveProfile', () => {
  it('sends the selected user in the header and profile data in the body', async () => {
    const responseBody = { user_id: 'user-123', ...PROFILE }
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(responseBody), { status: 200 }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await expect(saveProfile('user-123', PROFILE)).resolves.toEqual({
      ok: true,
      status: 200,
      body: responseBody,
    })
    expect(fetchMock).toHaveBeenCalledWith('/api/profile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-User-ID': 'user-123' },
      body: JSON.stringify(PROFILE),
    })
  })

  it('keeps the HTTP error body available to the profile screen', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response('not json', { status: 422 })),
    )

    await expect(saveProfile('user-123', PROFILE)).resolves.toEqual({
      ok: false,
      status: 422,
      body: { detail: 'a resposta não era JSON' },
    })
  })
})
