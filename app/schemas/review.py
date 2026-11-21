from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ReviewSort = Literal["newest", "oldest", "highest", "lowest"]


class ReviewCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    rating: int = Field(ge=1, le=5)
    comment: str = Field(min_length=10, max_length=2000)
    website: str = Field(default="", max_length=200)

    @field_validator("name", "comment")
    @classmethod
    def trim(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Поле не может быть пустым")
        return value


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    rating: int
    comment: str
    created_at: datetime


class ReviewStats(BaseModel):
    count: int
    average: float
    distribution: dict[int, int]
