from pydantic import BaseModel, Field
from typing import Literal


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
    filename: str
    status: str
    result: dict
