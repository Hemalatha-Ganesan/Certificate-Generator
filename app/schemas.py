from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

MAX_RECIPIENTS = 1000


class RecipientIn(BaseModel):
    name: str = Field(..., max_length=100)
    email: EmailStr

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be blank")
        return v


class JobCreate(BaseModel):
    course_title: str = Field(..., min_length=1, max_length=200)
    date: str = Field(..., min_length=1, max_length=50)
    recipients: List[RecipientIn] = Field(..., min_length=1, max_length=MAX_RECIPIENTS)


class CertificateOut(BaseModel):
    id: str
    name: str
    email: str
    status: str
    error_message: Optional[str] = None

    model_config = {"from_attributes": True}


class JobCreated(BaseModel):
    job_id: str
    status: str
    total: int


class JobOut(BaseModel):
    id: str
    course_title: str
    date: str
    status: str
    total: int
    success_count: int
    failed_count: int
    created_at: datetime
    certificates: List[CertificateOut]

    model_config = {"from_attributes": True}