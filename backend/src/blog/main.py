"""Composição da aplicação: adapters, casos de uso, app FastAPI."""

from __future__ import annotations

import collections.abc
import os
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from blog.application.create_post import CreatePost, IdempotencyConflict
from blog.application.cursor import InvalidCursor
from blog.application.get_post import GetPublishedPost
from blog.application.list_published_posts import ListPublishedPosts
from blog.application.ports import IdempotencyStore, PostRepository
from blog.application.publish_post import PostNotFound, PublishPost
from blog.infrastructure.sqlite_repository import (
    SqliteHandle,
    SqliteIdempotencyStore,
    SqlitePostRepository,
    init_schema,
    make_connection,
)
from blog.interfaces.errors import (
    IdempotencyKeyRequired,
    handle_idempotency_conflict,
    handle_idempotency_key_required,
    handle_invalid_cursor,
    handle_post_not_found,
    handle_validation_error,
)
from blog.interfaces.health_router import router as health_router
from blog.interfaces.observability import install_observability
from blog.interfaces.posts_router import router as posts_router


def _utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _new_ulid() -> str:
    from ulid import ULID

    return str(ULID())


def create_app(
    *,
    repo: PostRepository | None = None,
    idem: IdempotencyStore | None = None,
    id_gen: collections.abc.Callable[[], str] | None = None,
) -> FastAPI:
    """Fábrica de app — permite criar instâncias isoladas para testes.

    repo/idem=None → default de runtime = SQLite (BLOG_DB_PATH ou 'blog.db').
    Injete InMemoryPostRepository/InMemoryIdempotencyStore nos testes unit/integration.
    """
    resolved_id_gen = id_gen if id_gen is not None else _new_ulid
    app = FastAPI(title="Blog Tutorial API", version="1.1.0")

    if repo is None or idem is None:
        # Default de runtime: SQLite persistente (ADR-0003)
        db_path = os.environ.get("BLOG_DB_PATH", "blog.db")
        handle: SqliteHandle = make_connection(db_path)
        init_schema(handle.conn)
        post_repo: PostRepository = repo if repo is not None else SqlitePostRepository(handle.conn, handle.lock)
        idem_store: IdempotencyStore = idem if idem is not None else SqliteIdempotencyStore(handle.conn, handle.lock)
    else:
        post_repo = repo
        idem_store = idem

    # Casos de uso com dependências injetadas
    app.state.create_post_use_case = CreatePost(
        repo=post_repo,
        idem=idem_store,
        clock=_utc_now,
        id_gen=_new_ulid,
    )
    app.state.publish_post_use_case = PublishPost(repo=post_repo, clock=_utc_now)
    app.state.get_post_use_case = GetPublishedPost(repo=post_repo)
    app.state.list_posts_use_case = ListPublishedPosts(repo=post_repo)
    # Expor o repo e idem_store para asserções de estado em testes de integração
    app.state.post_repo = post_repo
    app.state.idem_store = idem_store

    # Middleware único de observabilidade (ADR-0006 §8 / T-S3-04)
    install_observability(app, id_gen=resolved_id_gen)

    # Routers
    app.include_router(posts_router)
    app.include_router(health_router)

    # Exception handlers centralizados (P-11)
    app.add_exception_handler(RequestValidationError, handle_validation_error)  # type: ignore[arg-type]
    app.add_exception_handler(IdempotencyKeyRequired, handle_idempotency_key_required)  # type: ignore[arg-type]
    app.add_exception_handler(IdempotencyConflict, handle_idempotency_conflict)  # type: ignore[arg-type]
    app.add_exception_handler(InvalidCursor, handle_invalid_cursor)  # type: ignore[arg-type]
    app.add_exception_handler(PostNotFound, handle_post_not_found)  # type: ignore[arg-type]

    return app


app = create_app()

if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run("blog.main:app", host="0.0.0.0", port=8000, reload=True)
