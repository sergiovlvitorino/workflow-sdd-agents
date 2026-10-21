"""Teste de prova (red-green): fecha o TOCTOU de idempotência no CREATE (ADR-0007, SEC-03).

Exercita o USE-CASE REAL (`CreatePost.execute`), parametrizado nos 2 adapters
(in-memory e SQLite). Prova as invariantes:

- INV-P03-CREATE-1: mesma key + mesmo payload → exatamente 1 post, mesmo id
  em todas as respostas.
- INV-P03-CREATE-2: mesma key + payload divergente sob concorrência →
  exatamente 1 IdempotencyConflict, exatamente 1 post.

Antes do fix (ADR-0007), o `id_gen` real (ULID distinto por chamada) faz o
TOCTOU se manifestar: `count()==N`, `len(set(ids))==N`. Depois do fix,
`count()==1`, `len(set(ids))==1`. NÃO injetar id_gen constante aqui — mascara
o bug (ADR-0007 §8.3/§8.4).

**Barreira no ponto TOCTOU, não no início do worker (revisão tl-qa, ciclo 2):**
colocar a `Barrier` antes de `execute()` NÃO força a corrida — sob GIL, a
1ª thread completa `get→put→add` inteiro antes da 2ª sequer chamar `get()`;
as demais caem no fast-path replay (que nunca passa por `existing is None`)
e o ramo mutado nunca é exercitado (falso-verde: mutação `add` incondicional
ficava VERDE). O `_BarrierSyncedIdem` abaixo embrulha o store real e dispara
a barreira DENTRO de `get()` quando retorna `None` — o ponto exato em que o
use-case decide "ainda não vista" — forçando as N threads a atravessarem
`existing is None` juntas, ANTES de qualquer `put`, replicando o TOCTOU real.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import pytest
from ulid import ULID

from blog.application.create_post import CreatePost, IdempotencyConflict
from blog.application.ports import IdempotencyStore, PostRepository
from blog.infrastructure.in_memory import InMemoryIdempotencyStore, InMemoryPostRepository
from blog.infrastructure.sqlite_repository import (
    SqliteHandle,
    SqliteIdempotencyStore,
    SqlitePostRepository,
    init_schema,
    make_connection,
)

_UTC = timezone.utc
_FIXED_NOW = datetime(2026, 7, 15, 12, 0, 0, tzinfo=_UTC)
_N = 12  # >= 8 p/ tornar o vermelho confiável (ADR-0007 §8.3)


def _real_id_gen() -> str:
    """ULID real e distinto por chamada — NÃO trocar por constante (mascara o TOCTOU)."""
    return str(ULID())


class _BarrierSyncedIdem:
    """Embrulha o IdempotencyStore real; dispara a barreira DENTRO de get() quando
    retorna None — o ponto TOCTOU exato (ADR-0007 §4.1: `existing is None`).

    Sem isso, colocar a Barrier no início do worker não força a corrida: sob
    GIL, uma thread pode completar get→put→add inteiro antes da próxima
    sequer chamar get(), fazendo as demais caírem no fast-path replay (que
    não passa pelo ramo `won`/perdedor) — falso-verde (tl-qa, ciclo 2).
    """

    def __init__(self, inner: IdempotencyStore, barrier: threading.Barrier) -> None:
        self._inner = inner
        self._barrier = barrier

    def get(self, key: str) -> tuple[str, dict[str, object]] | None:
        result = self._inner.get(key)
        if result is None:
            self._barrier.wait()  # todas as N threads atravessam o None juntas
        return result

    def put(self, key: str, payload_hash: str, response_json: dict[str, object]) -> bool:
        return self._inner.put(key, payload_hash, response_json)


@pytest.fixture(params=["in_memory", "sqlite"], ids=["in_memory", "sqlite"])
def adapters(request: pytest.FixtureRequest, tmp_path: Path) -> tuple[PostRepository, IdempotencyStore]:  # type: ignore[misc]
    if request.param == "in_memory":
        yield InMemoryPostRepository(), InMemoryIdempotencyStore()
        return
    handle: SqliteHandle = make_connection(str(tmp_path / "concurrency_uc.db"))
    init_schema(handle.conn)
    yield (
        SqlitePostRepository(handle.conn, handle.lock),
        SqliteIdempotencyStore(handle.conn, handle.lock),
    )
    handle.conn.close()


def _make_use_case(repo: PostRepository, idem: IdempotencyStore, barrier: threading.Barrier) -> CreatePost:
    return CreatePost(
        repo=repo,
        idem=_BarrierSyncedIdem(idem, barrier),  # type: ignore[arg-type]
        clock=lambda: _FIXED_NOW,
        id_gen=_real_id_gen,
    )


def test_concurrent_same_key_same_payload_creates_single_post(
    adapters: tuple[PostRepository, IdempotencyStore],
) -> None:
    post_repo, idem_store = adapters
    barrier = threading.Barrier(_N)
    use_case = _make_use_case(post_repo, idem_store, barrier)

    def worker() -> str:
        resp, _replayed = use_case.execute("SAME-KEY", "Título", "Conteúdo")
        return str(resp["id"])

    with ThreadPoolExecutor(max_workers=_N) as pool:
        futures = [pool.submit(worker) for _ in range(_N)]
        ids = [f.result() for f in as_completed(futures)]

    assert post_repo.count() == 1, f"P-03 violado: {post_repo.count()} posts para 1 key"
    assert len(set(ids)) == 1, f"ids divergentes sob concorrência: {set(ids)}"


def test_concurrent_same_key_divergent_payload_one_conflict(
    adapters: tuple[PostRepository, IdempotencyStore],
) -> None:
    post_repo, idem_store = adapters
    barrier = threading.Barrier(2)
    use_case = _make_use_case(post_repo, idem_store, barrier)

    def worker(content: str) -> str | None:
        try:
            resp, _replayed = use_case.execute("SAME-KEY-CONFLICT", "Título", content)
            return str(resp["id"])
        except IdempotencyConflict:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(worker, "Conteúdo A")
        f2 = pool.submit(worker, "Conteúdo B")
        results = [f1.result(), f2.result()]

    conflicts = sum(1 for r in results if r is None)
    assert conflicts == 1, f"Esperado exatamente 1 IdempotencyConflict, obtido {conflicts}"
    assert post_repo.count() == 1, f"P-03 violado sob conflito concorrente: count={post_repo.count()}"
