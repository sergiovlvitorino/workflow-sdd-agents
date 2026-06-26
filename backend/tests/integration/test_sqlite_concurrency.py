"""Teste de concorrência: lock compartilhado entre SqlitePostRepository e SqliteIdempotencyStore.

Verifica que add() e put() em threads concorrentes não produzem corrupção
quando usam a MESMA conexão + o MESMO lock (ADR-0003 §4.3, P-11).

Com locks separados (bug anterior), as transações implícitas de add() e put()
se intercalam na mesma conexão → ProgrammingError intermitente ou duplicação.
Com lock compartilhado, as escritas são serializadas corretamente.

O teste é determinístico: não usa sleep; assere apenas invariantes de estado
(count e ausência de exceção), não timing.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import pytest

from blog.domain.post import Post, PostStatus
from blog.infrastructure.sqlite_repository import (
    SqliteHandle,
    SqliteIdempotencyStore,
    SqlitePostRepository,
    init_schema,
    make_connection,
)

_UTC = timezone.utc
_N_THREADS = 20
_N_POSTS = 20  # um post único por thread — ids distintos


def _make_post(i: int) -> Post:
    return Post(
        id=f"concurrent-{i:03d}",
        title=f"Post concorrente {i}",
        content="conteúdo",
        status=PostStatus.DRAFT,
        created_at=datetime(2026, 1, 1, tzinfo=_UTC),
        published_at=None,
    )


def _write_pair(
    repo: SqlitePostRepository,
    idem: SqliteIdempotencyStore,
    i: int,
) -> None:
    """Simula o caminho de create_post.py: add → put em sequência."""
    post = _make_post(i)
    repo.add(post)
    idem.put(
        key=f"key-{i:03d}",
        payload_hash=f"hash-{i:03d}",
        response_json={"id": post.id},
    )


@pytest.fixture()
def handle(tmp_path: Path) -> SqliteHandle:  # type: ignore[misc]
    h: SqliteHandle = make_connection(str(tmp_path / "concurrency.db"))
    init_schema(h.conn)
    yield h
    h.conn.close()


def test_concurrent_add_and_put_shared_lock_no_error(handle: SqliteHandle) -> None:
    """_N_THREADS pares (add, put) concorrentes não levantam exceção e produzem N registros."""
    repo = SqlitePostRepository(handle.conn, handle.lock)
    idem = SqliteIdempotencyStore(handle.conn, handle.lock)

    errors: list[BaseException] = []
    with ThreadPoolExecutor(max_workers=_N_THREADS) as pool:
        futures = [pool.submit(_write_pair, repo, idem, i) for i in range(_N_POSTS)]
        for fut in as_completed(futures):
            exc = fut.exception()
            if exc is not None:
                errors.append(exc)

    assert not errors, f"Erros em threads concorrentes: {errors}"
    assert repo.count() == _N_POSTS, f"Esperado {_N_POSTS} posts, encontrado {repo.count()}"

    # Verifica que todas as chaves de idempotência foram gravadas
    for i in range(_N_POSTS):
        result = idem.get(f"key-{i:03d}")
        assert result is not None, f"Chave key-{i:03d} ausente após concorrência"
        assert result[1]["id"] == f"concurrent-{i:03d}"


def test_concurrent_upsert_same_id_no_duplicate(handle: SqliteHandle) -> None:
    """N threads tentando add() com MESMO id não duplicam o registro (UPSERT idempotente)."""
    repo = SqlitePostRepository(handle.conn, handle.lock)
    post = _make_post(0)

    errors: list[BaseException] = []
    with ThreadPoolExecutor(max_workers=_N_THREADS) as pool:
        futures = [pool.submit(repo.add, post) for _ in range(_N_THREADS)]
        for fut in as_completed(futures):
            exc = fut.exception()
            if exc is not None:
                errors.append(exc)

    assert not errors, f"Erros em threads concorrentes: {errors}"
    assert repo.count() == 1, f"UPSERT duplicou: count={repo.count()}"


def test_concurrent_idem_put_write_once(handle: SqliteHandle) -> None:
    """N threads tentando put() com MESMA key preservam o valor do vencedor (write-once)."""
    idem = SqliteIdempotencyStore(handle.conn, handle.lock)
    key = "shared-key"

    errors: list[BaseException] = []
    with ThreadPoolExecutor(max_workers=_N_THREADS) as pool:
        futures = [
            pool.submit(idem.put, key, f"hash-{i}", {"winner": i})
            for i in range(_N_THREADS)
        ]
        for fut in as_completed(futures):
            exc = fut.exception()
            if exc is not None:
                errors.append(exc)

    assert not errors, f"Erros em threads concorrentes: {errors}"

    result = idem.get(key)
    assert result is not None
    # Exatamente um valor persiste (INSERT OR IGNORE garante write-once)
    stored_hash, stored_resp = result
    assert stored_hash.startswith("hash-")
    assert "winner" in stored_resp
