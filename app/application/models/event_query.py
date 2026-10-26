from datetime import date
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EventQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str | None = Field(default=None, max_length=1000)
    date_local: date | None = None
    date_from_local: date | None = None
    date_to_local: date | None = None
    limit: int = Field(default=20, ge=1, le=200)

    @model_validator(mode="after")
    def validate_range(self) -> Self:
        if self.date_local and (self.date_from_local or self.date_to_local):
            raise ValueError("Use a day OR a range")
        if (
            self.date_from_local
            and self.date_to_local
            and self.date_from_local > self.date_to_local
        ):
            raise ValueError("Invalid date range")
        return self
