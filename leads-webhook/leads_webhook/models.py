from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

Category = Literal["new_order", "pricing", "support", "partnership", "other"]
Priority = Literal["low", "normal", "high"]
ClassifierName = Literal["rules", "llm"]
NotifyChannel = Literal["telegram", "console", "failed"]


class LeadIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    phone: str | None = None
    email: str | None = None
    message: str = Field(min_length=5, max_length=4000)
    source: str = Field(default="website", min_length=1, max_length=80)

    @field_validator("name", "message", "source", mode="before")
    @classmethod
    def _strip_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("phone", "email", mode="before")
    @classmethod
    def _blank_to_none(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("phone")
    @classmethod
    def _check_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        digits = re.sub(r"\D", "", value)
        if not 10 <= len(digits) <= 15:
            raise ValueError("телефон должен содержать от 10 до 15 цифр")
        return value

    @field_validator("email")
    @classmethod
    def _check_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if _EMAIL.fullmatch(value) is None:
            raise ValueError("некорректный email")
        return value

    @model_validator(mode="after")
    def _need_contact(self) -> LeadIn:
        if not self.phone and not self.email:
            raise ValueError("нужен телефон или email")
        return self


class Classification(BaseModel):
    category: Category
    priority: Priority
    summary: str = Field(min_length=1, max_length=160)
    source: ClassifierName


class LeadAccepted(BaseModel):
    id: str
    name: str
    category: Category
    priority: Priority
    summary: str
    classifier: ClassifierName
    stored: list[str]
    notified: NotifyChannel
