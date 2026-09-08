import { type FormEvent, useState } from 'react'
import {
  type RiskTolerance,
  type SaveProfileRequest,
  saveProfile,
} from '../api/profile'
import './Profile.css'

type StatusKind = 'ok' | 'error' | null

type ProfileProps = Readonly<{
  userId: string
  onBack: () => void
}>

export function Profile({ userId, onBack }: ProfileProps) {
  const [monthlyRevenue, setMonthlyRevenue] = useState('')
  const [objective, setObjective] = useState('')
  const [riskTolerance, setRiskTolerance] = useState<RiskTolerance | ''>('')
  const [preferences, setPreferences] = useState('')
  const [status, setStatus] = useState('nada enviado ainda')
  const [statusKind, setStatusKind] = useState<StatusKind>(null)
  const [responseBody, setResponseBody] = useState<unknown>(null)
  const [submitting, setSubmitting] = useState(false)

  function buildPayload(): SaveProfileRequest {
    const revenue = monthlyRevenue.trim()
    return {
      monthly_revenue: revenue === '' ? null : Number(revenue),
      objective: objective.trim() || null,
      risk_tolerance: riskTolerance || null,
      preferences: preferences.trim() || null,
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSubmitting(true)
    setStatus('enviando...')
    setStatusKind(null)
    setResponseBody(null)

    try {
      const result = await saveProfile(userId, buildPayload())
      setResponseBody(result.body)
      if (!result.ok) {
        setStatus(`a api recusou (${result.status})`)
        setStatusKind('error')
        return
      }
      setStatus('perfil salvo')
      setStatusKind('ok')
    } catch (error: unknown) {
      setStatus('não consegui falar com a api')
      setStatusKind('error')
      setResponseBody({ erro: String(error) })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="profile-page">
      <form className="sheet" onSubmit={handleSubmit}>
        <header className="sheet__header">
          <div className="sheet__identity">
            <span className="sheet__dot" aria-hidden="true" />
            <h1 className="sheet__title">perfil</h1>
          </div>
          <div className="sheet__meta">
            <span className="sheet__label">user</span>
            <span className="sheet__user" title={userId}>{userId.slice(0, 8)}…</span>
            <button className="sheet__back" type="button" onClick={onBack}>
              voltar ao chat
            </button>
          </div>
        </header>

        <div className="sheet__body">
          <p className="sheet__intro">
            Estes dados ficam salvos e valem para todas as conversas. O assessor lê
            este cadastro quando precisa aconselhar. O chat não altera nada daqui.
          </p>

          <div className="field">
            <label className="field__label" htmlFor="monthly_revenue">renda mensal</label>
            <input
              className="field__control"
              type="number"
              id="monthly_revenue"
              name="monthly_revenue"
              min="0"
              step="0.01"
              placeholder="4200"
              value={monthlyRevenue}
              onChange={(event) => setMonthlyRevenue(event.target.value)}
            />
          </div>

          <div className="field">
            <label className="field__label" htmlFor="objective">objetivo</label>
            <input
              className="field__control"
              type="text"
              id="objective"
              name="objective"
              maxLength={120}
              placeholder="juntar para viagem em dezembro"
              value={objective}
              onChange={(event) => setObjective(event.target.value)}
            />
          </div>

          <div className="field">
            <label className="field__label" htmlFor="risk_tolerance">tolerância a risco</label>
            <select
              className="field__select"
              id="risk_tolerance"
              name="risk_tolerance"
              value={riskTolerance}
              onChange={(event) => setRiskTolerance(event.target.value as RiskTolerance | '')}
            >
              <option value="">selecione</option>
              <option value="LOW">baixa</option>
              <option value="MEDIUM">média</option>
              <option value="HIGH">alta</option>
            </select>
          </div>

          <div className="field">
            <label className="field__label" htmlFor="preferences">preferências</label>
            <textarea
              className="field__area"
              id="preferences"
              name="preferences"
              placeholder="quero juntar para uma viagem a João Pessoa em dezembro; não quero investimento agressivo."
              value={preferences}
              onChange={(event) => setPreferences(event.target.value)}
            />
            <span className="field__hint">
              Texto livre. Escreva planos, restrições e gostos em frases normais.
            </span>
          </div>
        </div>

        <footer className="sheet__footer">
          <p className={'sheet__status' + (statusKind ? ` is-${statusKind}` : '')} role="status">
            {status}
          </p>
          <button className="sheet__submit" type="submit" disabled={submitting}>
            salvar perfil
          </button>
        </footer>
      </form>

      {responseBody !== null && (
        <section className="echo">
          <p className="echo__label">resposta da api</p>
          <pre className="echo__body">{JSON.stringify(responseBody, null, 2)}</pre>
        </section>
      )}
    </div>
  )
}
