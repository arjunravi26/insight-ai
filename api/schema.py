from typing import Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from datetime import datetime

class ChatRequest(BaseModel):
    document_id: str = Field(min_length=1, max_length=100)
    query: str = Field(min_length=1, max_length=10000)
    model: Literal["Gemini", "Mistral", "Groq"] = Field(
        default="Groq", description="The model to use for generating the response. Options are 'Gemini', 'Mistral', or 'Groq'.")


class ChatResponse(BaseModel):
    answer: str
    follow_ups: list[str] = Field(default_factory=list)


class DocumentUploadResponse(BaseModel):
    document_id: str
    job_id: str
    filename: str
    document_status: str
    job_status: str
    message: str
    created_at: datetime


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"