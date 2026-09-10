from unittest.mock import MagicMock

from app.application.ports.faq_search import FaqSearch
from app.infrastructure.agents._core.schemas.tool_response import ToolSuccess
from app.infrastructure.agents.tools.faq_rag import FaqRag, GetFAQAnswerResponse


def test_searches_faq_through_injected_port(
    mock_logger_factory: MagicMock,
) -> None:
    faq_search = MagicMock(spec=FaqSearch)
    faq_search.search.return_value = ["Trecho relevante"]
    tool = FaqRag(
        faq_search=faq_search,
        logger_factory=mock_logger_factory,
    )

    result = tool._run("Como funciona o sistema?")

    assert isinstance(result, ToolSuccess)
    assert isinstance(result.data, GetFAQAnswerResponse)
    assert result.data.response == ["Trecho relevante"]
    faq_search.search.assert_called_once_with(
        "Como funciona o sistema?",
        limit=6,
    )
