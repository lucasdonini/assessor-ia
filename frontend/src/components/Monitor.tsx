import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchMonitor, MonitorAccessError, type MonitorSnapshot } from '../api/monitor'
import './Monitor.css'

const number = (value: number | null | undefined, suffix = '') => value == null ? '—' : `${value.toLocaleString('pt-BR', { maximumFractionDigits: 2 })}${suffix}`
const usd = (value: string) => Number(value).toLocaleString('pt-BR', { style: 'currency', currency: 'USD', minimumFractionDigits: 6 })
const time = (value: string) => new Date(value).toLocaleString('pt-BR')

function Chart({ title, values, labels, threshold, money = false }: {
  title: string; values: number[]; labels: string[]; threshold?: number; money?: boolean
}) {
  const max = Math.max(...values, threshold ?? 0, 0.000001)
  const x = (i: number) => 45 + i * 700 / Math.max(values.length - 1, 1)
  const y = (v: number) => 170 - v / max * 140
  return <figure className="monitor__chart"><figcaption>{title}</figcaption>
    {values.length ? <svg viewBox="0 0 800 210" role="img" aria-label={title}>
      <text x="4" y="20">{money ? usd(String(max)) : number(max, ' ms')}</text>
      <path d="M45 25V170H755" className="monitor__axis" />
      {threshold !== undefined && <><path d={`M45 ${y(threshold)}H755`} className="monitor__limit" /><text x="650" y={y(threshold) - 5}>Limite: 8 s</text></>}
      <polyline points={values.map((v, i) => `${x(i)},${y(v)}`).join(' ')} />
      {values.map((v, i) => <circle key={i} cx={x(i)} cy={y(v)} r="3"><title>{labels[i]} · {money ? usd(String(v)) : number(v, ' ms')}</title></circle>)}
      <text x="45" y="198">Mais antigo</text><text x="655" y="198">Mais recente</text>
    </svg> : <p>Sem turnos nesta execução.</p>}
  </figure>
}

export function Monitor({ onBack }: { onBack: () => void }) {
  const [snapshot, setSnapshot] = useState<MonitorSnapshot | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const active = useRef(false)
  const pending = useRef<AbortController | null>(null)
  const forbidden = useRef(false)

  const refresh = useCallback(async () => {
    if (!active.current || pending.current || forbidden.current || document.hidden) return
    const controller = new AbortController()
    pending.current = controller
    setBusy(true)
    try {
      const result = await fetchMonitor(controller.signal)
      if (active.current && !controller.signal.aborted) { setSnapshot(result); setError('') }
    } catch (cause: unknown) {
      if (active.current && !controller.signal.aborted) {
        if (cause instanceof MonitorAccessError) {
          forbidden.current = true
          setSnapshot(null)
        }
        setError(cause instanceof Error ? cause.message : 'Monitoramento indisponível.')
      }
    } finally {
      if (pending.current === controller) {
        pending.current = null
        if (active.current) setBusy(false)
      }
    }
  }, [])

  useEffect(() => {
    active.current = true
    void refresh()
    const timer = window.setInterval(() => void refresh(), 4000)
    const visible = () => { if (!document.hidden) void refresh() }
    document.addEventListener('visibilitychange', visible)
    return () => {
      active.current = false
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', visible)
      pending.current?.abort()
      pending.current = null
    }
  }, [refresh])

  const service = snapshot?.service
  const usage = snapshot?.usage
  const metrics: [string, string][] = service && usage ? [
    ['Turnos', number(service.completed_turns)], ['Em andamento', number(service.in_progress)],
    ['Bloqueios', number(service.blocked_turns)], ['Erros', number(service.error_turns)],
    ['Cancelamentos', number(service.cancelled_turns)],
    ['Taxa de erro', service.error_rate === null ? '—' : number(service.error_rate * 100, '%')],
    ['Latência média', number(service.average_latency_ms, ' ms')], ['Latência p95', number(service.p95_latency_ms, ' ms')],
    ['No ar', number(snapshot?.uptime_seconds, ' s')],
    ['Tokens de entrada', number(usage.input_tokens)], ['Tokens de saída', number(usage.output_tokens)],
    ['Tokens totais', number(usage.total_tokens)], ['Custo conhecido', usd(usage.estimated_cost_usd)],
    ['Modelo mais usado', usage.most_used_model ?? '—'], ['Tentativas de modelo', number(usage.attempts)],
    ['Fallbacks', number(usage.fallbacks)],
  ] : []

  return <section className="monitor" aria-label="Monitoramento operacional">
    <header className="monitor__header"><div><p className="monitor__eyebrow">OPERAÇÃO · VISÃO GLOBAL</p><h1>Monitoramento</h1></div>
      <div><button className="header__reset" onClick={onBack}>Conversa</button>{' '}
        <button className="header__reset" disabled={busy || forbidden.current} onClick={() => void refresh()}>Atualizar</button></div>
    </header>
    <p>Últimos 50 turnos concluídos do processo, de todos os usuários. Reiniciar o servidor zera este registro.</p>
    {error && <p role="alert" className="monitor__error">{error}{snapshot ? ' Dados desatualizados; exibindo a última consulta bem-sucedida.' : ''}</p>}
    {!snapshot && !error && <p role="status">Carregando monitoramento…</p>}
    {snapshot && <>
      <div className={`monitor__slo monitor__slo--${snapshot.slo.state}`} role="status">
        {snapshot.slo.state === 'no_data' ? 'Sem turnos para avaliar o SLO.' : snapshot.slo.ok ? 'SLO dentro do objetivo' : 'SLO fora do objetivo'}
        <small>p95 ≤ {number(snapshot.slo.latency_limit_ms, ' ms')} · erros ≤ {number(snapshot.slo.error_rate_limit * 100, '%')}</small>
      </div>
      <p>Última atualização: {time(snapshot.generated_at)} · Início do processo: {time(snapshot.process_started_at)}</p>
      <div className="monitor__metrics">{metrics.map(([label, value]) => <article key={label}><span>{label}</span><strong>{value}</strong></article>)}</div>
      <p>Estimativa por tabela fixa ({snapshot.price_catalog}), sem descontos de cache; não é a fatura. Custo acumulado apenas na janela retida.</p>
      {!snapshot.usage.cost_complete && <p className="monitor__warning">Estimativa parcial: {snapshot.usage.unpriced_calls} chamadas sem preço confirmado e {snapshot.usage.missing_usage_calls} sem uso completo. Valores desconhecidos não são custo zero.</p>}
      <p>O SLO mede o grafo. Espera de sessão, autenticação e persistência ficam fora. Cancelamentos e falhas do classificador contam como erro; recusas por política não.</p>
      <div className="monitor__charts">
        <Chart title="Latência por turno" values={snapshot.series.map(p => p.latency_ms)} labels={snapshot.series.map(p => time(p.started_at))} threshold={snapshot.slo.latency_limit_ms} />
        <Chart title="Custo conhecido acumulado na janela" values={snapshot.series.map(p => Number(p.cumulative_cost_usd))} labels={snapshot.series.map(p => time(p.started_at))} money />
      </div>
      <h2>Turnos</h2><div className="monitor__scroll"><table><thead><tr><th>Hora / sessão</th><th>Rota</th><th>Status</th><th>Latência</th><th>Tokens</th><th>Custo conhecido</th><th>Diagnóstico</th></tr></thead>
        <tbody>{snapshot.turns.map(turn => <tr key={turn.turn_id}>
          <td>{time(turn.started_at)}<small>{turn.session_id}</small></td><td>{turn.route}</td><td>{turn.status}<small>{turn.failure_category}</small></td>
          <td>{number(turn.elapsed_ms, ' ms')}</td><td>{number(turn.usage.total_tokens)}</td><td>{usd(turn.usage.estimated_cost_usd)}{!turn.usage.cost_complete && ' (parcial)'}</td>
          <td><details><summary>Nós e chamadas</summary><p>Turno: {turn.turn_id}</p>
            <ul>{turn.nodes.map((node, i) => <li key={i}>{node.node}: {number(node.elapsed_ms, ' ms')}</li>)}</ul>
            <ul>{turn.calls.map((call, i) => <li key={i}>{call.node} · {call.provider}/{call.model} · {call.success ? 'ok' : 'falha'} · {number(call.elapsed_ms, ' ms')} · entrada {number(call.input_tokens)} / saída {number(call.output_tokens)} · custo conhecido {usd(call.usage.estimated_cost_usd)}{!call.usage.cost_complete && ' (parcial)'}</li>)}</ul>
          </details></td></tr>)}</tbody></table></div>
      <h2>Modelos</h2><div className="monitor__scroll"><table><thead><tr><th>Provedor / modelo</th><th>Chamadas / falhas</th><th>Entrada / saída</th><th>Custo conhecido</th></tr></thead>
        <tbody>{snapshot.models.map(row => <tr key={`${row.provider}/${row.model}`}><td>{row.provider} / {row.model}</td><td>{row.usage.attempts} / {row.usage.failures}</td><td>{row.usage.input_tokens} / {row.usage.output_tokens}</td><td>{usd(row.usage.estimated_cost_usd)}{!row.usage.cost_complete && ' (parcial)'}</td></tr>)}</tbody></table></div>
      <h2>Rotas</h2><div className="monitor__scroll"><table><thead><tr><th>Rota</th><th>Turnos / erros</th><th>Média / p95</th><th>Custo conhecido</th></tr></thead>
        <tbody>{snapshot.routes.map(row => <tr key={row.route}><td>{row.route}</td><td>{row.turns} / {row.errors}</td><td>{number(row.average_latency_ms)} / {number(row.p95_latency_ms, ' ms')}</td><td>{usd(row.usage.estimated_cost_usd)}{!row.usage.cost_complete && ' (parcial)'}</td></tr>)}</tbody></table></div>
    </>}
  </section>
}
