# Perfil financeiro do usuário

Objetivo: salvar o perfil pela tela React existente e usá-lo para fundamentar o aconselhamento do especialista financeiro, com identidade fornecida pelo servidor e preferências consultadas semanticamente.

## Quais arquivos foram criados ou modificados?

Nesta implementação, posterior à API dummy:

- Domínio e contratos: `app/domain/model/user_profile.py`, `app/application/repositories/user_profile_repository.py`, `app/application/ports/profile_preferences_index.py`, `app/application/exceptions.py`.
- Persistência MongoDB: `app/infrastructure/mongodb/entities/user_profile.py`, `app/infrastructure/mongodb/mappers/user_profile_mapper.py`, `app/infrastructure/mongodb/repositories/user_profile_repository.py`, `app/infrastructure/mongodb/client.py`.
- Persistência vetorial e serviço: `app/infrastructure/vectorstore/repositories/profile_preferences_index.py`, `app/services/user_profile_service.py`.
- API e inicialização: `app/api/routes/profile.py`, `app/api/dependencies.py`, `app/api/middleware/exception_handler.py`, `app/lifespan.py`.
- Agente: `app/infrastructure/agents/tools/consult_profile.py`, `app/infrastructure/agents/composition.py`, `app/infrastructure/agents/financial/financial_agent.py`, `app/infrastructure/agents/financial/financial_prompt.py`.
- Testes: `tests/test_models/test_user_profile.py`, `tests/test_repositories/test_user_profile_repository.py`, `tests/test_infrastructure/test_profile_preferences_index.py`, `tests/test_services/test_user_profile_service.py`, `tests/test_tools/test_consult_profile.py`, `tests/test_agents/test_composition.py`, `tests/test_agents/test_specialist_prompts.py`, `tests/test_api/test_profile_route.py`, `tests/test_api/test_history_composition.py`, `tests/integration/test_profile_workflow.py`, `tests/integration/test_agents/conftest.py`.
- Documentação: `JUSTIFICATIVA.md`.

## Por onde o perfil entra e onde cada parte é gravada?

O `POST /api/profile` recebe `monthly_revenue`, `objective`, `risk_tolerance` e `preferences`; o UUID vem do header `X-User-ID`, validado contra os usuários existentes. O serviço grava `user_profiles` no MongoDB e `profile_preferences` no Qdrant antes de responder com sucesso.

## Como as preferências são guardadas e consultadas e por que não é busca por palavra?

O texto completo recebe um embedding de documento; a pergunta recebe um embedding de consulta e o Qdrant calcula similaridade cosseno com filtro por usuário. Existe um ponto por usuário, substituído a cada salvamento, e uma cópia do texto no MongoDB permite detectar um índice desatualizado; não há filtro por palavras. Uma busca por palavras seria insegura pois as preferências indicam intenção. Se eu digo nas preferências que não quero nenhum investimento de alto risco, uma busca por cripto deve retornar o point das preferências pois a intenção é relacionada, o que uma busca por palavra não faria

## Foi criada uma tool ou duas e por quê?

Uma tool, `consult_profile`, reúne os dados estruturados e as preferências recuperadas semanticamente. Assim, o especialista recebe o contexto completo em uma chamada, sem precisar decidir quais das duas fontes consultar.

## O que impede que o perfil de um usuário apareça para outro?

A tool obtém o UUID pelo contexto de execução, sem argumento de identidade no schema exposto ao modelo. MongoDB usa esse UUID como chave primária, Qdrant exige o filtro `user_id`, e a consulta verifica novamente a identidade devolvida por ambas as fontes.

## A tool consulta o banco diretamente ou chama a própria API?

A tool chama o serviço de aplicação com repositórios injetados, sem HTTP interno. A rota e o agente compartilham a mesma implementação de aplicação; a tool expõe somente consulta.

## Por que não existe um agente perfil?

O perfil é contexto do especialista financeiro já existente, não um novo domínio de roteamento. A ferramenta foi adicionada somente ao financeiro, preservando agenda, FAQ e memória.

## Por que o chat não altera o cadastro?

A escrita está disponível apenas pela rota consumida pela tela Perfil; não existe tool de salvar perfil. O prompt orienta a usar essa tela e proíbe representar mudanças do perfil como transações ou alegar que o chat salvou o cadastro. Além disso, se o chat pudesse alterar o cadastro seria difícil rastrear as alterações além de abrir espaço para alucinações alterando um registro do usuário.

## Consistência e limites operacionais

Os upserts usam chaves determinísticas. Uma falha em qualquer gravação retorna HTTP 503 e uma nova tentativa substitui os mesmos registros; não existe transação distribuída nem reparo automático em segundo plano.

O serviço compartilhado serializa gravações e consultas dentro do processo. Ele recusa consultas quando as preferências do índice divergem do MongoDB, inclusive após falha parcial. Múltiplos processos não compartilham esse bloqueio: escritas concorrentes entre workers podem exigir novo salvamento para reconciliar os bancos.

As collections usam a infraestrutura já configurada. A inicialização cria a collection de preferências e seu índice de identidade, valida dimensão e distância vetorial e não recria collections incompatíveis. Nenhuma configuração de cluster ou frontend foi alterada nesta etapa.

## Verificação

Os testes cobrem validação, header ausente/inválido/desconhecido, falha pública, substituição, isolamento, contexto concorrente da tool e composição dos agentes. O teste `tests/integration/test_profile_workflow.py` percorre HTTP, MongoDB real descartável, Qdrant local e tool, incluindo novo salvamento e consulta por dois usuários.

Os embeddings dos testes são simulados; a qualidade semântica do provedor e o comportamento probabilístico do LLM exigem verificação manual no ambiente configurado. Execute a suíte comum com `uv run pytest -p no:cacheprovider` e o teste integrado com `uv run pytest tests/integration/test_profile_workflow.py -m integration -p no:cacheprovider` (Docker necessário).
