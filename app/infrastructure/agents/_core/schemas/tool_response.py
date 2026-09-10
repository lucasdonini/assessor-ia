from typing import Literal

from pydantic import BaseModel, Field, JsonValue

from app.application.exceptions import ApplicationError


class ToolSuccess[T: BaseModel](BaseModel):
    status: Literal["ok"] = "ok"
    data: T


class ToolFailure(BaseModel):
    status: Literal["error"] = "error"
    code: str = "tool_error"
    error: str
    details: dict[str, JsonValue] = Field(default_factory=dict)

    @classmethod
    def application_error(cls, error: ApplicationError) -> "ToolFailure":
        return cls(
            code=error.code,
            error=error.public_message,
        )

    @classmethod
    def unexpected_error(cls) -> "ToolFailure":
        return cls(
            code="unexpected_error",
            error="Não foi possível concluir a operação.",
        )

    @classmethod
    def exception(cls, _: Exception) -> "ToolFailure":
        return cls.unexpected_error()


type ToolResponse[T: BaseModel] = ToolSuccess[T] | ToolFailure
