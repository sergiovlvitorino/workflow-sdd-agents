"""Problem Details (RFC 9457) — ApiError e exception handlers centralizados."""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from blog.application.create_post import IdempotencyConflict
from blog.application.cursor import InvalidCursor
from blog.application.publish_post import PostNotFound

_BASE_TYPE = "https://blog-tutorial/errors"

PROBLEM_JSON = "application/problem+json"


class IdempotencyKeyRequired(Exception):
    """Header Idempotency-Key ausente/vazio em rota de escrita → 400."""


def _error_body(
    type_suffix: str,
    title: str,
    status: int,
    detail: str | None = None,
    errors: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "type": f"{_BASE_TYPE}/{type_suffix}",
        "title": title,
        "status": status,
    }
    if detail is not None:
        body["detail"] = detail
    if errors:
        body["errors"] = errors
    return body


def _request_id_of(request: Request) -> str:
    """Lê o request_id do state (setado pelo middleware) ou ContextVar de fallback."""
    # Import local para evitar circular import entre errors e observability
    from blog.interfaces.observability import request_id_of

    return request_id_of(request)


def _log_error(rid: str, request: Request, status: int) -> None:
    """Emite log JSON Lines de erro correlacionado (level=error, allowlist)."""
    from blog.interfaces.observability import _route_template, _utc_now, emit_event

    emit_event(
        timestamp=_utc_now(),
        level="error",
        request_id=rid,
        method=request.method,
        route=_route_template(request),
        status=status,
    )


async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    rid = _request_id_of(request)
    field_errors = [
        {
            "field": ".".join(str(loc) for loc in err["loc"] if loc != "body"),
            "code": err["type"],
            "message": err["msg"],
        }
        for err in exc.errors()
    ]
    body = _error_body(
        type_suffix="validation_error",
        title="Erro de validação",
        status=422,
        detail="Um ou mais campos são inválidos.",
        errors=field_errors,
    )
    _log_error(rid, request, 422)
    return JSONResponse(
        status_code=422,
        content=body,
        media_type=PROBLEM_JSON,
        headers={"X-Request-ID": rid},
    )


async def handle_idempotency_key_required(request: Request, exc: IdempotencyKeyRequired) -> JSONResponse:
    rid = _request_id_of(request)
    body = _error_body(
        type_suffix="idempotency_key_required",
        title="Idempotency-Key obrigatório",
        status=400,
        detail="O header 'Idempotency-Key' é obrigatório em rotas de escrita.",
    )
    _log_error(rid, request, 400)
    return JSONResponse(
        status_code=400,
        content=body,
        media_type=PROBLEM_JSON,
        headers={"X-Request-ID": rid},
    )


async def handle_idempotency_conflict(request: Request, exc: IdempotencyConflict) -> JSONResponse:
    rid = _request_id_of(request)
    body = _error_body(
        type_suffix="idempotency_key_conflict",
        title="Conflito de idempotência",
        status=409,
        detail="A chave de idempotência já foi usada com um payload diferente.",
    )
    _log_error(rid, request, 409)
    return JSONResponse(
        status_code=409,
        content=body,
        media_type=PROBLEM_JSON,
        headers={"X-Request-ID": rid},
    )


async def handle_invalid_cursor(request: Request, exc: InvalidCursor) -> JSONResponse:
    rid = _request_id_of(request)
    body = _error_body(
        type_suffix="invalid_cursor",
        title="Cursor inválido",
        status=400,
        detail="O cursor de paginação é malformado ou corrompido.",
    )
    _log_error(rid, request, 400)
    return JSONResponse(
        status_code=400,
        content=body,
        media_type=PROBLEM_JSON,
        headers={"X-Request-ID": rid},
    )


async def handle_post_not_found(request: Request, exc: PostNotFound) -> JSONResponse:
    """404 genérico para PostNotFound — detalhe não revela existência (ADR-0004 §8)."""
    rid = _request_id_of(request)
    body = _error_body(
        type_suffix="post_not_found",
        title="Post não encontrado",
        status=404,
        detail="Nenhum post publicado com o id informado.",
    )
    _log_error(rid, request, 404)
    return JSONResponse(
        status_code=404,
        content=body,
        media_type=PROBLEM_JSON,
        headers={"X-Request-ID": rid},
    )
