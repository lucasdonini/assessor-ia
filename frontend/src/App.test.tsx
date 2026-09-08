import { listUsers } from './api/user'
// @vitest-environment jsdom

import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { sendChatMessage } from './api/chat'
import { finalizeSession } from './api/session'
import App from './App'

const SESSION_ID = '123e4567-e89b-12d3-a456-426614174000'
const NEXT_SESSION_ID = '123e4567-e89b-12d3-a456-426614174001'
const USER_ID = '123e4567-e89b-12d3-a456-426614174099'
const SESSION_STORAGE_KEY = `assessor-ia.session-id:${USER_ID}`
vi.mock('./api/user', () => ({ listUsers: vi.fn(), createUser: vi.fn() }))

vi.mock('./api/chat', () => ({
  sendChatMessage: vi.fn(),
}))
vi.mock('./api/session', () => ({
  finalizeSession: vi.fn(),
}))

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  localStorage.clear()
  vi.resetAllMocks()
  vi.unstubAllGlobals()
})

async function renderApp(nextSessionId = SESSION_ID) {
  const randomUUID = vi
    .fn()
    .mockReturnValueOnce(SESSION_ID)
    .mockReturnValue(nextSessionId)
  vi.stubGlobal('crypto', {
    randomUUID,
  })
  vi.mocked(listUsers).mockResolvedValue([{ id: USER_ID, created_at: '2026-09-07' }])
  await act(async () => { render(<App />) })
  return { randomUUID }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise
  })
  return { promise, resolve }
}

describe('App', () => {
  it('abre o perfil do usuário selecionado e volta ao chat', async () => {
    const user = userEvent.setup()
    await renderApp()

    await user.click(screen.getByRole('button', { name: 'Perfil' }))

    expect(screen.getByRole('heading', { name: 'perfil' })).toBeTruthy()
    expect(screen.getByTitle(USER_ID)).toBeTruthy()

    await user.click(screen.getByRole('button', { name: 'voltar ao chat' }))

    expect(screen.getByLabelText('Sua mensagem')).toBeTruthy()
  })

  it('envia a mensagem e apresenta a resposta do assistente', async () => {
    const user = userEvent.setup()
    vi.mocked(sendChatMessage).mockResolvedValue({
      session_id: SESSION_ID,
      called_agents: [], content: '**Resposta** do assistente',
    })
    await renderApp()

    await user.type(screen.getByLabelText('Sua mensagem'), 'Minha pergunta')
    await user.click(screen.getByRole('button', { name: 'Enviar mensagem' }))

    expect(sendChatMessage).toHaveBeenCalledWith(SESSION_ID, USER_ID, 'Minha pergunta')
    await waitFor(() => {
      expect(screen.getByRole('log').textContent).toContain(
        'Resposta do assistente',
      )
    })
  })

  it('apresenta erro público quando o envio falha', async () => {
    const user = userEvent.setup()
    vi.mocked(sendChatMessage).mockRejectedValue(
      new Error('Não foi possível conectar ao assistente.'),
    )
    await renderApp()

    await user.type(screen.getByLabelText('Sua mensagem'), 'Minha pergunta')
    await user.click(screen.getByRole('button', { name: 'Enviar mensagem' }))

    expect(
      await screen.findByText('Não foi possível conectar ao assistente.'),
    ).toBeTruthy()
    const input = screen.getByLabelText('Sua mensagem') as HTMLTextAreaElement
    expect(input.value).toBe('Minha pergunta')
    expect(document.activeElement).toBe(input)
  })

  it('não permite enviar uma mensagem vazia', async () => {
    await renderApp()

    const submitButton = screen.getByRole('button', {
      name: 'Enviar mensagem',
    }) as HTMLButtonElement
    expect(submitButton.disabled).toBe(true)
    expect(sendChatMessage).not.toHaveBeenCalled()
  })

  it('persiste a sessão criada para reutilizá-la depois', async () => {
    await renderApp()

    expect(localStorage.getItem(SESSION_STORAGE_KEY)).toBe(SESSION_ID)
  })

  it('reutiliza a sessão persistida ao abrir novamente', async () => {
    const user = userEvent.setup()
    localStorage.setItem(SESSION_STORAGE_KEY, SESSION_ID)
    vi.mocked(sendChatMessage).mockResolvedValue({
      session_id: SESSION_ID,
      called_agents: [], content: 'Resposta do assistente',
    })

    const { randomUUID } = await renderApp(NEXT_SESSION_ID)

    await user.type(screen.getByLabelText('Sua mensagem'), 'Continuar conversa')
    await user.click(screen.getByRole('button', { name: 'Enviar mensagem' }))

    await waitFor(() =>
      expect(sendChatMessage).toHaveBeenCalledWith(
        SESSION_ID,
        USER_ID, 'Continuar conversa',
      ),
    )
    expect(randomUUID).not.toHaveBeenCalled()
  })

  it('substitui um identificador persistido inválido', async () => {
    localStorage.setItem(SESSION_STORAGE_KEY, 'id-inválido')

    await renderApp()

    expect(localStorage.getItem(SESSION_STORAGE_KEY)).toBe(SESSION_ID)
  })

  it('reutiliza a mesma sessão em mensagens consecutivas', async () => {
    const user = userEvent.setup()
    vi.mocked(sendChatMessage).mockResolvedValue({
      session_id: SESSION_ID,
      called_agents: [], content: 'Resposta do assistente',
    })
    await renderApp()

    const messageInput = screen.getByLabelText('Sua mensagem')
    const submitButton = screen.getByRole('button', { name: 'Enviar mensagem' })

    await user.type(messageInput, 'Primeira pergunta')
    await user.click(submitButton)
    await waitFor(() => expect(sendChatMessage).toHaveBeenCalledTimes(1))

    await user.clear(messageInput)
    await user.type(messageInput, 'Segunda pergunta')
    await user.click(submitButton)
    await waitFor(() => expect(sendChatMessage).toHaveBeenCalledTimes(2))

    expect(sendChatMessage).toHaveBeenNthCalledWith(
      1,
      SESSION_ID,
      USER_ID, 'Primeira pergunta',
    )
    expect(sendChatMessage).toHaveBeenNthCalledWith(
      2,
      SESSION_ID,
      USER_ID, 'Segunda pergunta',
    )
  })

  it('encerra a sessão atual antes de iniciar outra', async () => {
    const user = userEvent.setup()
    vi.mocked(finalizeSession).mockResolvedValue({
      session_id: SESSION_ID,
      session_summary: 'Resumo da sessão',
    })
    vi.mocked(sendChatMessage).mockResolvedValue({
      session_id: NEXT_SESSION_ID,
      called_agents: [], content: 'Resposta da nova sessão',
    })
    await renderApp(NEXT_SESSION_ID)

    await user.click(screen.getByRole('button', { name: 'Nova sessão' }))
    await waitFor(() =>
      expect(finalizeSession).toHaveBeenCalledWith(SESSION_ID, USER_ID),
    )
    expect(localStorage.getItem(SESSION_STORAGE_KEY)).toBe(NEXT_SESSION_ID)

    await user.type(screen.getByLabelText('Sua mensagem'), 'Nova pergunta')
    await user.click(screen.getByRole('button', { name: 'Enviar mensagem' }))

    await waitFor(() =>
      expect(sendChatMessage).toHaveBeenCalledWith(
        NEXT_SESSION_ID,
        USER_ID, 'Nova pergunta',
      ),
    )
  })

  it('preserva a sessão atual quando o encerramento falha', async () => {
    const user = userEvent.setup()
    vi.mocked(finalizeSession).mockRejectedValue(
      new Error('Não foi possível encerrar a sessão.'),
    )
    vi.mocked(sendChatMessage).mockResolvedValue({
      session_id: SESSION_ID,
      called_agents: [], content: 'Resposta do assistente',
    })
    await renderApp(NEXT_SESSION_ID)

    await user.click(screen.getByRole('button', { name: 'Nova sessão' }))
    expect(
      await screen.findByText('Não foi possível encerrar a sessão.'),
    ).toBeTruthy()
    expect(localStorage.getItem(SESSION_STORAGE_KEY)).toBe(SESSION_ID)

    await user.type(screen.getByLabelText('Sua mensagem'), 'Tentar novamente')
    await user.click(screen.getByRole('button', { name: 'Enviar mensagem' }))

    await waitFor(() =>
      expect(sendChatMessage).toHaveBeenCalledWith(
        SESSION_ID,
        USER_ID, 'Tentar novamente',
      ),
    )
  })

  it('mantém todas as perguntas e respostas em ordem na conversa', async () => {
    const user = userEvent.setup()
    vi.mocked(sendChatMessage)
      .mockResolvedValueOnce({ session_id: SESSION_ID, called_agents: [], content: 'Primeira resposta' })
      .mockResolvedValueOnce({ session_id: SESSION_ID, called_agents: [], content: 'Segunda resposta' })
    await renderApp()

    const input = screen.getByLabelText('Sua mensagem')
    await user.type(input, 'Primeira pergunta{Enter}')
    await screen.findByText('Primeira resposta')
    await user.type(input, 'Segunda pergunta{Enter}')
    await screen.findByText('Segunda resposta')

    const messages = within(screen.getByRole('log')).getAllByRole('article')
    expect(messages.map((message) => message.textContent)).toEqual([
      'vocêPrimeira pergunta',
      'assistentePrimeira resposta',
      'vocêSegunda pergunta',
      'assistenteSegunda resposta',
    ])
    expect((input as HTMLTextAreaElement).value).toBe('')
  })

  it('associa as etapas somente à resposta correspondente, inclusive em bloqueios', async () => {
    const user = userEvent.setup()
    vi.mocked(sendChatMessage)
      .mockResolvedValueOnce({
        session_id: SESSION_ID, content: 'Resposta financeira',
        called_agents: ['input_guardrail', 'router', 'financial', 'orquestrator', 'output_guardrail'],
      })
      .mockResolvedValueOnce({
        session_id: SESSION_ID, content: 'Resposta da agenda',
        called_agents: ['input_guardrail', 'router', 'agenda', 'orquestrator', 'output_guardrail'],
      })
      .mockResolvedValueOnce({
        session_id: SESSION_ID, content: 'Solicitação bloqueada',
        called_agents: ['input_guardrail'],
      })
    await renderApp()
    const input = screen.getByLabelText('Sua mensagem')
    await user.type(input, 'Saldo{Enter}')
    await screen.findByText('Resposta financeira')
    await user.type(input, 'Compromissos{Enter}')
    await screen.findByText('Resposta da agenda')
    await user.type(input, 'Entrada bloqueada{Enter}')
    await screen.findByText('Solicitação bloqueada')

    const lists = screen.getAllByRole('list', { name: 'Etapas executadas nesta pergunta' })
    expect(lists.map((list) => within(list).getAllByRole('listitem').map((item) => item.textContent))).toEqual([
      ['Validação de entrada', 'Roteador', 'Financeiro', 'Orquestrador', 'Validação de saída'],
      ['Validação de entrada', 'Roteador', 'Agenda', 'Orquestrador', 'Validação de saída'],
      ['Validação de entrada'],
    ])
  })

  it('preserva nomes novos e repetições reais dentro da mesma execução', async () => {
    const user = userEvent.setup()
    vi.mocked(sendChatMessage).mockResolvedValue({
      session_id: SESSION_ID, content: 'Resposta',
      called_agents: ['router', 'novo_especialista', 'router'],
    })
    await renderApp()
    await user.type(screen.getByLabelText('Sua mensagem'), 'Pergunta{Enter}')
    await screen.findByText('Resposta')
    const list = screen.getByRole('list', { name: 'Etapas executadas nesta pergunta' })
    expect(within(list).getAllByRole('listitem').map((item) => item.textContent)).toEqual([
      'Roteador', 'novo_especialista', 'Roteador',
    ])
  })

  it('quebra a linha com Shift+Enter e envia com Ctrl+Enter', async () => {
    const user = userEvent.setup()
    vi.mocked(sendChatMessage).mockResolvedValue({
      session_id: SESSION_ID, called_agents: [], content: 'Resposta',
    })
    await renderApp()
    const input = screen.getByLabelText('Sua mensagem') as HTMLTextAreaElement

    await user.type(input, 'Linha um{Shift>}{Enter}{/Shift}Linha dois')
    expect(input.value).toBe('Linha um\nLinha dois')
    expect(sendChatMessage).not.toHaveBeenCalled()

    await user.keyboard('{Control>}{Enter}{/Control}')
    await screen.findByText('Resposta')
    expect(sendChatMessage).toHaveBeenCalledWith(SESSION_ID, USER_ID, 'Linha um\nLinha dois')
  })

  it('não envia Enter enquanto o teclado está compondo um caractere', async () => {
    await renderApp()
    const input = screen.getByLabelText('Sua mensagem')
    fireEvent.change(input, { target: { value: 'Pergunta' } })
    fireEvent.keyDown(input, { key: 'Enter', isComposing: true })
    fireEvent.keyDown(input, { key: 'Enter', keyCode: 229 })
    expect(sendChatMessage).not.toHaveBeenCalled()
  })

  it('bloqueia envio duplicado e nova sessão enquanto aguarda resposta', async () => {
    const pending = deferred<Awaited<ReturnType<typeof sendChatMessage>>>()
    vi.mocked(sendChatMessage).mockReturnValue(pending.promise)
    await renderApp()
    const input = screen.getByLabelText('Sua mensagem') as HTMLTextAreaElement
    const form = screen.getByRole('form', { name: 'Enviar mensagem ao assistente' })
    const reset = screen.getByRole('button', { name: 'Nova sessão' }) as HTMLButtonElement

    fireEvent.change(input, { target: { value: 'Pergunta' } })
    fireEvent.submit(form)
    fireEvent.submit(form)
    fireEvent.click(reset)

    expect(sendChatMessage).toHaveBeenCalledTimes(1)
    expect(finalizeSession).not.toHaveBeenCalled()
    expect(input.disabled).toBe(true)
    expect(reset.disabled).toBe(true)
    expect(screen.getByRole('status').textContent).toContain('preparando uma resposta')

    await act(async () => {
      pending.resolve({ session_id: SESSION_ID, called_agents: [], content: 'Resposta' })
      await pending.promise
    })
    expect(input.disabled).toBe(false)
    expect(reset.disabled).toBe(false)
  })

  it('só limpa a conversa e troca a sessão após finalizar, exibindo o resumo', async () => {
    const user = userEvent.setup()
    const pending = deferred<Awaited<ReturnType<typeof finalizeSession>>>()
    vi.mocked(finalizeSession).mockReturnValue(pending.promise)
    vi.mocked(sendChatMessage).mockResolvedValue({
      session_id: SESSION_ID, called_agents: [], content: 'Resposta antiga',
    })
    await renderApp(NEXT_SESSION_ID)
    const input = screen.getByLabelText('Sua mensagem') as HTMLTextAreaElement
    await user.type(input, 'Pergunta antiga{Enter}')
    await screen.findByText('Resposta antiga')
    await user.click(screen.getByRole('button', { name: 'Nova sessão' }))

    expect(localStorage.getItem(SESSION_STORAGE_KEY)).toBe(SESSION_ID)
    expect(screen.getByText('Resposta antiga')).toBeTruthy()
    expect(input.disabled).toBe(true)
    fireEvent.submit(screen.getByRole('form', { name: 'Enviar mensagem ao assistente' }))
    expect(sendChatMessage).toHaveBeenCalledTimes(1)

    await act(async () => {
      pending.resolve({ session_id: SESSION_ID, session_summary: '**Resumo** anterior' })
      await pending.promise
    })

    expect(localStorage.getItem(SESSION_STORAGE_KEY)).toBe(NEXT_SESSION_ID)
    expect(screen.queryByText('Resposta antiga')).toBeNull()
    expect(within(screen.getByRole('log')).queryAllByRole('article')).toHaveLength(0)
    await user.click(screen.getByText('Resumo da sessão anterior'))
    expect(screen.getByText('Resumo', { selector: 'strong' })).toBeTruthy()
    expect(input.disabled).toBe(false)
  })

  it('continua funcionando quando o navegador bloqueia o armazenamento', async () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('Blocked') })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('Blocked') })
    vi.mocked(sendChatMessage).mockResolvedValue({
      session_id: SESSION_ID, called_agents: [], content: 'Resposta sem armazenamento',
    })
    const user = userEvent.setup()
    await renderApp()
    await user.type(screen.getByLabelText('Sua mensagem'), 'Pergunta{Enter}')
    await screen.findByText('Resposta sem armazenamento')
    expect(sendChatMessage).toHaveBeenCalledWith(SESSION_ID, USER_ID, 'Pergunta')
  })
})


it('descarta a resposta pendente ao trocar de usuário', async () => {
  const other = '123e4567-e89b-12d3-a456-426614174088'
  const pending = deferred<Awaited<ReturnType<typeof sendChatMessage>>>()
  vi.stubGlobal('crypto', { randomUUID: vi.fn().mockReturnValue(SESSION_ID) })
  vi.mocked(listUsers).mockResolvedValue([
    { id: USER_ID, created_at: '2026-09-07' },
    { id: other, created_at: '2026-09-07' },
  ])
  vi.mocked(sendChatMessage).mockReturnValue(pending.promise)
  await act(async () => { render(<App />) })
  fireEvent.change(screen.getByLabelText('Sua mensagem'), { target: { value: 'Segredo A' } })
  fireEvent.submit(screen.getByRole('form'))
  fireEvent.change(screen.getByLabelText('Usuário'), { target: { value: other } })
  await act(async () => {
    pending.resolve({ session_id: SESSION_ID, content: 'Resposta privada A', called_agents: [] })
  })
  expect(screen.queryByText('Segredo A')).toBeNull()
  expect(screen.queryByText('Resposta privada A')).toBeNull()
  expect(localStorage.getItem(`assessor-ia.session-id:${other}`)).toBe(SESSION_ID)
  expect(localStorage.getItem(SESSION_STORAGE_KEY)).toBe(SESSION_ID)
})
