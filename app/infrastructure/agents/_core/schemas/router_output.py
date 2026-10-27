import re
from collections.abc import Sequence
from typing import Self

from pydantic import BaseModel, Field, JsonValue, create_model, model_validator


class RouterOutput(BaseModel):
    route: str
    response: str = Field(
        description="Texto ao usuário somente para route=direct; vazio ao encaminhar."
    )

    @model_validator(mode="after")
    def validate_direct_response(self) -> Self:
        if self.route == "direct" and not self.response.strip():
            raise ValueError("A direct route requires a response")
        if self.route != "direct" and self.response:
            raise ValueError("A specialist route cannot contain a direct response")
        return self


def router_output_schema(routes: Sequence[str]) -> type[RouterOutput]:
    allowed = ["direct", *routes]
    if "direct" in routes:
        raise ValueError("direct is reserved for router responses")
    enum_values: list[JsonValue] = list(allowed)
    pattern = "^(?:" + "|".join(re.escape(route) for route in allowed) + ")$"
    return create_model(
        "RoutingDecision",
        __base__=RouterOutput,
        route=(str, Field(pattern=pattern, json_schema_extra={"enum": enum_values})),
    )
