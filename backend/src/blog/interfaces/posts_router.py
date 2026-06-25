"""Router de posts — interface HTTP para POST /v1/posts, PUT /v1/posts/{id}/publish e GET /v1/posts."""

from __future__ import annotations

import hashlib
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import JSONResponse

from blog.application.create_post import IdempotencyConflict
from blog.interfaces.errors import IdempotencyKeyRequired
from blog.interfaces.schemas import ApiError, CreatePostRequest, PageResponse, PostResponse

router = APIRouter(prefix="/v1/posts", tags=["posts"])


def require_idempotency_key(
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> str:
    """Dependency que valida presença do header Idempotency-Key → 400 se ausente."""
    if not idempotency_key or not idempotency_key.strip():
        raise IdempotencyKeyRequired()
    return idempotency_key


@router.post(
    "",
    status_code=201,
    response_model=PostResponse,
    responses={
        200: {"model": PostResponse, "description": "Replay idempotente (Idempotent-Replayed: true)"},
        400: {"model": ApiError, "description": "Idempotency-Key ausente"},
        409: {"model": ApiError, "description": "Conflito de idempotência"},
        422: {"model": ApiError, "description": "Erro de validação"},
    },
)
async def create_post(
    request: Request,
    body: CreatePostRequest,
    idem_key: Annotated[str, Depends(require_idempotency_key)],
) -> JSONResponse:
    """Cria post com idempotência (CA-F001-01..04)."""
    use_case = request.app.state.create_post_use_case
    response_dict: dict[str, Any]
    response_dict, replayed = use_case.execute(
        key=idem_key,
        title=body.title,
        content=body.content,
    )

    if replayed:
        return JSONResponse(
            status_code=200,
            content=response_dict,
            headers={"Idempotent-Replayed": "true"},
        )

    return JSONResponse(status_code=201, content=response_dict)


@router.put(
    "/{post_id}/publish",
    status_code=200,
    response_model=PostResponse,
    responses={
        400: {"model": ApiError, "description": "Idempotency-Key ausente"},
        404: {"model": ApiError, "description": "Post não encontrado"},
        409: {"model": ApiError, "description": "Conflito de idempotência"},
    },
)
async def publish_post(
    request: Request,
    post_id: str,
    idem_key: Annotated[str, Depends(require_idempotency_key)],
) -> JSONResponse:
    """Publica um post (CA-F002-01..03). Transição aberta — sem auth (ADR-0004).

    Replay opção B (DETAIL §4.2):
    - store_key = f"publish:{idem_key}" — namespace por rota, evita colisão com POST /v1/posts
      que grava a chave crua. O idem_key do header honra o piso P-03.
    - payload_hash = sha256(post_id) — discrimina recurso → 409 cross-id.
    - 1ª chamada: executa PublishPost, persiste resposta com store_key.
    - Replay (mesma Idempotency-Key + mesmo post_id) → 200 + Idempotent-Replayed: true.
    - Mesma Idempotency-Key + post_id diferente → hashes divergem → 409.
    """
    idem_store = request.app.state.idem_store
    use_case = request.app.state.publish_post_use_case

    store_key = f"publish:{idem_key}"
    # Hash derivado do post_id (sem corpo — identifica o recurso alvo)
    payload_hash = hashlib.sha256(post_id.encode()).hexdigest()

    existing = idem_store.get(store_key)
    if existing is not None:
        stored_hash, stored_resp = existing
        if stored_hash != payload_hash:
            raise IdempotencyConflict()
        return JSONResponse(
            status_code=200,
            content=dict(stored_resp),
            headers={"Idempotent-Replayed": "true"},
        )

    # PostNotFound propaga → handle_post_not_found → 404
    response_dict: dict[str, Any] = use_case.execute(post_id)
    idem_store.put(store_key, payload_hash, response_dict)
    return JSONResponse(status_code=200, content=response_dict)


@router.get(
    "/{post_id}",
    status_code=200,
    response_model=PostResponse,
    responses={
        404: {"model": ApiError, "description": "Post não encontrado"},
    },
)
async def get_post(request: Request, post_id: str) -> JSONResponse:
    """Lê post publicado por id (CA-F004-01/02). Rascunho/inexistente → 404 (P-04)."""
    use_case = request.app.state.get_post_use_case
    response_dict: dict[str, Any] = use_case.execute(post_id)  # PostNotFound → handler → 404
    return JSONResponse(status_code=200, content=response_dict)


@router.get(
    "",
    status_code=200,
    response_model=PageResponse,
    responses={
        400: {"model": ApiError, "description": "Cursor inválido"},
    },
)
async def list_posts(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    cursor: Annotated[str | None, Query()] = None,
) -> JSONResponse:
    """Lista posts publicados com paginação keyset (CA-F003-01..03, ADR-0002)."""
    use_case = request.app.state.list_posts_use_case
    page: dict[str, Any] = use_case.execute(limit=limit, cursor=cursor)
    return JSONResponse(status_code=200, content=page)
