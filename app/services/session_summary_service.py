import traceback

from app.application.ports.logger import Logger, LoggerFactory
from app.application.ports.text_generator import TextGenerator
from app.domain.model.chat_entry import ChatEntry, ChatMessage

_MESSAGES_SUMMARY_PROMPT = """\
Você é um assistente que resume conversas de assessoria financeira e agenda.
Gere um resumo conciso em 2-4 frases capturando:
- O que o usuário fez (transações registradas, eventos agendados)
- O que o usuário perguntou
- Informações relevantes mencionadas (valores, datas, categorias)

Responda APENAS com o resumo, sem introdução ou explicação.

Conversa:
{conversa}
"""

_EXCEPTION_SUMMARY_PROMPT = """\
Você é responsável por converter exceções internas da 
aplicação em uma explicação curta e amigável para o usuário.

Sua resposta será armazenada no histórico de uma conversa e poderá ser utilizada 
posteriormente por outro agente para responder perguntas sobre o que aconteceu.

Objetivo:
Gerar um resumo fiel do erro em linguagem natural.

Regras:
- Escreva no máximo duas frases.
- Explique apenas o que aconteceu, não como corrigir.
- Não invente informações que não estejam evidentes no erro.
- Não mencione nomes de classes, funções, arquivos, 
    linhas de código ou stack traces.
- Não exponha detalhes internos da aplicação.
- Se a causa do erro estiver clara, mencione-a de forma simples.
- Se a causa não puder ser determinada com segurança, 
    diga apenas que ocorreu um erro interno inesperado.
- Escreva como se estivesse registrando um fato ocorrido 
    durante a conversa, e não respondendo diretamente ao usuário.
- Não use primeira pessoa ("eu", "nós").

Stack trace:
<stack_trace>
{}
</stack_trace>

Retorne apenas o resumo.
"""


class SessionSummaryService:
    def __init__(
        self, text_generator: TextGenerator, logger_factory: LoggerFactory
    ) -> None:
        self._text_generator = text_generator
        self._logger: Logger = logger_factory(__name__)

    def _format_conversation(self, entries: tuple[ChatEntry, ...]) -> str:
        """Formats entries array for summary"""
        lines = []
        for entry in entries:
            if isinstance(entry, ChatMessage):
                lines.append(f"{entry.role.value}: {entry.content}")
            else:
                lines.append(f"ERROR: {entry.exception} -> {entry.summary}")
        return "\n".join(lines)

    async def summarize_session(self, entries: tuple[ChatEntry, ...]) -> str:
        """Summarizes the session's entries"""
        self._logger.debug(
            "Summarizing entries",
            details={"entry_count": len(entries)},
        )

        conversation = self._format_conversation(entries)
        response = await self._text_generator.generate(
            _MESSAGES_SUMMARY_PROMPT.format(conversa=conversation)
        )

        return response.strip()

    async def summarize_exception(self, exc: Exception) -> str:
        """Summarizes the erro's traceback into a couple of friendly lines."""
        self._logger.debug(
            "Summarizing error", details={"exec_name": type(exc).__name__}
        )

        stack_trace = traceback.format_exception(type(exc), exc, exc.__traceback__)
        response = await self._text_generator.generate(
            _EXCEPTION_SUMMARY_PROMPT.format(stack_trace)
        )

        return response.strip()
