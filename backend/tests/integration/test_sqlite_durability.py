"""Teste de durabilidade entre conexões SQLite — feature-âncora do ADR-0003.

Verifica que dados escritos numa instância de SqlitePostRepository persistem
e são legíveis por uma NOVA instância abrindo o MESMO arquivo.
NUNCA usa :memory: (cada conexão :memory: é um banco distinto — falso-verde).
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import pytest

from blog.domain.post import Post, PostStatus
from blog.infrastructure.sqlite_repository import (
    SqliteIdempotencyStore,
    SqlitePostRepository,
    init_schema,
    make_connection,
)

_UTC = timezone.utc


@contextmanager
def _repo(db_path: Path) -> Generator[SqlitePostRepository, None, None]:
    """Abre repositório em arquivo e fecha a conexão ao sair."""
    handle = make_connection(str(db_path))
    init_schema(handle.conn)
    try:
        yield SqlitePostRepository(handle.conn, handle.lock)
    finally:
        handle.conn.close()


@contextmanager
def _idem(db_path: Path) -> Generator[SqliteIdempotencyStore, None, None]:
    """Abre idempotency store em arquivo e fecha a conexão ao sair."""
    handle = make_connection(str(db_path))
    init_schema(handle.conn)
    try:
        yield SqliteIdempotencyStore(handle.conn, handle.lock)
    finally:
        handle.conn.close()


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "durability.db"


class TestSqliteDurabilityBetweenConnections:
    def test_post_persists_across_connections(self, db_path: Path) -> None:
        """Escreve com conn_a, lê com conn_b no mesmo arquivo."""
        post = Post(
            id="duravel-01",
            title="Post durável",
            content="Sobrevive ao restart.",
            status=PostStatus.DRAFT,
            created_at=datetime(2026, 6, 25, 10, 0, tzinfo=_UTC),
            published_at=None,
        )

        with _repo(db_path) as repo_a:
            repo_a.add(post)

        # Lê com nova instância no mesmo arquivo (simula restart do processo)
        with _repo(db_path) as repo_b:
            result = repo_b.get("duravel-01")

        assert result is not None
        assert result.id == "duravel-01"
        assert result.title == "Post durável"
        assert result.status == PostStatus.DRAFT

    def test_count_persists_across_connections(self, db_path: Path) -> None:
        with _repo(db_path) as repo_a:
            for i in range(3):
                repo_a.add(
                    Post(
                        id=f"p{i}",
                        title=f"Post {i}",
                        content="conteúdo",
                        status=PostStatus.DRAFT,
                        created_at=datetime(2026, 1, 1, tzinfo=_UTC),
                        published_at=None,
                    )
                )

        with _repo(db_path) as repo_b:
            count = repo_b.count()

        assert count == 3

    def test_published_post_keyset_persists(self, db_path: Path) -> None:
        """Posts publicados listados por keyset sobrevivem ao restart."""
        t = datetime(2026, 6, 25, 12, 0, tzinfo=_UTC)
        with _repo(db_path) as repo_a:
            repo_a.add(
                Post(
                    id="pub-duravel",
                    title="Publicado",
                    content="conteúdo",
                    status=PostStatus.PUBLISHED,
                    created_at=datetime(2026, 1, 1, tzinfo=_UTC),
                    published_at=t,
                )
            )

        with _repo(db_path) as repo_b:
            results = repo_b.list_published(after=None, limit=10)

        assert len(results) == 1
        assert results[0].id == "pub-duravel"
        assert results[0].published_at is not None
        assert results[0].published_at.tzinfo is not None  # tz-aware preservado

    def test_idempotency_persists_across_connections(self, db_path: Path) -> None:
        """Chave de idempotência persiste entre conexões (P-03 durável)."""
        with _idem(db_path) as idem_a:
            idem_a.put("chave-dur", "hash-dur", {"id": "post-dur", "status": "draft"})

        with _idem(db_path) as idem_b:
            result = idem_b.get("chave-dur")

        assert result is not None
        h, resp = result
        assert h == "hash-dur"
        assert resp["id"] == "post-dur"

    def test_idempotency_replay_preserves_original_across_connections(self, db_path: Path) -> None:
        """Replay do SqliteIdempotencyStore real: valor original preservado após dois puts."""
        with _idem(db_path) as idem_a:
            idem_a.put("replay-key", "hash-1", {"id": "p1"})

        # Nova instância tenta put com mesma key (simulando retry)
        with _idem(db_path) as idem_b:
            idem_b.put("replay-key", "hash-1", {"id": "p1"})

        # Lê com terceira instância: valor original preservado
        with _idem(db_path) as idem_c:
            result = idem_c.get("replay-key")

        assert result is not None
        assert result[0] == "hash-1"
        assert result[1]["id"] == "p1"
