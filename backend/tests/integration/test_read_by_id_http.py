"""Testes de integração HTTP real — GET /v1/posts/{id} (CA-F004-01/02, ADR-0004 §8).

Exercitam o wiring completo de DI (middleware, serialização, handlers).
Inclui teste de indistinguibilidade byte-a-byte entre 404 de rascunho, 404 de inexistente
e 404 de publicação de id inexistente — fecha o anti-vazamento do ADR-0004 §8 por teste.
Um teste usa SQLite real (anti-falso-verde de persistência).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from blog.infrastructure.in_memory import InMemoryIdempotencyStore, InMemoryPostRepository
from blog.infrastructure.sqlite_repository import (
    SqliteHandle,
    SqliteIdempotencyStore,
    SqlitePostRepository,
    init_schema,
    make_connection,
)
from blog.main import create_app

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

DRAFT_BODY = {"title": "Post de Leitura", "content": "Conteúdo para leitura por id."}


@pytest.fixture()
def client() -> TestClient:
    """App isolada com adapters in-memory para velocidade."""
    app = create_app(repo=InMemoryPostRepository(), idem=InMemoryIdempotencyStore())
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def sqlite_client(tmp_path: Path) -> TestClient:  # type: ignore[misc]
    """App montada sobre SQLite real — valida persistência end-to-end."""
    handle: SqliteHandle = make_connection(str(tmp_path / "read_by_id_test.db"))
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


def _publish(client: TestClient, post_id: str, idem_key: str = "pub-key") -> None:
    resp = client.put(
        f"/v1/posts/{post_id}/publish",
        headers={"Idempotency-Key": idem_key},
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# CA-F004-01: post publicado → 200 com schema Post completo
# ---------------------------------------------------------------------------


def test_get_published_post_returns_200_with_full_schema(client: TestClient) -> None:
    post_id = _create_draft(client, idem_key="create-f004-01")
    _publish(client, post_id, idem_key="pub-f004-01")

    resp = client.get(f"/v1/posts/{post_id}")

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == post_id
    assert data["title"] == DRAFT_BODY["title"]
    assert data["content"] == DRAFT_BODY["content"]
    assert data["status"] == "published"
    assert data["created_at"] is not None
    assert data["published_at"] is not None


# ---------------------------------------------------------------------------
# CA-F004-01 (SQLite real): wiring completo de persistência
# ---------------------------------------------------------------------------


def test_get_published_post_sqlite_wiring(sqlite_client: TestClient) -> None:
    """Leitura por id funciona sobre SQLite real (anti-falso-verde de wiring)."""
    post_id = _create_draft(sqlite_client, idem_key="create-sqlite-f004")
    _publish(sqlite_client, post_id, idem_key="pub-sqlite-f004")

    resp = sqlite_client.get(f"/v1/posts/{post_id}")

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == post_id
    assert data["status"] == "published"
    assert data["published_at"] is not None


# ---------------------------------------------------------------------------
# CA-F004-02 (draft): rascunho → 404 post_not_found (não revela existência)
# ---------------------------------------------------------------------------


def test_get_draft_post_returns_404(client: TestClient) -> None:
    post_id = _create_draft(client, idem_key="create-draft-f004")

    resp = client.get(f"/v1/posts/{post_id}")

    assert resp.status_code == 404
    data = resp.json()
    assert data["type"].endswith("post_not_found")
    assert data["status"] == 404
    assert resp.headers.get("content-type", "").startswith("application/problem+json")


# ---------------------------------------------------------------------------
# CA-F004-02 (inexistente): id que não existe → 404 post_not_found
# ---------------------------------------------------------------------------


def test_get_nonexistent_post_returns_404(client: TestClient) -> None:
    resp = client.get("/v1/posts/ID-QUE-NAO-EXISTE")

    assert resp.status_code == 404
    data = resp.json()
    assert data["type"].endswith("post_not_found")
    assert data["status"] == 404
    assert resp.headers.get("content-type", "").startswith("application/problem+json")


# ---------------------------------------------------------------------------
# INDISTINGUIBILIDADE byte-a-byte (pendência ADR-0004 §8):
#   GET rascunho, GET inexistente e PUT .../publish de id inexistente
#   devem ter type/title/status/detail IDÊNTICOS — mesmo handler.
#   Qualquer diferença reintroduziria vazamento de existência.
# ---------------------------------------------------------------------------


def test_404_bodies_are_indistinguishable_across_all_three_cases(client: TestClient) -> None:
    """Fecha anti-vazamento de existência (ADR-0004 §8) por comparação byte-a-byte.

    Os três casos devem produzir exatamente os mesmos campos de erro:
    - type, title, status, detail devem ser idênticos.
    Mutation-âncora: diferenciar 404-draft de 404-inexistente faz este teste vermelho.
    """
    # Caso 1: GET de rascunho existente
    draft_id = _create_draft(client, idem_key="create-indist")
    resp_draft = client.get(f"/v1/posts/{draft_id}")
    assert resp_draft.status_code == 404

    # Caso 2: GET de id inexistente
    resp_nonexistent = client.get("/v1/posts/ID-INEXISTENTE-INDIST")
    assert resp_nonexistent.status_code == 404

    # Caso 3: PUT .../publish de id inexistente (F002 — mesma exceção PostNotFound)
    resp_publish_404 = client.put(
        "/v1/posts/ID-INEXISTENTE-PUBLISH/publish",
        headers={"Idempotency-Key": "pub-indist-key"},
    )
    assert resp_publish_404.status_code == 404

    # Extrair apenas campos de identidade do erro (RFC 9457)
    _FIELDS = ("type", "title", "status", "detail")

    def _extract(body: dict) -> dict:  # type: ignore[type-arg]
        return {k: body[k] for k in _FIELDS}

    draft_error = _extract(resp_draft.json())
    nonexistent_error = _extract(resp_nonexistent.json())
    publish_error = _extract(resp_publish_404.json())

    assert draft_error == nonexistent_error, f"404-draft != 404-inexistente: {draft_error!r} vs {nonexistent_error!r}"
    assert draft_error == publish_error, f"404-draft != 404-publish-inexistente: {draft_error!r} vs {publish_error!r}"

    # Content-Type idêntico nos três casos
    ct_draft = resp_draft.headers.get("content-type", "")
    ct_nonexistent = resp_nonexistent.headers.get("content-type", "")
    ct_publish = resp_publish_404.headers.get("content-type", "")
    assert ct_draft == ct_nonexistent == ct_publish
    assert ct_draft.startswith("application/problem+json")


# ---------------------------------------------------------------------------
# Não-colisão de rota: GET /v1/posts (listagem) não é capturado por /{post_id}
# ---------------------------------------------------------------------------


def test_list_posts_route_not_captured_by_get_by_id(client: TestClient) -> None:
    """GET /v1/posts (sem id) continua resolvendo para a listagem, sem colisão."""
    post_id = _create_draft(client, idem_key="create-list-check")
    _publish(client, post_id, idem_key="pub-list-check")

    resp = client.get("/v1/posts")

    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data, "GET /v1/posts deve retornar Page<Post> com 'items'"


# ---------------------------------------------------------------------------
# Cruzamento com F003 (P-04): rascunho não aparece em listagem nem em read-by-id
# ---------------------------------------------------------------------------


def test_draft_invisible_in_both_list_and_read_by_id(client: TestClient) -> None:
    """Rascunho não vaza nem via lista nem via leitura direta (allowlist P-04 coerente)."""
    draft_id = _create_draft(client, idem_key="create-cross-f003")

    # Listagem: draft não aparece
    list_resp = client.get("/v1/posts")
    assert list_resp.status_code == 200
    ids_listed = [item["id"] for item in list_resp.json()["items"]]
    assert draft_id not in ids_listed

    # Read-by-id: draft retorna 404
    read_resp = client.get(f"/v1/posts/{draft_id}")
    assert read_resp.status_code == 404
