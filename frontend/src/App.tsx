import { createUser, listUsers, type User } from './api/user'
import {
  type KeyboardEvent,
  type SubmitEvent,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from 'react'
import { sendChatMessage } from './api/chat'
import { finalizeSession } from './api/session'
import { MarkdownResponse } from './components/MarkdownResponse'
import './App.css'

const SESSION_STORAGE_KEY = 'assessor-ia.session-id'
const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

type Message = Readonly<{
  id: number
  kind: 'user' | 'assistant' | 'error'
  text: string
  calledAgents: readonly string[]
}>

const AGENT_LABELS: Readonly<Record<string, string>> = {
  input_guardrail: 'Validação de entrada',
  router: 'Roteador',
  financial: 'Financeiro',
  agenda: 'Agenda',
  faq: 'Perguntas frequentes',
  orquestrator: 'Orquestrador',
  output_guardrail: 'Validação de saída',
}

type Phase = 'idle' | 'sending' | 'finalizing'
type Connection = 'ready' | 'connected' | 'error'

function persistSessionId(sessionId: string, userId: string) {
  try {
    localStorage.setItem(`${SESSION_STORAGE_KEY}:${userId}`, sessionId)
  } catch {
    // The conversation still works for the lifetime of the current page.
  }
}

function createSessionId(userId: string) {
  const sessionId = crypto.randomUUID()
  persistSessionId(sessionId, userId)
  return sessionId
}

function getOrCreateSessionId(userId: string) {
  try {
    const persistedSessionId = localStorage.getItem(`${SESSION_STORAGE_KEY}:${userId}`)
    if (persistedSessionId && UUID_PATTERN.test(persistedSessionId)) {
      return persistedSessionId
    }
  } catch {
    // Fall back to an in-memory identifier when storage is unavailable.
  }

  return createSessionId(userId)
}

function Chat({ userId }: { userId: string }) {
  const [sessionId, setSessionId] = useState(() => getOrCreateSessionId(userId))
  const [draft, setDraft] = useState('')
  const [messages, setMessages] = useState<readonly Message[]>([])
  const [phase, setPhase] = useState<Phase>('idle')
  const [connection, setConnection] = useState<Connection>('ready')
  const [summary, setSummary] = useState<string | null>(null)
  const [notice, setNotice] = useState('')
  const [finalizationError, setFinalizationError] = useState('')
  const activeRef = useRef(true)
  useEffect(() => {
    activeRef.current = true
    return () => { activeRef.current = false }
  }, [])
  const busyRef = useRef(false)
  const nextMessageId = useRef(0)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const threadRef = useRef<HTMLDivElement>(null)
  const isBusy = phase !== 'idle'

  useEffect(() => {
    if (phase === 'idle') inputRef.current?.focus()
  }, [phase])

  useLayoutEffect(() => {
    const input = inputRef.current
    if (!input) return
    input.style.height = 'auto'
    const borderHeight = input.offsetHeight - input.clientHeight
    input.style.height = Math.min(input.scrollHeight + borderHeight, 140) + 'px'
  }, [draft])

  useEffect(() => {
    const thread = threadRef.current
    if (thread) thread.scrollTop = thread.scrollHeight
  }, [messages, phase])

  function appendMessage(
    kind: Message['kind'],
    text: string,
    calledAgents: readonly string[] = [],
  ) {
    const message: Message = { id: nextMessageId.current++, kind, text, calledAgents }
    setMessages((previous) => [...previous, message])
  }

  async function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault()
    const question = draft.trim()
    if (!question || busyRef.current) return

    busyRef.current = true
    setPhase('sending')
    setNotice('')
    setFinalizationError('')
    appendMessage('user', question)
    setDraft('')

    try {
      const reply = await sendChatMessage(sessionId, userId, question)
      if (!activeRef.current) return
      appendMessage('assistant', reply.content, reply.called_agents)
      setConnection('connected')
    } catch (error: unknown) {
      appendMessage(
        'error',
        error instanceof Error
          ? error.message
          : 'Não foi possível obter uma resposta. Tente novamente.',
      )
      setConnection('error')
      setDraft(question)
    } finally {
      busyRef.current = false
      setPhase('idle')
    }
  }

  async function handleNewSession() {
    if (busyRef.current) return

    busyRef.current = true
    setPhase('finalizing')
    setNotice('')
    setFinalizationError('')

    try {
      const result = await finalizeSession(sessionId, userId)
      if (!activeRef.current) return
      setSessionId(createSessionId(userId))
      setMessages([])
      setDraft('')
      setSummary(result.session_summary)
      setNotice('Nova sessão iniciada.')
      setConnection('connected')
    } catch (error: unknown) {
      setFinalizationError(
        error instanceof Error
          ? error.message
          : 'Não foi possível encerrar a sessão. Tente novamente.',
      )
      setConnection('error')
    } finally {
      busyRef.current = false
      setPhase('idle')
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (
      event.key === 'Enter' &&
      !event.shiftKey &&
      !event.nativeEvent.isComposing &&
      event.keyCode !== 229
    ) {
      event.preventDefault()
      event.currentTarget.form?.requestSubmit()
    }
  }

  const statusText =
    phase === 'sending'
      ? 'O assistente está preparando uma resposta…'
      : phase === 'finalizing'
        ? 'Encerrando a sessão atual…'
        : notice ||
          (connection === 'error'
            ? 'A última operação não foi concluída. Você pode tentar novamente.'
            : connection === 'connected'
              ? 'Resposta recebida. Pode continuar a conversa.'
              : 'Pronto para conversar.')

  return (
    <main className="console-page">
      <section className="console" aria-labelledby="console-title">
        <header className="console__header">
          <div className="header__identity">
            <span
              className={'header__dot' + (connection === 'error' ? ' is-error' : '')}
              aria-hidden="true"
            />
            <h1 className="header__title" id="console-title">
              assistente<span className="header__cursor" aria-hidden="true">_</span>
            </h1>
          </div>
          <div className="header__meta">
            <span className="header__label">sessão</span>
            <code
              className="header__session"
              title={sessionId}
              aria-label={'Sessão atual: ' + sessionId}
            >
              {sessionId.slice(0, 8)}…
            </code>
            <button
              className="header__reset"
              type="button"
              onClick={handleNewSession}
              disabled={isBusy}
              title="Encerrar esta conversa e iniciar uma nova sessão"
            >
              {phase === 'finalizing' ? 'Encerrando…' : 'Nova sessão'}
            </button>
          </div>
        </header>

        {summary && (
          <details className="session-summary">
            <summary>Resumo da sessão anterior</summary>
            <div className="session-summary__content">
              <MarkdownResponse content={summary} />
            </div>
          </details>
        )}

        <div
          className="console__thread"
          ref={threadRef}
          role="log"
          aria-label="Conversa com o assistente"
          aria-live="polite"
          aria-relevant="additions"
        >
          {messages.length === 0 && (
            <div className="thread__empty">
              <p className="empty__eyebrow">// pronto para receber</p>
              <p className="empty__text">
                Escreva uma pergunta abaixo para conversar sobre finanças e rotina.
              </p>
              <p className="empty__note">
                A sessão é mantida ao reabrir o app. Aqui aparecem as mensagens
                trocadas nesta tela.
              </p>
            </div>
          )}
          {messages.map((message) => (
            <article className={'message message--' + message.kind} key={message.id}>
              <span className="message__label">
                {message.kind === 'user'
                  ? 'você'
                  : message.kind === 'error'
                    ? 'não foi possível responder'
                    : 'assistente'}
              </span>
              <div className="message__bubble">
                {message.kind === 'assistant'
                  ? <MarkdownResponse content={message.text} />
                  : message.text}
              </div>
              {message.kind === 'assistant' && message.calledAgents.length > 0 && (
                <ul className="message__agents" aria-label="Etapas executadas nesta pergunta">
                  {message.calledAgents.map((agent, index) => (
                    <li
                      className={'agent-tag' + (agent === 'input_guardrail' || agent === 'output_guardrail' ? ' agent-tag--validation' : '')}
                      key={`${agent}-${index}`}
                    >
                      {Object.hasOwn(AGENT_LABELS, agent) ? AGENT_LABELS[agent] : agent}
                    </li>
                  ))}
                </ul>
              )}
            </article>
          ))}
          {phase === 'sending' && (
            <div className="message message--assistant" aria-hidden="true">
              <span className="message__label">assistente</span>
              <div className="message__bubble">
                <span className="typing"><span /><span /><span /></span>
              </div>
            </div>
          )}
        </div>

        <form
          className="console__composer"
          onSubmit={handleSubmit}
          autoComplete="off"
          aria-label="Enviar mensagem ao assistente"
        >
          <label className="sr-only" htmlFor="message">Sua mensagem</label>
          <textarea
            className="composer__input"
            id="message"
            ref={inputRef}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Digite sua pergunta…"
            aria-describedby="keyboard-hint"
            rows={1}
            disabled={isBusy}
            required
          />
          <button
            className="composer__send"
            type="submit"
            disabled={isBusy || !draft.trim()}
            aria-label="Enviar mensagem"
            title="Enviar mensagem"
          >
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
              <path d="M2 9L16 2L11 16L8.5 10.5L2 9Z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
              <path d="M8.5 10.5L16 2" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
            </svg>
          </button>
        </form>

        <footer className="console__footer">
          {finalizationError && (
            <p className="console__error" role="alert">{finalizationError}</p>
          )}
          <p className="console__status" role="status">{statusText}</p>
          <p className="console__hint" id="keyboard-hint">
            <kbd>Enter</kbd> envia <span aria-hidden="true">·</span>{' '}
            <kbd>Shift + Enter</kbd> quebra a linha
          </p>
        </footer>
      </section>
    </main>
  )
}

const USER_STORAGE_KEY = 'assessor-ia.user-id'

function App() {
  const [users, setUsers] = useState<User[]>([])
  const [userId, setUserId] = useState('')
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')
  const [reload, setReload] = useState(0)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    listUsers().then((loaded) => {
      if (!active) return
      setUsers(loaded)
      let saved: string | null = null
      try { saved = localStorage.getItem(USER_STORAGE_KEY) } catch { /* Memory only. */ }
      setUserId(loaded.find((user) => user.id === saved)?.id ?? loaded[0]?.id ?? '')
    }).catch(() => {
      if (active) setError('Não foi possível carregar os usuários. Tente novamente.')
    }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [reload])

  function selectUser(id: string) {
    setUserId(id)
    try { localStorage.setItem(USER_STORAGE_KEY, id) } catch { /* Memory only. */ }
  }

  async function handleCreateUser() {
    if (creating) return
    setCreating(true)
    setError('')
    try {
      const user = await createUser()
      setUsers((previous) => [...previous, user])
      selectUser(user.id)
    } catch {
      setError('Não foi possível criar o usuário. Tente novamente.')
    } finally { setCreating(false) }
  }

  return <>
    <section className="user-picker" aria-label="Usuários de demonstração">
      <label htmlFor="active-user">Usuário</label>
      <select id="active-user" value={userId} disabled={loading || creating}
        onChange={(event) => selectUser(event.target.value)}>
        {!users.length && <option value="">{loading ? 'Carregando…' : 'Crie um usuário'}</option>}
        {users.map((user, index) => <option key={user.id} value={user.id}>
          Usuário {index + 1} · {user.id.slice(0, 8)}
        </option>)}
      </select>
      <button type="button" onClick={handleCreateUser} disabled={loading || creating}>
        {creating ? 'Criando…' : 'Criar usuário'}
      </button>
      {error && <><p role="alert">{error}</p>
        <button type="button" onClick={() => setReload((value) => value + 1)}>Recarregar usuários</button></>}
    </section>
    {userId && <Chat key={userId} userId={userId} />}
  </>
}

export default App
