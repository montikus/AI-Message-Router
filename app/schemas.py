from enum import StrEnum
from typing import Literal
from uuid import UUID

# This is test task done by Roman Nadkernychnyi. For recruitment purposes only. 
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class Department(StrEnum):
    HR = "human-resources@example.com"
    HELP_DESK = "help-desk@example.com"
    IT = "it@example.com"
    KADRY = "kadry@example.com"
    OTHER = "other@example.com"


class MessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(examples=["jan.nowak@example.com"])
    message: str = Field(min_length=1, max_length=4000, examples=["Nie działa mi komputer"])

    @field_validator("email", mode="before")
    @classmethod
    def reject_email_header_injection(cls, value: object) -> object:
        if isinstance(value, str) and ("\r" in value or "\n" in value):
            raise ValueError("Email must not contain newlines")
        return value

    @field_validator("message")
    @classmethod
    def reject_blank_message(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Message must not be blank")
        return value  # Preserve the original text, including whitespace.


class SendEmailArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipient: Department


class MessageResponse(BaseModel):
    status: Literal["sent"] = "sent"
    request_id: UUID
    recipient: Department
    message_id: str


class ErrorResponse(BaseModel):
    detail: str
