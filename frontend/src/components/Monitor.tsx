import { useEffect, useRef, useState } from 'react'
import { fetchMonitor, type MonitorData } from '../api/monitor'
import './Monitor.css'

const ms = (value: number | null) => value === null ? '—' : `${value.toLocaleString('pt-BR', { maximumFractionDigits: 0 })} ms`
const usd = (value: number) => value.toLocaleString('pt-BR', { style: 'currency', currency: 'USD', maximumFractionDigits: 6 })
const statuses: Record<string, string> = { ok: 'Concluído', error: 'Erro', blocked: 'Bloqueado', cancelled: 'Cancelado' }

function Chart({ title, series, limit, currency = false }: {
  title: string; series: MonitorData['latency_series']; limit?: number; currency?: boolean
}) {
  const maximum = Math.max(1, limit ?? 0, ...series.map((point) => point.value))
  const y = (value: number) => 150 - value / maximum * 130
  const x = (index: number) => 20 + index / Math.max(1, series.length - 1) * 560
  return <section className="monitor__panel">
    <h2>{title}</h2>
    {series.length ? <>
      <svg viewBox="0 0 600 175" role="img" aria-label={`${title}. Valores disponíveis na tabela abaixo.`}>
        {limit !== undefined && <line x1="20" x2="580" y1={y(limit)} y2={y(limit)} className="monitor__limit" />}
        <polyline fill="none" points={series.map((point, index) => `${x(index)},${y(point.value)}`).join(' ')} />
        {series.map((point, index) => <circle key={point.turn_id} cx={x(index)} cy={y(point.value)} r="3"><title>{currency ? usd(point.value) : ms(point.value)}</title></circle>)}
      </svg>
      <details><summary>Ver valores do gráfico</summary><table><thead><tr><th>Turno</th><th>Valor</th></tr></thead><tbody>
        {series.map((point) => <tr key={point.turn_id}><td>{point.turn_id.slice(0, 8)}</td><td>{currency ? usd(point.value) : ms(point.value)}</td></tr>)}
      </tbody></table></details>
    </> : <p>Sem turnos nesta janela.</p>}
  </section>
}

export function Monitor({ userId, onBack }: { userId: string; onBack: () => void }) {
  const [data, setData] = useState<MonitorData | null>(null)
  const [error, setError] = useState(false)
  const [loading, setLoading] = useState(true)
  const refresh = useRef<() => void>(() => {})

  useEffect(() => {
    let active = true
    let busy = false
    let timer: ReturnType<typeof setTimeout> | undefined
    let controller: AbortController | undefined
    setData(null); setError(false); setLoading(true)
    async function load() {
      if (!active || busy) return
      busy = true
      clearTimeout(timer)
      controller = new AbortController()
      try {
        const snapshot = await fetchMonitor(userId, controller.signal)
        if (active) { setData(snapshot); setError(false) }
      } catch {
        if (active) setError(true)
      } finally {
        busy = false
        if (active) { setLoading(false); timer = setTimeout(() => { void load() }, 4000) }
      }
    }
    refresh.current = () => { void load() }
    void load()
    return () => { active = false; clearTimeout(timer); controller?.abort(); refresh.current = () => {} }
  }, [userId])

  const summary = data?.summary
  const metrics = summary ? [
    ['Turnos', summary.turns], ['Em andamento', summary.in_flight],
    ['Erros', summary.errors], ['Bloqueios', summary.blocked], ['Cancelamentos', summary.cancelled],
    ['Latência média', ms(summary.latency_mean_ms)], ['Latência p95', ms(summary.latency_p95_ms)],
    ['Taxa de erro', summary.error_rate === null ? '—' : `${(summary.error_rate * 100).toLocaleString('pt-BR')}%`],
    ['No ar', `${Math.floor(data!.window.uptime_seconds)} s`],
    ['Tokens conhecidos', summary.usage.input_tokens + summary.usage.output_tokens],
    ['Custo conhecido', usd(summary.usage.known_cost_usd)], ['Fallbacks', summary.fallbacks],
    ['Modelo mais usado', summary.most_used_model ?? '—'],
  ] : []
  return <section className="monitor" aria-label="Monitoramento">
    <header className="monitor__header"><h1>Monitoramento</h1><div>
      <button type="button" onClick={onBack}>Voltar ao chat</button>
      <button type="button" onClick={() => refresh.current()}>Atualizar</button>
    </div></header>
    <p>Seu usuário · últimos {data?.window.capacity ?? 50} turnos do processo, filtrados por usuário. Reiniciar limpa esta janela.</p>
    <p>Latência do grafo: não inclui espera pela sessão nem persistência. A atividade de outros usuários pode remover turnos antigos.</p>
    {loading && <p role="status">Carregando monitoramento…</p>}
    {error && <p role="alert">Não foi possível atualizar o monitoramento.{data && ' Os dados exibidos estão desatualizados.'}</p>}
    {data && <>
      <div className={`monitor__slo ${data.slo.ok === null ? '' : data.slo.ok ? 'is-ok' : 'is-error'}`} role="status">
        <strong>{data.slo.ok === null ? 'Sem amostras para avaliar o SLO' : data.slo.ok ? 'SLO dentro do objetivo' : 'SLO fora do objetivo'}</strong>
        <p>p95 até {ms(data.slo.p95_limit_ms)} · erros até {data.slo.error_rate_limit * 100}% · {data.slo.sample_size} amostras{data.slo.sample_size < 20 && ' (amostra pequena)'}</p>
      </div>
      <p>Atualizado em {new Date(data.window.snapshot_at).toLocaleString('pt-BR')} · consulta 4 s após cada atualização</p>
      <div className="monitor__metrics">{metrics.map(([label, value]) => <div key={label} className="monitor__panel"><span>{label}</span><strong>{value}</strong></div>)}</div>
      <p>Custo estimado a preço cheio, sem desconto de cache; não é a fatura. {summary?.usage.cost_complete ? 'Cobertura completa.' : 'Custo parcial: há chamadas sem preço ou consumo conhecido.'} {!summary?.usage.usage_complete && 'Tokens também são parciais.'}</p>
      <div className="monitor__charts"><Chart title="Latência por turno" series={data.latency_series} limit={data.slo.p95_limit_ms} /><Chart title="Custo conhecido acumulado na janela" series={data.cost_series} currency /></div>
      <section className="monitor__panel"><h2>Turnos</h2>{!data.turns.length ? <p>Nenhum turno deste usuário na janela.</p> : <table><thead><tr><th>Hora</th><th>Sessão</th><th>Rota</th><th>Status</th><th>Latência</th><th>Detalhes</th></tr></thead><tbody>
        {[...data.turns].reverse().map((turn) => <tr key={turn.turn_id}>
          <td>{new Date(turn.ended_at).toLocaleTimeString('pt-BR')}</td><td>{turn.session_id}</td><td>{turn.route}</td><td>{statuses[turn.status]}{turn.reason && <small>{turn.reason}</small>}</td><td>{ms(turn.elapsed_ms)}</td>
          <td><details><summary>Nós e modelos · {turn.turn_id.slice(0, 8)}</summary>
            {(!turn.capture_complete || turn.detail_truncated) && <p>Captura parcial; valores conhecidos são um subtotal.</p>}
            <ul>{turn.nodes.map((node, index) => <li key={index}>{node.name}: {ms(node.elapsed_ms)} · {statuses[node.status]}</li>)}</ul>
            <ul>{turn.attempts.map((attempt) => <li key={attempt.run_id}>{attempt.node} · {attempt.provider}/{attempt.model} · {statuses[attempt.status]} · {ms(attempt.elapsed_ms)} · entrada {attempt.input_tokens ?? 'desconhecida'} / saída {attempt.output_tokens ?? 'desconhecida'} · {attempt.cost_usd === null ? 'custo desconhecido' : usd(attempt.cost_usd)}{attempt.fallback && ' · fallback'}</li>)}</ul>
          </details></td>
        </tr>)}
      </tbody></table>}</section>
      <section className="monitor__panel"><h2>Por modelo</h2><table><thead><tr><th>Modelo</th><th>Tentativas</th><th>Erros</th><th>Entrada / saída</th><th>Custo conhecido</th><th>Latência média de sucesso</th></tr></thead><tbody>
        {data.by_model.map((model) => <tr key={`${model.provider}/${model.model}`}><td>{model.provider}/{model.model}</td><td>{model.attempts}</td><td>{model.errors}</td><td>{model.usage.input_tokens} / {model.usage.output_tokens}{!model.usage.usage_complete && ' (parcial)'}</td><td>{usd(model.usage.known_cost_usd)}{!model.usage.cost_complete && ' (parcial)'}</td><td>{ms(model.successful_latency_mean_ms)}</td></tr>)}
      </tbody></table>{!data.by_model.length && <p>Nenhuma chamada de modelo registrada.</p>}</section>
      <section className="monitor__panel"><h2>Por rota</h2><table><thead><tr><th>Rota</th><th>Turnos</th><th>Erros</th><th>Latência média</th><th>Custo conhecido</th></tr></thead><tbody>
        {data.by_route.map((route) => <tr key={route.route}><td>{route.route}</td><td>{route.turns}</td><td>{route.errors}</td><td>{ms(route.latency_mean_ms)}</td><td>{usd(route.usage.known_cost_usd)}{!route.usage.cost_complete && ' (parcial)'}</td></tr>)}
      </tbody></table></section>
    </>}
  </section>
}
