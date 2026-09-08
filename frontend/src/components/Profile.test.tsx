// @vitest-environment jsdom

import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { saveProfile } from '../api/profile'
import { Profile } from './Profile'

vi.mock('../api/profile', () => ({ saveProfile: vi.fn() }))

afterEach(() => {
  cleanup()
  vi.resetAllMocks()
})

it('preserves the form behavior while using the English API contract', async () => {
  const user = userEvent.setup()
  vi.mocked(saveProfile).mockResolvedValue({
    ok: true,
    status: 200,
    body: { user_id: 'user-123' },
  })
  render(<Profile userId="user-123" onBack={vi.fn()} />)

  await user.type(screen.getByLabelText('renda mensal'), '4200')
  await user.type(screen.getByLabelText('objetivo'), 'juntar para viagem')
  await user.selectOptions(screen.getByLabelText('tolerância a risco'), 'LOW')
  await user.type(screen.getByLabelText('preferências'), 'não quero risco agressivo')
  await user.click(screen.getByRole('button', { name: 'salvar perfil' }))

  expect(saveProfile).toHaveBeenCalledWith('user-123', {
    monthly_revenue: 4200,
    objective: 'juntar para viagem',
    risk_tolerance: 'LOW',
    preferences: 'não quero risco agressivo',
  })
  expect(await screen.findByText('perfil salvo')).toBeTruthy()
  expect(screen.getAllByText(/user-123/)).toHaveLength(2)
})

it('sends null for empty fields so the API owns validation', async () => {
  const user = userEvent.setup()
  vi.mocked(saveProfile).mockResolvedValue({
    ok: false,
    status: 422,
    body: { detail: 'invalid fields' },
  })
  render(<Profile userId="user-123" onBack={vi.fn()} />)

  await user.click(screen.getByRole('button', { name: 'salvar perfil' }))

  expect(saveProfile).toHaveBeenCalledWith('user-123', {
    monthly_revenue: null,
    objective: null,
    risk_tolerance: null,
    preferences: null,
  })
  expect(await screen.findByText('a api recusou (422)')).toBeTruthy()
})
