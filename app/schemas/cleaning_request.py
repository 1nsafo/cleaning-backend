import re
from enum import StrEnum
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator


class CleaningType(StrEnum):
    MAINTENANCE = "maintenance"
    GENERAL = "general"
    AFTER_RENOVATION = "after_renovation"


class ContactMethod(StrEnum):
    CALL = "call"
    MESSAGE = "message"


class CleaningRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    phone: str = Field(min_length=5, max_length=32)
    cleaning_type: CleaningType
    contact_method: ContactMethod
    name: str | None = Field(default=None, max_length=100)
    comment: str | None = Field(default=None, max_length=2000)
    privacy_consent: StrictBool

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value: str) -> str:
        if not re.fullmatch(r"[+0-9 ()-]+", value):
            raise ValueError("Недопустимые символы в телефоне")
        number = re.sub(r"[ ()-]", "", value)
        if re.fullmatch(r"8[0-9]{10}", number):
            number = "+7" + number[1:]
        elif re.fullmatch(r"7[0-9]{10}", number):
            number = "+" + number
        if not re.fullmatch(r"\+7[0-9]{10}", number):
            raise ValueError("Укажите телефон в формате +7XXXXXXXXXX")
        return number

    @field_validator("privacy_consent")
    @classmethod
    def require_consent(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Необходимо согласие на обработку персональных данных")
        return value

    @field_validator("name", "comment")
    @classmethod
    def empty_to_none(cls, value: str | None) -> str | None:
        return value or None


class CleaningRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    status: str
