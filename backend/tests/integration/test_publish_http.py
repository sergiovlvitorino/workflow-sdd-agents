"""Testes de integração HTTP real — PUT /v1/posts/{id}/publish (CA-F002-01..03).

Exercitam o wiring completo de DI (middleware, serialização, handlers).
Um teste usa SQLite real (anti-falso-verde de persistência — exigência T-S2-05 revisão).

Adições T-S2-08:
- A1/M2: published_at exato em RFC 3339 (relógio congelado via app.state override).
- A2/M1: reler via GET e comparar published_at exato (estado persistido, não só resposta).
- A3/M3: republicação com relógio avançado para T2 — published_at fica em T1 (red-green M3).
- A4: contagem via list_published (não só count()) estável após republicação.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from blog.application.publish_post import PublishPost
from blog.infrastructure.in_memory import InMemoryIdempotencyStore, InMemoryPostRepository
from blog.infrastructure.sqlite_repository import (
    SqliteHandle,
    SqliteIdempotencyStore,
    SqlitePostRepository,
    init_schema,
    make_connection,
)
from blog.main import create_app

# Timestamps fixos para testes com relógio congelado
T_PUB = datetime(2026, 6, 25, 12, 0, 0, tzinfo=timezone.utc)
T_PUB_RFC3339 = "2026-06-25T12:00:00Z"
T2 = datetime(2026, 6, 25, 13, 0, 0, tzinfo=timezone.utc)  # relógio avançado (diferente de T_PUB)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

DRAFT_BODY = {"title": "Post de teste", "content": "Conteúdo do draft."}


@pytest.fixture()
def client() -> TestClient:
    """App isolada com adapters in-memory para velocidade."""
    app = create_app(repo=InMemoryPostRepository(), idem=InMemoryIdempotencyStore())
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def sqlite_client(tmp_path: Path) -> TestClient:  # type: ignore[misc]
    """App montada sobre SQLite real — valida persistência end-to-end."""
    handle: SqliteHandle = make_connection(str(tmp_path / "publish_test.db"))
    init_schema(handle.conn)
    repo = SqlitePostRepository(handle.conn, handle.lock)
    idem = SqliteIdempotencyStore(handle.conn, handle.lock)
    app = create_app(repo=repo, idem=idem)
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    handle.conn.close()


def _create_draft(client: TestClient, idem_key: str = "create-key") -> str:
    """Cria um draft e retorna o id."""
    resp = client.post(
        "/v1/posts",
        json=DRAFT_BODY,
        headers={"Idempotency-Key": idem_key},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# CA-F002-01: publicar draft → 200, status=published, published_at preenchido
# ---------------------------------------------------------------------------


def test_publish_draft_returns_200_with_published_status(client: TestClient) -> None:
    post_id = _create_draft(client)

    resp = client.put(
        f"/v1/posts/{post_id}/publish",
        headers={"Idempotency-Key": "pub-key-001"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == post_id
    assert data["status"] == "published"
    assert data["published_at"] is not None


# ---------------------------------------------------------------------------
# CA-F002-01 (SQLite real): publicar draft persiste no banco
# ---------------------------------------------------------------------------


def test_publish_draft_sqlite_wiring_persists(sqlite_client: TestClient) -> None:
    """Transição draft→published persiste no SQLite (anti-falso-verde de wiring)."""
    post_id = _create_draft(sqlite_client, idem_key="create-sqlite")

    resp = sqlite_client.put(
        f"/v1/posts/{post_id}/publish",
        headers={"Idempotency-Key": "pub-sqlite-001"},
    )

    assert resp.status_code == 200
    assert resp.json()["status"] == "published"

    # Reler via repo diretamente — estado persistido no SQLite
    repo = sqlite_client.app.state.post_repo  # type: ignore[union-attr]
    saved = repo.get(post_id)
    assert saved is not None
    assert saved.status.value == "published"
    assert saved.published_at is not None


# ---------------------------------------------------------------------------
# Replay (opção B): mesma Idempotency-Key → 200 + Idempotent-Replayed: true + corpo idêntico
# ---------------------------------------------------------------------------


def test_replay_same_key_returns_idempotent_replayed_header(client: TestClient) -> None:
    post_id = _create_draft(client)

    first = client.put(
        f"/v1/posts/{post_id}/publish",
        headers={"Idempotency-Key": "replay-key-001"},
    )
    assert first.status_code == 200
    assert first.headers.get("idempotent-replayed") is None  # 1ª chamada não tem o header

    second = client.put(
        f"/v1/posts/{post_id}/publish",
        headers={"Idempotency-Key": "replay-key-001"},
    )
    assert second.status_code == 200
    assert second.headers.get("idempotent-replayed") == "true"
    # Corpo idêntico ao da 1ª chamada
    assert second.json() == first.json()


# ---------------------------------------------------------------------------
# 409: mesma Idempotency-Key com post_id diferente → idempotency_key_conflict
# ---------------------------------------------------------------------------


def test_same_key_different_post_id_returns_409(client: TestClient) -> None:
    post_id_a = _create_draft(client, idem_key="create-a")
    post_id_b = _create_draft(client, idem_key="create-b")

    # 1ª publicação com a chave
    resp_a = client.put(
        f"/v1/posts/{post_id_a}/publish",
        headers={"Idempotency-Key": "shared-pub-key"},
    )
    assert resp_a.status_code == 200

    # 2ª tentativa: mesma chave, post_id diferente → 409
    resp_b = client.put(
        f"/v1/posts/{post_id_b}/publish",
        headers={"Idempotency-Key": "shared-pub-key"},
    )
    assert resp_b.status_code == 409
    assert resp_b.json()["type"].endswith("idempotency_key_conflict")


# ---------------------------------------------------------------------------
# CA-F002-03: id inexistente → 404 post_not_found, nada publicado
# ---------------------------------------------------------------------------


def test_publish_nonexistent_id_returns_404(client: TestClient) -> None:
    resp = client.put(
        "/v1/posts/ID-INEXISTENTE/publish",
        headers={"Idempotency-Key": "pub-key-404"},
    )

    assert resp.status_code == 404
    data = resp.json()
    assert data["type"].endswith("post_not_found")
    assert resp.headers.get("content-type", "").startswith("application/problem+json")

    # Nenhum post publicado — estado limpo
    count = client.app.state.post_repo.count()  # type: ignore[union-attr]
    assert count == 0


# ---------------------------------------------------------------------------
# CA-F002-03 (sem chave): sem Idempotency-Key → 400, nada publicado
# ---------------------------------------------------------------------------


def test_publish_without_idempotency_key_returns_400(client: TestClient) -> None:
    post_id = _create_draft(client)

    resp = client.put(f"/v1/posts/{post_id}/publish")

    assert resp.status_code == 400
    data = resp.json()
    assert data["type"].endswith("idempotency_key_required")
    assert resp.headers.get("content-type", "").startswith("application/problem+json")

    # Guard disparou antes do caso de uso — post ainda é draft
    repo = client.app.state.post_repo  # type: ignore[union-attr]
    saved = repo.get(post_id)
    assert saved is not None
    assert saved.status.value == "draft"


# ---------------------------------------------------------------------------
# Não-colisão cross-rota: mesma Idempotency-Key em POST e depois PUT → sem 409
# Prova que store_key = f"publish:{idem_key}" não colide com chave crua do create
# ---------------------------------------------------------------------------


def test_same_key_cross_route_no_collision(client: TestClient) -> None:
    shared_key = "cross-route-key"

    # 1. Usar a chave no POST /v1/posts (cria draft)
    create_resp = client.post(
        "/v1/posts",
        json=DRAFT_BODY,
        headers={"Idempotency-Key": shared_key},
    )
    assert create_resp.status_code == 201
    post_id = create_resp.json()["id"]

    # 2. Usar a MESMA chave no PUT .../publish → deve publicar (200), NÃO 409
    pub_resp = client.put(
        f"/v1/posts/{post_id}/publish",
        headers={"Idempotency-Key": shared_key},
    )
    assert pub_resp.status_code == 200, f"Esperado 200, obtido {pub_resp.status_code}: {pub_resp.json()}"
    assert pub_resp.json()["status"] == "published"

    # 3. Inverso: chave usada primeiro no PUT, depois no POST → create não quebra
    # Cria outro draft com chave diferente para ter um id válido
    other_post_id = _create_draft(client, idem_key="other-create-key")
    pub_first_key = "pub-first-key"
    pub_resp2 = client.put(
        f"/v1/posts/{other_post_id}/publish",
        headers={"Idempotency-Key": pub_first_key},
    )
    assert pub_resp2.status_code == 200

    # Reusar a chave do publish num POST (namespace diferente → cria sem 409)
    create_resp2 = client.post(
        "/v1/posts",
        json={"title": "Segundo post", "content": "Conteúdo."},
        headers={"Idempotency-Key": pub_first_key},
    )
    assert create_resp2.status_code == 201, f"Esperado 201, obtido {create_resp2.status_code}: {create_resp2.json()}"


# ---------------------------------------------------------------------------
# Visibilidade pós-publicação: published aparece em GET /v1/posts; draft não aparece
# ---------------------------------------------------------------------------


def test_published_post_appears_in_list_draft_does_not(client: TestClient) -> None:
    # Cria e publica um draft
    post_id = _create_draft(client, idem_key="create-for-list")
    pub_resp = client.put(
        f"/v1/posts/{post_id}/publish",
        headers={"Idempotency-Key": "pub-for-list"},
    )
    assert pub_resp.status_code == 200

    # Cria um segundo draft (sem publicar)
    draft_id = _create_draft(client, idem_key="create-draft-only")

    # GET /v1/posts deve listar apenas o publicado
    list_resp = client.get("/v1/posts")
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    ids_listed = [item["id"] for item in items]

    assert post_id in ids_listed, f"Post publicado {post_id} não aparece em GET /v1/posts"
    assert draft_id not in ids_listed, f"Draft {draft_id} não deveria aparecer em GET /v1/posts"


# ---------------------------------------------------------------------------
# A1 + M2 (T-S2-08): published_at EXATO em RFC 3339 UTC — relógio congelado
#
# Mutation-âncora M2: remover `published_at=now` em Post.publish (setar None)
# → este teste fica VERMELHO (published_at seria None, não T_PUB_RFC3339).
# ---------------------------------------------------------------------------


def test_publish_draft_published_at_exact_value_with_frozen_clock(client: TestClient) -> None:
    """A1: published_at == T_PUB_RFC3339 (valor exato, não só is not None).

    Relógio injetado via substituição de publish_post_use_case após create_app.
    Mutation-âncora M2: remover `published_at=now` em Post.publish → VERMELHO.
    """
    post_repo = client.app.state.post_repo  # type: ignore[union-attr]

    # Substituir o caso de uso com clock congelado em T_PUB
    client.app.state.publish_post_use_case = PublishPost(  # type: ignore[union-attr]
        repo=post_repo, clock=lambda: T_PUB
    )

    post_id = _create_draft(client, idem_key="create-frozen-a1")
    resp = client.put(
        f"/v1/posts/{post_id}/publish",
        headers={"Idempotency-Key": "pub-frozen-a1"},
    )

    assert resp.status_code == 200
    data = resp.json()
    # A1: valor EXATO em RFC 3339, não só is not None
    assert data["published_at"] == T_PUB_RFC3339, (
        f"published_at={data['published_at']!r} != {T_PUB_RFC3339!r} "
        "(M2: remover published_at=now em Post.publish → este assert fica VERMELHO)"
    )
    assert data["status"] == "published"


# ---------------------------------------------------------------------------
# A2 + M1 (T-S2-08): reler via GET e comparar published_at EXATO
#
# Mutation-âncora M1: se PublishPost não persistir (repo.add removido),
# GET /v1/posts/{id} ainda vê draft/404 → este teste fica VERMELHO.
# ---------------------------------------------------------------------------


def test_publish_state_persisted_verified_via_get_exact_published_at(client: TestClient) -> None:
    """A2: publicar → GET /v1/posts/{id} → published_at exato (estado persistido, não só resposta).

    Prova que a transição foi gravada no repo, não só serializada na resposta do PUT.
    Mutation-âncora M1: remover repo.add em PublishPost → GET retorna 404 → VERMELHO.
    """
    post_repo = client.app.state.post_repo  # type: ignore[union-attr]

    # Relógio congelado em T_PUB
    client.app.state.publish_post_use_case = PublishPost(  # type: ignore[union-attr]
        repo=post_repo, clock=lambda: T_PUB
    )

    post_id = _create_draft(client, idem_key="create-a2")
    put_resp = client.put(
        f"/v1/posts/{post_id}/publish",
        headers={"Idempotency-Key": "pub-a2"},
    )
    assert put_resp.status_code == 200
    published_at_put = put_resp.json()["published_at"]

    # A2: reler via GET — estado persistido, não só resposta do PUT
    get_resp = client.get(f"/v1/posts/{post_id}")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["status"] == "published"
    # Mesmo published_at exato (valor, não só is not None)
    assert data["published_at"] == T_PUB_RFC3339
    assert data["published_at"] == published_at_put, (
        "published_at do GET difere do PUT — estado não foi persistido corretamente"
    )


# ---------------------------------------------------------------------------
# A3 + M3 (T-S2-08): republicação com relógio avançado para T2
#
# Setup: publica em T_PUB (clock congelado); avança clock para T2; republica.
# A3: published_at_2 == published_at_1 == T_PUB_RFC3339 (NÃO T2).
# Mutation-âncora M3: remover guarda de no-op (re-setar published_at incondicionalmente)
# → published_at_2 == T2 != T_PUB_RFC3339 → este teste fica VERMELHO.
# ---------------------------------------------------------------------------


def test_republish_with_advanced_clock_published_at_stays_at_t1(client: TestClient) -> None:
    """A3 (relógio avançado): published_at_2 == published_at_1 == T_PUB, NÃO T2.

    Prova que a guarda de no-op ignora o relógio novo T2.
    Mutation-âncora M3: remover guarda → published_at_2 == T2 → VERMELHO.
    """
    post_repo = client.app.state.post_repo  # type: ignore[union-attr]

    # 1ª publicação: clock congelado em T_PUB
    client.app.state.publish_post_use_case = PublishPost(  # type: ignore[union-attr]
        repo=post_repo, clock=lambda: T_PUB
    )
    post_id = _create_draft(client, idem_key="create-a3")
    first = client.put(
        f"/v1/posts/{post_id}/publish",
        headers={"Idempotency-Key": "pub-a3-first"},
    )
    assert first.status_code == 200
    published_at_1 = first.json()["published_at"]
    assert published_at_1 == T_PUB_RFC3339

    # Avança o clock para T2 (T2 != T_PUB — diferença de 1 hora)
    client.app.state.publish_post_use_case = PublishPost(  # type: ignore[union-attr]
        repo=post_repo, clock=lambda: T2
    )
    second = client.put(
        f"/v1/posts/{post_id}/publish",
        headers={"Idempotency-Key": "pub-a3-second"},
    )
    assert second.status_code == 200
    published_at_2 = second.json()["published_at"]

    # A3: valor exato — published_at_2 deve ser T_PUB (1ª publicação), NÃO T2
    assert published_at_2 == published_at_1, (
        f"published_at_2={published_at_2!r} != published_at_1={published_at_1!r} "
        "(M3: remover guarda no-op → re-seta para T2 → VERMELHO)"
    )
    assert published_at_2 == T_PUB_RFC3339, (
        f"published_at mudou para T2 ({T2.isoformat()}) — guarda de no-op ausente (M3)"
    )


# ---------------------------------------------------------------------------
# A4 (T-S2-08): contagem via list_published estável após republicação
#
# DETAIL-08 exige assertar efeito via list_published (publicados), não só count() total.
# ---------------------------------------------------------------------------


def test_republish_list_published_count_stable(client: TestClient) -> None:
    """A4: contagem de list_published não muda ao republicar (CA-F002-02).

    Diferente de count() (total): list_published conta só publicados.
    Garante que republica não duplica registro na lista.
    """
    post_id = _create_draft(client, idem_key="create-a4")

    # 1ª publicação
    client.put(
        f"/v1/posts/{post_id}/publish",
        headers={"Idempotency-Key": "pub-a4-first"},
    )

    count_after_first = len(
        client.app.state.post_repo.list_published(after=None, limit=100)  # type: ignore[union-attr]
    )
    assert count_after_first == 1, f"Esperado 1 publicado após 1ª publicação, obtido {count_after_first}"

    # 2ª publicação (republicação)
    client.put(
        f"/v1/posts/{post_id}/publish",
        headers={"Idempotency-Key": "pub-a4-second"},
    )

    count_after_second = len(
        client.app.state.post_repo.list_published(after=None, limit=100)  # type: ignore[union-attr]
    )
    assert count_after_second == count_after_first == 1, (
        f"count_after_second={count_after_second} — republicação duplicou entrada em list_published"
    )
