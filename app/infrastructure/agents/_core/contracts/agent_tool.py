from abc import abstractmethod
from typing import Annotated, Any, Self, cast

from langchain.tools import BaseTool
from pydantic import BaseModel, Field, PrivateAttr, model_validator

from app.application.exceptions import ApplicationError
from app.application.ports.logger import Logger, LoggerFactory

from ..schemas.tool_response import ToolFailure, ToolResponse, ToolSuccess


class AgentTool[ArgsSchema: BaseModel, Response: BaseModel](BaseTool):
    args_schema: type[BaseModel]

    logger_factory: Annotated[LoggerFactory, Field(exclude=True)]
    log_details: Annotated[dict[str, Any], Field(exclude=True)] = {}

    _logger: Logger = PrivateAttr()

    @model_validator(mode="after")
    def model_post_validate(self) -> Self:
        self._logger = self.logger_factory(type(self).__module__)
        return self

    @abstractmethod
    async def _execute(self, args: ArgsSchema) -> Response: ...

    def _run(self, *args: Any, **kwargs: Any) -> ToolResponse[Response]:
        raise NotImplementedError("Use the asynchronous tool")

    async def _arun(self, **kwargs: Any) -> ToolResponse[Response]:
        self._logger.debug(
            "Tool called",
            details={
                "tool": self.name,
                **kwargs,
            },
        )

        try:
            args = self.args_schema(**kwargs)
            typed_args = cast(ArgsSchema, args)
            result = await self._execute(args=typed_args)

            self._logger.debug("Tool succeeded", details={"result": result})
            return ToolSuccess(data=result)

        except ApplicationError as error:
            self._logger.warning(
                "Tool rejected operation",
                details={
                    "tool": self.name,
                    "error_code": error.code,
                },
            )
            return ToolFailure.application_error(error)

        except Exception as e:
            self._logger.exception(
                "Async tool failed",
                exception=e,
                details={"tool": self.name},
            )
            return ToolFailure.unexpected_error()
