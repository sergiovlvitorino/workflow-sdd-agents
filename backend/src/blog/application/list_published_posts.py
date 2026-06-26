"""Caso de uso: listar posts publicados com paginação keyset (ADR-0002)."""

from __future__ import annotations

from typing import Any

from blog.application.cursor import decode_cursor, encode_cursor
from blog.application.ports import PostRepository
from blog.application.serialization import to_response_dict


class ListPublishedPosts:
    def __init__(self, repo: PostRepository) -> None:
        self._repo = repo

    def execute(self, *, limit: int, cursor: str | None) -> dict[str, Any]:
        """Retorna Page<Post> conforme 005-api-contract §3.

        cursor=None → primeira página.
        cursor inválido → propaga InvalidCursor → handler → 400.
        Padrão limit+1: busca um item a mais para detectar próxima página sem COUNT.
        """
        after = decode_cursor(cursor) if cursor else None

        # +1 para saber se há próxima página sem COUNT (ADR-0002)
        page = self._repo.list_published(after=after, limit=limit + 1)

        has_more = len(page) > limit
        items = page[:limit]

        next_cursor: str | None = None
        if has_more and items:
            last = items[-1]
            assert last.published_at is not None  # invariante: só publicados chegam aqui
            next_cursor = encode_cursor(last.published_at, last.id)

        return {
            "items": [to_response_dict(p) for p in items],
            "next_cursor": next_cursor,
            "limit": limit,
        }
