"""
Adapters in-memory — DIDÁTICO (ADR-0001).

Propósito exclusivamente pedagógico: mostra a separação de portas e adapters
sem exigir infraestrutura externa. Substituível por SQLite/Postgres sem alterar
o domínio ou os casos de uso (P-06/P-12).

NAO use em produção.
"""

from __future__ import annotations

from datetime import datetime

from blog.domain.post import Post, PostStatus


class InMemoryPostRepository:
    """Repositório de posts em memória — DIDÁTICO."""

    def __init__(self) -> None:
        self._store: dict[str, Post] = {}

    def add(self, post: Post) -> None:
        self._store[post.id] = post

    def get(self, id: str) -> Post | None:
        return self._store.get(id)

    def count(self) -> int:
        return len(self._store)

    def list_published(
        self,
        *,
        after: tuple[datetime, str] | None,
        limit: int,
    ) -> list[Post]:
        """Keyset in-memory equivalente a WHERE (published_at, id) < (:p, :id).

        Ordenação total: (published_at DESC, id DESC).
        Filtro allowlist: só PostStatus.PUBLISHED (RF-006, P-04).
        Keyset estrito '<' (ADR-0002): nunca repete a fronteira.
        """
        # Allowlist: só publicados (nunca rascunhos — RF-006)
        items: list[Post] = [p for p in self._store.values() if p.status is PostStatus.PUBLISHED]
        # Ordenação total determinística (published_at DESC, id DESC)
        items.sort(key=lambda p: (p.published_at, p.id), reverse=True)

        if after is not None:
            after_ts, after_id = after
            # Keyset estrito '<': exclui o item de fronteira e tudo antes (ADR-0002)
            items = [p for p in items if (p.published_at, p.id) < (after_ts, after_id)]

        return items[:limit]


class InMemoryIdempotencyStore:
    """Idempotency store em memória — DIDÁTICO."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[str, dict[str, object]]] = {}

    def get(self, key: str) -> tuple[str, dict[str, object]] | None:
        return self._store.get(key)

    def put(self, key: str, payload_hash: str, response_json: dict[str, object]) -> None:
        """Write-once: preserva o primeiro valor (P-03); replay é no-op."""
        if key not in self._store:
            self._store[key] = (payload_hash, response_json)
