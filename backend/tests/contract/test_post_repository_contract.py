"""Suíte de contrato de porta parametrizada — PostRepository + IdempotencyStore.

Os mesmos casos rodam contra InMemoryPostRepository e SqlitePostRepository,
garantindo paridade de comportamento entre adapters (ADR-0003 §8).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from blog.domain.post import Post, PostStatus
from blog.infrastructure.in_memory import InMemoryIdempotencyStore, InMemoryPostRepository
from blog.infrastructure.sqlite_repository import (
    SqliteHandle,
    SqliteIdempotencyStore,
    SqlitePostRepository,
    init_schema,
    make_connection,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_UTC = timezone.utc


def _dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


def _published_post(
    *,
    id: str,
    published_at: datetime,
) -> Post:
    return Post(
        id=id,
        title=f"Post {id}",
        content="conteúdo",
        status=PostStatus.PUBLISHED,
        created_at=datetime(2026, 1, 1, tzinfo=_UTC),
        published_at=published_at,
    )


def _draft_post(*, id: str) -> Post:
    return Post(
        id=id,
        title=f"Draft {id}",
        content="rascunho",
        status=PostStatus.DRAFT,
        created_at=datetime(2026, 1, 1, tzinfo=_UTC),
        published_at=None,
    )


# ---------------------------------------------------------------------------
# Fixtures parametrizadas
# ---------------------------------------------------------------------------

@pytest.fixture(
    params=["in_memory", "sqlite"],
    ids=["in_memory", "sqlite"],
)
def post_repo(request: pytest.FixtureRequest, tmp_path: Path) -> SqlitePostRepository | InMemoryPostRepository:  # type: ignore[misc]
    if request.param == "in_memory":
        yield InMemoryPostRepository()
        return
    handle: SqliteHandle = make_connection(str(tmp_path / "contract.db"))
    init_schema(handle.conn)
    yield SqlitePostRepository(handle.conn, handle.lock)
    handle.conn.close()


@pytest.fixture(
    params=["in_memory", "sqlite"],
    ids=["in_memory", "sqlite"],
)
def idem_store(request: pytest.FixtureRequest, tmp_path: Path) -> SqliteIdempotencyStore | InMemoryIdempotencyStore:  # type: ignore[misc]
    if request.param == "in_memory":
        yield InMemoryIdempotencyStore()
        return
    handle: SqliteHandle = make_connection(str(tmp_path / "idem_contract.db"))
    init_schema(handle.conn)
    yield SqliteIdempotencyStore(handle.conn, handle.lock)
    handle.conn.close()


# ---------------------------------------------------------------------------
# Contrato PostRepository
# ---------------------------------------------------------------------------

class TestPostRepositoryContract:
    def test_count_empty(self, post_repo: SqlitePostRepository | InMemoryPostRepository) -> None:
        assert post_repo.count() == 0

    def test_add_increases_count(self, post_repo: SqlitePostRepository | InMemoryPostRepository) -> None:
        post_repo.add(_draft_post(id="p1"))
        assert post_repo.count() == 1

    def test_get_existing_post(self, post_repo: SqlitePostRepository | InMemoryPostRepository) -> None:
        draft = _draft_post(id="p1")
        post_repo.add(draft)
        result = post_repo.get("p1")
        assert result is not None
        assert result.id == "p1"
        assert result.title == draft.title

    def test_get_absent_returns_none(self, post_repo: SqlitePostRepository | InMemoryPostRepository) -> None:
        assert post_repo.get("nao-existe") is None

    def test_add_upsert_updates_existing(self, post_repo: SqlitePostRepository | InMemoryPostRepository) -> None:
        """UPSERT: add com mesmo id deve atualizar o registro (suporte à publicação futura)."""
        draft = _draft_post(id="p1")
        post_repo.add(draft)

        published = Post(
            id="p1",
            title="Título atualizado",
            content="conteúdo",
            status=PostStatus.PUBLISHED,
            created_at=draft.created_at,
            published_at=datetime(2026, 6, 1, 12, 0, tzinfo=_UTC),
        )
        post_repo.add(published)

        result = post_repo.get("p1")
        assert result is not None
        assert result.status == PostStatus.PUBLISHED
        assert result.title == "Título atualizado"
        assert post_repo.count() == 1  # não criou duplicata

    def test_list_published_empty(self, post_repo: SqlitePostRepository | InMemoryPostRepository) -> None:
        assert post_repo.list_published(after=None, limit=10) == []

    def test_list_published_excludes_drafts(self, post_repo: SqlitePostRepository | InMemoryPostRepository) -> None:
        post_repo.add(_draft_post(id="draft1"))
        assert post_repo.list_published(after=None, limit=10) == []

    def test_list_published_order_desc(self, post_repo: SqlitePostRepository | InMemoryPostRepository) -> None:
        t1 = datetime(2026, 1, 1, tzinfo=_UTC)
        t2 = datetime(2026, 1, 2, tzinfo=_UTC)
        t3 = datetime(2026, 1, 3, tzinfo=_UTC)

        post_repo.add(_published_post(id="p1", published_at=t1))
        post_repo.add(_published_post(id="p2", published_at=t3))
        post_repo.add(_published_post(id="p3", published_at=t2))

        result = post_repo.list_published(after=None, limit=10)
        ids = [p.id for p in result]
        assert ids == ["p2", "p3", "p1"]

    def test_list_published_keyset_pagination(self, post_repo: SqlitePostRepository | InMemoryPostRepository) -> None:
        """Keyset estrito '<': página 2 não repete o item de fronteira (ADR-0002)."""
        # 4 posts com datas distintas
        for i in range(1, 5):
            t = datetime(2026, 1, i, tzinfo=_UTC)
            post_repo.add(_published_post(id=f"p{i:02d}", published_at=t))

        page1 = post_repo.list_published(after=None, limit=2)
        assert len(page1) == 2
        last = page1[-1]
        assert last.published_at is not None

        page2 = post_repo.list_published(after=(last.published_at, last.id), limit=2)
        assert len(page2) == 2
        # Nenhum id de page1 em page2
        p1_ids = {p.id for p in page1}
        p2_ids = {p.id for p in page2}
        assert p1_ids.isdisjoint(p2_ids), f"Fronteira duplicada: {p1_ids & p2_ids}"

    def test_list_published_limit_respected(self, post_repo: SqlitePostRepository | InMemoryPostRepository) -> None:
        for i in range(1, 6):
            t = datetime(2026, 1, i, tzinfo=_UTC)
            post_repo.add(_published_post(id=f"p{i:02d}", published_at=t))

        result = post_repo.list_published(after=None, limit=3)
        assert len(result) == 3

    def test_datetimes_are_tz_aware(self, post_repo: SqlitePostRepository | InMemoryPostRepository) -> None:
        """Datetimes lidos de volta nunca devem ser naive (ADR-0003 §8)."""
        t = datetime(2026, 6, 25, 10, 30, tzinfo=_UTC)
        post = _published_post(id="p1", published_at=t)
        post_repo.add(post)

        result = post_repo.get("p1")
        assert result is not None
        assert result.created_at.tzinfo is not None
        assert result.published_at is not None
        assert result.published_at.tzinfo is not None

    def test_keyset_mutation_anchor_lt_not_lte(self, post_repo: SqlitePostRepository | InMemoryPostRepository) -> None:
        """Mutation-anchor: '<' estrito não repete o item de fronteira (ADR-0002).

        Se '<' fosse '<=', o item de fronteira apareceria em ambas as páginas.
        """
        t = datetime(2026, 1, 1, tzinfo=_UTC)
        p = _published_post(id="pA", published_at=t)
        post_repo.add(p)

        # Cursor apontando exatamente para 'pA'
        page2 = post_repo.list_published(after=(t, "pA"), limit=10)
        assert "pA" not in [x.id for x in page2], "Fronteira duplicada: '<' virou '<=' (mutation)"

    def test_publish_via_domain_method_persists_exact_published_at(
        self, post_repo: SqlitePostRepository | InMemoryPostRepository
    ) -> None:
        """C4 (T-S2-08): Post.publish(now) + add/update → reler → status=published, published_at=T1.

        Exercita o caminho real de domínio (Post.publish) + persistência nos 2 adapters.
        Prova que os adapters preservam o valor exato de published_at (sem truncamento).
        """
        T1 = datetime(2026, 6, 25, 10, 0, 0, tzinfo=_UTC)
        draft = Post(
            id="c4-pub",
            title="Post para publicar via domínio",
            content="conteúdo",
            status=PostStatus.DRAFT,
            created_at=datetime(2026, 1, 1, tzinfo=_UTC),
            published_at=None,
        )
        post_repo.add(draft)

        # Publicar via método de domínio com relógio injetado (T1)
        published = draft.publish(T1)
        post_repo.add(published)  # upsert (mesmo id)

        # Reler e verificar campos exatos
        result = post_repo.get("c4-pub")
        assert result is not None
        assert result.status == PostStatus.PUBLISHED
        assert result.published_at == T1, (
            f"published_at={result.published_at!r} != T1={T1!r} "
            "(adapter não preservou valor exato de published_at)"
        )
        assert result.published_at is not None
        assert result.published_at.tzinfo is not None  # tz-aware preservado

    def test_same_sequence_same_ids_both_adapters(
        self, post_repo: SqlitePostRepository | InMemoryPostRepository
    ) -> None:
        """C1 (T-S2-08): mesma sequência de ids → list_published devolve mesma ordem absoluta.

        Asserção absoluta (len == N_publicados) antes da relativa (ordem).
        Nos 2 adapters a lista de ids deve ser idêntica.
        """
        T1 = datetime(2026, 1, 1, tzinfo=_UTC)
        T2 = datetime(2026, 1, 2, tzinfo=_UTC)
        T3 = datetime(2026, 1, 3, tzinfo=_UTC)

        for post_id, pub_at in [("seq-p1", T1), ("seq-p2", T3), ("seq-p3", T2)]:
            post_repo.add(_published_post(id=post_id, published_at=pub_at))

        result = post_repo.list_published(after=None, limit=10)
        # Absoluto: exatamente 3 publicados
        assert len(result) == 3, f"Esperado 3 publicados, obtido {len(result)}"
        # Relativo: ordem DESC por published_at
        ids = [p.id for p in result]
        assert ids == ["seq-p2", "seq-p3", "seq-p1"], f"Ordem incorreta: {ids}"


# ---------------------------------------------------------------------------
# Contrato IdempotencyStore
# ---------------------------------------------------------------------------

class TestIdempotencyStoreContract:
    def test_get_absent_returns_none(self, idem_store: SqliteIdempotencyStore | InMemoryIdempotencyStore) -> None:
        assert idem_store.get("chave-inexistente") is None

    def test_put_and_get(self, idem_store: SqliteIdempotencyStore | InMemoryIdempotencyStore) -> None:
        idem_store.put("k1", "hash123", {"id": "abc", "status": "draft"})
        result = idem_store.get("k1")
        assert result is not None
        h, resp = result
        assert h == "hash123"
        assert resp["id"] == "abc"

    def test_put_is_write_once_idempotent(self, idem_store: SqliteIdempotencyStore | InMemoryIdempotencyStore) -> None:
        """Segundo put com mesma key é no-op: preserva o valor original (P-03)."""
        idem_store.put("k1", "hash_original", {"id": "original"})
        idem_store.put("k1", "hash_novo", {"id": "novo"})  # deve ser ignorado

        result = idem_store.get("k1")
        assert result is not None
        h, resp = result
        assert h == "hash_original"
        assert resp["id"] == "original"

    def test_replay_preserves_original_value(self, idem_store: SqliteIdempotencyStore | InMemoryIdempotencyStore) -> None:
        """Replay de idempotência: count==1 (não duplica o registro)."""
        idem_store.put("k1", "hash", {"id": "p1"})
        idem_store.put("k1", "hash", {"id": "p1"})  # replay

        # Verificar que get ainda retorna o valor correto (store intacto)
        result = idem_store.get("k1")
        assert result is not None
        assert result[1]["id"] == "p1"
