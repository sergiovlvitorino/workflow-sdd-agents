"""Schemas Pydantic v2 — conforme 005-api-contract §3/§4."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class CreatePostRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=50000)

    @field_validator("title", mode="before")
    @classmethod
    def strip_title(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("content", mode="before")
    @classmethod
    def strip_content(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v


class PostResponse(BaseModel):
    """Schema de resposta de post (005-api-contract §3).

    ATENÇÃO: created_at/published_at são declarados como str (não datetime) para
    preservar o sufixo 'Z' entregue por to_response_dict (application/serialization.py). Se fossem datetime,
    o Pydantic v2 re-serializaria como '+00:00', quebrando o contrato do 005 §3.
    O OpenAPI ainda sai como type: string, format: date-time via Field(examples).
    """

    id: str
    title: str
    content: str
    status: Literal["draft", "published"]
    created_at: str = Field(examples=["2026-06-25T10:00:00Z"])
    published_at: str | None = Field(default=None, examples=["2026-06-25T10:00:00Z"])

    model_config = {"populate_by_name": True}


class PageResponse(BaseModel):
    """Page<Post> conforme 005-api-contract §3 (sem total/page — ADR-0002)."""

    items: list[PostResponse]
    next_cursor: str | None
    limit: int


class HealthResponse(BaseModel):
    """Resposta do liveness endpoint GET /v1/health (CA-F006-01)."""

    status: Literal["ok"]


class ApiError(BaseModel):
    """Problem Details RFC 9457 — catálogo de erros conforme 005-api-contract §4."""

    type: str = Field(examples=["https://blog-tutorial/errors/validation_error"])
    title: str = Field(examples=["Erro de validação"])
    status: int = Field(examples=[422])
    detail: str | None = Field(default=None, examples=["Um ou mais campos são inválidos."])
    errors: list[dict[str, Any]] | None = Field(default=None)
