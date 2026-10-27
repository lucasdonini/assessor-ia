# Assessor.IA

Assistente web multiagente para organização financeira e apoio ao dia a dia. O
backend usa FastAPI e LangGraph; a interface usa React, TypeScript e Vite.

O PostgreSQL armazena transações, o MongoDB armazena a sessão e o histórico do
chat, e o Qdrant mantém os embeddings do FAQ e dos resumos de sessões. As respostas
podem ser produzidas por modelos Gemini e Groq.

## Servidor MCP local para ChatGPT / Codex

O servidor em `app/mcp_server.py` publica as nove ferramentas do agente
financeiro por `stdio`: `total_balance`, `daily_balance`,
`search_transactions`, `add_transaction`, `update_transaction`,
`delete_transaction`, `restore_transaction`, `consult_profile` e
`search_history`. As quatro operações de escrita exigem confirmação no cliente.
`delete_transaction` cancela o lançamento; `restore_transaction` reverte o
cancelamento. O servidor reutiliza os serviços e as ferramentas do agente, sem
iniciar o FastAPI ou o grafo.

Esta integração é **local e de um usuário por processo**. Configure
`ASSESSOR_MCP_USER_ID` com o UUID de um usuário existente. Após o login Google,
`GET /api/auth/me` informa o UUID da conta autenticada. O servidor valida o UUID no
PostgreSQL ao iniciar e vincula esse usuário a cada chamada. O modelo não pode
escolher outro `user_id` pelos argumentos das ferramentas. Quem puder iniciar o
processo com sua configuração local terá acesso às capacidades desse usuário;
portanto, não compartilhe a configuração nem use este modo para vários usuários.
A conta ChatGPT não é usada como identidade do banco.

No aplicativo de desktop ChatGPT, abra **Settings → MCP servers → Add server**,
escolha **STDIO** e informe o Python de `.venv` e o módulo
`app.mcp_server`. Também é possível configurar o Codex pelo `config.toml`
do usuário. Use o diretório absoluto do projeto como `cwd`, o executável absoluto
do Python do ambiente virtual como `command`, `args` com `-m` e
`app.mcp_server`, e `env` com `ASSESSOR_MCP_USER_ID`. Configure
`default_tools_approval_mode = "writes"` para pedir aprovação nas quatro
operações que alteram dados. Mantenha caminhos pessoais e o UUID no arquivo
local `~/.codex/config.toml`; o `.codex/config.toml` do projeto é ignorado pelo
Git. O ChatGPT na web não lê essa configuração local.

Execute `uv sync` no projeto e deixe PostgreSQL, MongoDB e Qdrant disponíveis.
O processo usa a configuração existente no `.env` da raiz. Reinicie o cliente
após adicionar o servidor; o catálogo deve mostrar nove ferramentas. Teste
primeiro uma leitura de saldo para o mesmo UUID usado no chat do Assessor.
Para testar gravações, use dados de teste e aprove cada chamada no Codex.
O servidor reserva `stdout` para MCP e envia seus logs para `stderr`.

## Requisitos

- Python 3.14;
- [uv](https://docs.astral.sh/uv/);
- Node.js 24 e npm;
- PostgreSQL, MongoDB e Qdrant acessíveis pela aplicação;
- chaves de API do Gemini, do Groq e do Qdrant;
- Docker, opcionalmente, para executar a aplicação em container.

O `docker-compose.yml` atual constrói e executa a aplicação, mas não provisiona
PostgreSQL, MongoDB nem Qdrant. Esses serviços precisam estar disponíveis
separadamente.

## Configuração inicial

Na raiz do projeto, crie o arquivo de ambiente usado pela aplicação:

```powershell
Copy-Item .env.example .env
```

Em Linux ou macOS, use `cp .env.example .env`. Preencha ao menos
`GEMINI_API_KEY`, `GROQ_API_KEY`, `QDRANT_API_KEY`, `QDRANT_URL`,
`POSTGRES_URL`, `MONGODB_URI` e `MONGODB_DBNAME`. O arquivo `.env` contém
segredos e não deve ser versionado.

Na primeira execução, use `INGEST_FAQ_PDF=true` para criar a coleção vetorial e
o alias configurado em `FAQ_COLLECTION_ALIAS`. Depois da ingestão, a opção pode
voltar para `false`. Novas ingestões constroem uma coleção versionada, trocam o
alias atomicamente e removem a coleção anterior.

### Configuração da busca no FAQ

As principais variáveis do pipeline vetorial são:

- `FAQ_COLLECTION_ALIAS`: alias estável consultado pela aplicação;
- `FAQ_COLLECTION_PREFIX`: prefixo das coleções versionadas criadas na ingestão;
- `EMBEDDING_DIMMENSIONS`: dimensão dos vetores, que deve ser compatível com o
  modelo de embeddings;
- `FAQ_CHUNK_SIZE` e `FAQ_CHUNK_OVERLAP`: tamanho e sobreposição dos trechos do
  PDF. A sobreposição deve ser menor que o tamanho do trecho;
- `FAQ_INGESTION_BATCH_SIZE`: quantidade de trechos processados por lote;
- `FAQ_SEARCH_SCORE_THRESHOLD`: similaridade mínima, entre `0` e `1`, para um
  trecho ser considerado relevante;
- `INGEST_FAQ_PDF`: controla se o PDF será ingerido durante a inicialização.

Mantenha `INGEST_FAQ_PDF=true` somente até uma inicialização concluir a ingestão
com sucesso. Cada nova ingestão cria outra coleção, valida a quantidade de pontos
e então troca o alias. O valor inicial de `FAQ_SEARCH_SCORE_THRESHOLD` é `0.52`,
mas deve ser calibrado com perguntas representativas sempre que o modelo de
embeddings ou o conteúdo do FAQ mudar.

Instale as dependências e prepare o frontend:

```bash
uv sync
npm ci --prefix frontend
npm run --prefix frontend build
uv run alembic upgrade head
```

O build inicial do frontend cria `frontend/dist`, diretório que o FastAPI monta
para servir a interface. Por isso, ele também é necessário antes da primeira
execução local do backend em um clone limpo.

### Memória semântica de sessões

`HISTORY_COLLECTION_NAME` já é suportada e tem valor padrão `session-history`.
A aplicação valida essa collection existente na inicialização: vetor padrão sem
nome, dimensão igual a `EMBEDDING_DIMMENSIONS`, distância Cosine e índice de payload
`keyword` em `user_id`. Ela não cria nem recria essa collection. O ambiente atual
usa 768 dimensões e índice de usuário com `is_tenant=true`.

Ao finalizar uma sessão, o resumo é salvo no MongoDB e indexado no Qdrant. O payload
contém `user_id` (UUID em string), `session_id`, `summary` e `started_at` (ISO 8601).
O ID do ponto é determinístico por usuário e sessão. Repetir a finalização reutiliza
o resumo salvo e repete o upsert, sem gerar outro resumo ou duplicar pontos.

Buscas vazias ou só com espaços retornam lista vazia sem I/O. Consultas preenchidas
buscam por similaridade, sempre filtradas por usuário; não há fallback para sessões
recentes. O limiar inicial do adaptador é `0.6`, independente do FAQ. Uma avaliação
manual em 07/09/2026 com `gemini-embedding-2-preview`, três resumos sintéticos e seis
perguntas recuperou três das quatro correspondências esperadas e rejeitou as duas
perguntas sem correspondência. "Quando eu viajei?" teve similaridade `0.618` com o
resumo de viagem; a consulta mais vaga sobre melhorar o escritório ficou em `0.567`
e não foi recuperada. Esse limiar conservador precisa de avaliação adicional com
conversas representativas. Os testes automatizados usam vetores controlados para
verificar filtros e ordenação, sem depender da variabilidade do modelo.

Uma falha no índice não desfaz o resumo persistido: a memória pode ficar incompleta
até uma nova finalização ou uma carga explícita. Não há retentativa automática em
segundo plano. Para validar a collection e contar resumos antigos sem gravar dados:

```bash
uv run python -m app.infrastructure.vectorstore.ingestors.history_ingestor --check
```

Para indexar os resumos existentes ou recuperar falhas, execute explicitamente:

```bash
uv run python -m app.infrastructure.vectorstore.ingestors.history_ingestor --batch-size 100
```

A leitura usa lotes do cursor MongoDB e projeta somente os campos do resumo.
A carga não limpa dados nem regenera resumos, mas chama o provedor de embeddings
para cada resumo e pode gerar custos. Ela para no primeiro erro; é seguro repeti-la.
Mantenha o mesmo modelo de embeddings para gravar e consultar essa collection.

## Desenvolvimento local

Inicie o backend em um terminal:

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Em outro terminal, inicie o servidor de desenvolvimento do frontend:

```bash
npm run --prefix frontend dev
```

A interface de desenvolvimento fica em `http://localhost:5173`. O Vite encaminha
requisições iniciadas por `/api` para o backend em `http://localhost:8000`.

Para testar o modo integrado, gere o frontend e inicie somente o backend:

```bash
npm run --prefix frontend build
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Nesse modo, a aplicação completa fica em `http://localhost:8000`.

Os atalhos equivalentes estão no `makefile`: `make dev`, `make up`,
`make build-frontend` e `make upgrade-db`.

## Execução com Docker

Com PostgreSQL, MongoDB e Qdrant já acessíveis e o `.env` configurado:

```bash
docker compose up --build
```

O build multi-stage instala o frontend, gera `frontend/dist`, instala as
dependências Python e publica a aplicação na porta 8000. As URLs de banco usadas
pelo container podem ser ajustadas no `docker-compose.yml` conforme o ambiente.

## API

As rotas privadas usam a sessao do login Google. O servidor ignora X-User-ID
como identidade. Operacoes de escrita exigem X-CSRF-Token, obtido em
GET /api/auth/me; a interface faz isso automaticamente. Credenciais Google
permanecem no backend, nunca no navegador ou no contexto do modelo.

- GET /api/auth/google/start e /api/auth/google/callback: login OIDC.
- GET /api/auth/me: usuario autenticado e token CSRF; 401 sem sessao valida.
- POST /api/auth/logout: invalida a sessao (validade absoluta de 24 horas).
- POST /api/chat/{session_id}: recebe message e devolve session_id, content e called_agents.
- POST /api/session/{session_id}/finalize: finaliza a conversa do usuario autenticado.
- POST /api/profile: salva o perfil do usuario autenticado.
- POST /api/calendar/google/connect: inicia consentimento separado para Calendar.
- GET /api/calendar/google/callback: conclui o vinculo da mesma conta Google.
- GET /api/calendar/connection e DELETE /api/calendar/connection: estado e desconexao.
- GET /api/agenda/proposals: conflitos aguardando confirmacao.
- POST /api/agenda/proposals/{operation_id}/confirm: confirma a proposta exata.
- GET /health, /docs e /redoc: saude e documentacao publica.

A API nao publica mais cadastro/listagem anonima de usuarios. UUIDs conhecidos
nao autorizam acesso aos dados. Erros internos usam mensagens publicas seguras.

## Qualidade e testes

Backend:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
uv run pytest -m integration
```

Os testes de integração usam Testcontainers e requerem Docker disponível.

Frontend:

```bash
npm run --prefix frontend lint
npm run --prefix frontend test
npm run --prefix frontend type-check
npm run --prefix frontend build
```

A CI executa checks separados para Ruff, MyPy, testes unitários, testes de
integração, lint do frontend, testes do frontend, type checking do frontend e
build Vite. A workflow é disparada em pull requests direcionados à branch `main`.

Na última auditoria, em 2026-08-23, passaram 312 testes Python sem a marca de
integração, 64 testes Python de integração e 10 testes do frontend. Esses números
são um snapshot e podem crescer; a fonte de verdade continua sendo a execução das
suítes.

## Organização do projeto

- `app/api` — rotas, dependências e tratamento HTTP;
- `app/application` — contratos, modelos de entrada e exceções da aplicação;
- `app/domain` — modelos e regras do domínio;
- `app/services` — casos de uso e coordenação de serviços;
- `app/infrastructure` — agentes, bancos, LLMs, logging e implementações técnicas;
- `frontend` — aplicação React/Vite;
- `migrations` — migrações Alembic;
- `tests` — testes unitários, arquiteturais e de integração;
- `data` — recursos estáticos usados pelos agentes.

O contexto arquitetural mais amplo e o escopo consolidado da migração para a
aplicação web estão em [`context.md`](context.md).

## Contribuição

### Specification-Driven Development (SDD)

The [SDD guide](specs/README.md) defines the specification-driven workflow in
English. Start with the [existing project baseline](specs/baseline.md), then use
the [specification](specs/templates/spec.md), [implementation plan](specs/templates/plan.md),
and [delivery tasks](specs/templates/tasks.md) templates for a concrete change.
Each feature records requirements, acceptance scenarios, and verification evidence
without changing the application's existing architecture.

Crie uma branch por alteração, mantenha commits pequenos e abra um pull request
para `main`. Não inclua arquivos `.env`, logs ou outros artefatos locais no
versionamento.


## Agenda local e Google Calendar por usuario

Esta funcionalidade e descrita em [spec.md](specs/001-agenda-google-calendar/spec.md).
A aplicacao usa Google para login; conectar Calendar exige consentimento adicional.
Cada identidade Google (subject verificado) corresponde a um usuario do Assessor.
O fluxo aceita apenas a mesma conta Google para login e Calendar. O destino desta
versao e o calendario principal, com eventos unicos e horarios definidos.

Configure um cliente OAuth Web e os redirects em .env.example. Um cliente separado
para Calendar pode ser informado. Habilite a Google Calendar API e configure os
usuarios de teste enquanto o consentimento estiver em modo de teste.
O padrao GOOGLE_CALENDAR_TRANSPORT=rest nao exige o programa de preview.
Opcionalmente, GOOGLE_CALENDAR_TRANSPORT=mcp exige Calendar MCP API e os requisitos
especificos do [MCP oficial](https://developers.google.com/workspace/calendar/api/guides/configure-mcp-server).
Nenhum recurso Cloud e provisionado automaticamente.
O escopo solicitado para escrita e calendar.events, separado dos escopos de login.
A disponibilidade real desse escopo/cliente deve ser verificada no ambiente Google.

GOOGLE_TOKEN_ENCRYPTION_KEY deve conter uma chave Fernet gerada e guardada como
segredo de implantacao. GOOGLE_TOKEN_KEY_ID identifica essa chave; mantenha chave e
ID enquanto houver tokens criptografados. Trocar apenas a chave invalida as
conexoes existentes: desconecte e refaca os consentimentos ou execute uma migracao
explicita de chaves. Nao coloque chaves nem tokens no Git. Os antigos nomes
`gcp-oauth.keys.json` e `google-calendar.token.json` sao ignorados, mas nao sao usados
por esta integracao Web. Nao ha token global compartilhado.

Em localhost, AUTH_SECURE_COOKIES=false permite HTTP. Fora de localhost, mantenha
true e HTTPS. Para Vite, APP_FRONTEND_URL pode ser http://localhost:5173/; as rotas
/api passam pelo proxy existente. Redirects OAuth continuam apontando para o
backend em 8000. Os URLs cadastrados no Google devem coincidir exatamente.

Execute a migracao Alembic para head no seu fluxo normal de implantacao. As novas
revisoes sao aditivas: nao removem transacoes nem alteram proprietarios. Usuarios
de demonstracao e seus dados ficam preservados, sem vinculo automatico a contas
Google; login novo cria uma identidade nova. A recuperacao verificada desses dados
legados exige uma funcionalidade futura. Nao use downgrade em banco populado como
rollback: os downgrades removem as tabelas novas e destinam-se a ambientes de teste
ou a operacoes explicitamente planejadas. Nenhuma migracao foi executada nos bancos
da aplicacao durante esta entrega.

Ao pedir um evento, informe titulo, inicio e termino/duracao; a aplicacao pergunta
quando faltar algum desses dados, sem assumir uma hora. query_events consulta so
os compromissos locais. Datas usam America/Sao_Paulo; o intervalo final e inclusivo
na consulta. Sem filtro de data, eventos passados tambem aparecem. Compromissos
exclusivos do Google nao sao usados para afirmar disponibilidade.

Conflitos bloqueiam a escrita. Use Revisar conflitos e depois Confirmar conflito;
o backend revalida os conflitos sob bloqueio por usuario. Se eles mudarem, exige
nova confirmacao. A proposta expira em 10 minutos. O modelo nao pode aprova-la.

O servico grava localmente antes de tentar Google, com prazo total de 30 segundos.
O caminho principal usa events.insert pela API REST, com o mesmo token por usuario.
No modo MCP opcional, usa initialize, tools/list e create_event; somente uma
rejeicao estruturada MCP SERVICE_DISABLED permite fallback REST.
Permissao negada, 5xx e timeout nao causam segunda gravacao. Falha remota preserva
sempre o evento local. pending/unknown significam resultado incerto: confira o
Calendar antes de repetir. Recibos bem-sucedidos sao reutilizados por operation_id.
Outra mensagem intencional do usuario constitui outra operacao.

Operacoes incertas exigem conciliacao manual por um operador, usando o recibo em
event_operations e uma consulta de leitura no Google antes de qualquer decisao de
nova criacao. Nao ha retentativa automatica nem garantia de exactly-once entre os
dois sistemas. Reiniciar nao reenvia operacoes pendentes. Desconectar remove tokens
locais, tenta revoga-los e preserva ambos os calendarios; a resposta indica se a
revogacao remota falhou. Refresh, uso e desconexao sao serializados por usuario.
Mantenha apenas um worker, conforme a restricao existente do projeto.

A memoria de conversas continua disponivel, mas nao comprova a existencia de
compromissos. O frontend, o servidor MCP financeiro local e os servicos financeiros
mantem suas responsabilidades; o MCP financeiro nao recebe acesso a tokens Google.

### Verificacao local sem Google

Os testes de banco usam containers descartaveis. Para os cenarios HTTP, inicie
`postman simulation run postman/simulations/google-calendar/google-calendar.sim.yaml --port 4900 --no-history`.
Defina CALENDAR_SIMULATION_URL=http://localhost:4900/google e execute
`uv run pytest -m integration tests/integration/test_google_calendar_http.py`.
A simulacao cobre REST como padrao, rejeicao e resultado incerto sem retentativa,
alem dos cenarios do MCP opcional. Os detalhes estao no contexto da simulacao em postman/simulations.
Ela nao usa credenciais reais nem confirma a elegibilidade do projeto Google.
O login/consentimento e uma criacao REST real com readback continuam sendo gates
antes de considerar a funcionalidade validada em ambiente real.

## Monitoramento de turnos

A [spec de observabilidade](specs/002-turn-observability/spec.md) descreve o
registro dos últimos 50 turnos concluídos do grafo. A
[spec de persistência](specs/003-telemetry-persistence/spec.md) acrescenta o
armazenamento dos turnos no MongoDB. O painel aparece
em **Monitoramento** para operadores autenticados com Google. Configure
`MONITOR_OPERATOR_EMAILS` como um array JSON de e-mails no ambiente, por exemplo
`["operador@example.com"]`, e reinicie a API. O padrão `[]` nega acesso a todos.
O servidor compara o e-mail verificado da sessão sem distinguir maiúsculas de
minúsculas. Nenhum e-mail enviado em um header concede acesso. A lista não é
devolvida ao navegador. `GET /api/monitor` retorna 401 sem login e 403 para quem
não está autorizado.

O painel atualiza a cada quatro segundos enquanto visível e mostra a visão global
do processo: latências, SLO, bloqueios, erros, cancelamentos, tokens, fallbacks,
custo conhecido e detalhes por turno, modelo e rota. O p95 usa nearest-rank.
O objetivo é p95 até 8 segundos e taxa de erro até 5%; sem turnos, o SLO fica sem
avaliação. Recusas por política não são erros; indisponibilidade do classificador
e cancelamento contam como falha. As medidas excluem espera de sessão,
autenticação e persistência HTTP.

O custo usa preços padrão verificados em 26/10/2026, sem desconto de cache.
Tokens ou preços indisponíveis tornam a estimativa parcial. O fallback financeiro
usa o mesmo modelo Groq disponível no roteador; o JEV permanece sem preço no catálogo local. Custo acumulado significa
somente a janela retida, nunca a fatura ou o total histórico. Reiniciar restaura
os 50 turnos mais recentes e reinicia apenas os contadores de atividade e uptime.
Use um único worker, conforme a
restrição do checkpointer atual; não há agregação entre processos.

Cada turno concluído é persistido na coleção `telemetry_turns` do MongoDB já
configurado. Chamadas e tempos dos nós ficam no mesmo documento, sem prompts,
respostas ou conteúdo das tools. O identificador do turno impede duplicatas;
o índice de consulta é criado automaticamente, sem migração PostgreSQL. Não há
TTL ou exclusão automática: o banco preserva todos os turnos, enquanto o painel
agrega os últimos 50. A política de retenção de longo prazo pode ser definida
posteriormente. Turnos que existiam somente em RAM antes da atualização não podem
ser recuperados retroativamente.

A gravação aguarda confirmação com journal e tem prazo total de dois segundos,
incluindo uma retentativa idempotente. Falhas não impedem a resposta do chat;
o painel sinaliza histórico não restaurado ou gravações não confirmadas. Não há
outbox durável: encerramento abrupto antes da confirmação ou indisponibilidade
prolongada do banco pode causar perda de telemetria. O shutdown normal aguarda
gravações pendentes antes de fechar a conexão MongoDB. Nenhum dado financeiro
ou de conversa é apagado por essa funcionalidade.

O LangSmith é opcional e vem desativado em `.env.example`. Para ativá-lo no seu
ambiente, configure `LANGSMITH_TRACING`, `LANGSMITH_API_KEY` e `LANGSMITH_PROJECT`.
O coletor local e o painel funcionam sem essa chave. O exporter explícito envia
somente metadados técnicos: topologia, duração, identificador do turno, modelo e
uso conhecido. Antes do envio ele remove mensagens, argumentos/resultados de
tools, objetos serializados, eventos livres e detalhes de exceções. Resumos de
sessão ficam fora dos traces. Não configure callbacks paralelos que enviem
conteúdo diretamente. Nunca versione uma chave.

A validação local usa o SDK real com transporte capturado para verificar árvore,
correlação, tokens e remoção de conteúdo. A entrega não ativou tracing nem alterou
contas externas; confira um turno sintético no projeto LangSmith após habilitá-lo
no ambiente de implantação.

## Validação de evidências e gravações financeiras

A [spec 004](specs/004-evidence-validation/spec.md) acrescenta o JEV da TypeSafe.
Configure sua própria `TYPESAFE_API_KEY` no `.env` e reinicie a API. O exemplo
versionado deixa a chave vazia: o servidor inicia, mas recusa respostas factuais
não verificadas e operações financeiras que dependem dessa validação. A chave
da aula não é reutilizada. O modelo é fixado em `jev-1.14.0`, com prazo de cinco
segundos por validação e sem retentativas automáticas.

O JEV recebe uma cópia minimizada da pergunta, resposta ou comando e evidências
necessárias. Identificadores, credenciais e contatos privados são removidos ou
substituídos consistentemente; valores, datas, moeda, comerciantes e fatos públicos
do FAQ necessários ao julgamento continuam sendo enviados à TypeSafe. Logs e
telemetria guardam somente metadados dessa validação. O custo do JEV permanece
marcado como incompleto enquanto não houver preço verificado no catálogo local.

Respostas geradas são verificadas após o compliance; FAQ e respostas diretas do
roteador também passam pelo juiz. Somente `apoiada` com `noul >= 0.70` preserva o
texto original. Nos outros casos, o chat informa que não tem evidência.

Novos valores financeiros exigem BRL explícito: por exemplo, “camisa por 120
reais”. Sem preço/moeda, com dólar/euro ou referência ambígua, o sistema pede
esclarecimento e não grava. Uma confirmação como “Sim” pode continuar o pedido
anterior que já contém o valor em BRL; a origem preserva a mensagem da compra.
Outro pedido, valor ou moeda no meio impede reaproveitar essa evidência. Alterações e cancelamentos resolvem o registro do
próprio usuário antes da validação, e a propriedade é conferida novamente na
escrita. Operações confirmadas geram recibos determinísticos, sem depender de um
novo julgamento após o commit. Não há transação distribuída entre banco, histórico
e entrega HTTP: em caso de resultado incerto, consulte antes de repetir.

Registros antigos sem indicação de outra moeda são presumidos em BRL, sem
reescrever dados. Um saldo cujo escopo inclua moeda estrangeira não é apresentado
como total em BRL. Alterar o valor de um registro explicitamente estrangeiro para
reais também é recusado, pois esta etapa não faz conversão. Cancelar/restaurar um
registro não exige repetir moeda e valor. Chamadas idênticas de escrita no mesmo
turno são deduplicadas; novas requisições e reinícios não possuem deduplicação
durável. Um turno com várias operações pode confirmar algumas antes de uma falha.

As tools de escrita do MCP exigem agora `operation_evidence`, contendo o pedido
confirmado pelo usuário. `source_text` sozinho não substitui esse contexto. As
tools continuam retornando envelopes estruturados e exigindo confirmação pelo
cliente; o servidor não comprova criptograficamente a origem dessa fala.

Testes locais: `uv run pytest`. Integração em containers descartáveis:
`uv run pytest -m integration`. A [simulação Postman](postman/simulations/jev/jev.context.md)
exercita HTTP real sem credenciais. A avaliação sintética em português é opt-in:
defina `RUN_JEV_EVALUATION=1` e execute
`uv run pytest -m integration tests/integration/test_jev_evaluation.py -s`.
Ela usa exclusivamente as [24 fixtures sintéticas](specs/004-evidence-validation/evaluation-cases.json).
A aprovação nos testes determinísticos não substitui esse gate de qualidade e
latência do modelo real.

Para verificar também o encaminhamento e a execução do grafo completo, defina
`RUN_GRAPH_EVALUATION=1` e execute
`uv run python -m tests.integration.test_live_financial_graph`. O teste usa compras
fictícias, modelos reais e repositórios falsos: não grava no seu banco. Ele executa
fora do pytest para usar a mesma construção LangChain/LangGraph da aplicação.
O roteador entrega uma decisão estruturada; relatos de compra seguem ao financeiro,
mesmo quando o especialista ainda precisa esclarecer algum dado.

Esclarecimentos financeiros pendentes mantêm o domínio para respostas curtas,
como “Sim”. A saída tipada do especialista é preservada antes da orquestração.
Quando o modelo apenas propõe uma escrita sem tentar ferramenta alguma, existe
no máximo uma correção de geração; ela mantém a validação do comando e nunca
repete uma escrita tentada, recusada, incerta ou confirmada.
