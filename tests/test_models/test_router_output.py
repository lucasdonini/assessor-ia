import pytest
from pydantic import ValidationError

from app.infrastructure.agents._core.schemas.router_output import router_output_schema


def test_routes_come_from_registered_catalog():
    schema = router_output_schema(("financial", "agenda"))
    assert schema(route="financial", response="").route == "financial"
    assert schema(route="direct", response="Olá").response == "Olá"
    with pytest.raises(ValidationError):
        schema(route="faq", response="")


@pytest.mark.parametrize("route,response", [("direct", ""), ("financial", "Gravei!")])
def test_direct_text_and_delegation_are_mutually_exclusive(route, response):
    with pytest.raises(ValidationError):
        router_output_schema(("financial",))(route=route, response=response)
