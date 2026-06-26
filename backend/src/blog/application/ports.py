"""Portas (Protocols) — contratos das fronteiras de saída (P-12)."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from blog.domain.post import Post


class PostRepository(Protocol):
    def add(self, post: Post) -> None: ...

    def get(self, id: str) -> Post | None: ...

    def count(self) -> int: ...

    def list_published(
        self,
        *,
        after: tuple[datetime, str] | None,
        limit: int,
    ) -> list[Post]:
        """Retorna até `limit` posts publicados após o cursor keyset (published_at DESC, id DESC).

        after=None → primeira página. Keyset estrito `<` (ADR-0002).
        """
        ...


class IdempotencyStore(Protocol):
    """Armazena key → (hash_payload, resposta_serializada)."""

    def get(self, key: str) -> tuple[str, dict[str, object]] | None: ...

    def put(self, key: str, payload_hash: str, response_json: dict[str, object]) -> None: ...
