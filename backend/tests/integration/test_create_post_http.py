"""Testes de integração HTTP real via TestClient — CA-F001-01..04 + conflito.

Exercitam o wiring completo de DI (middleware, serialização, handlers).
Os adapters in-memory de produção são usados — não dublês ad-hoc — para
que o caminho de replay seja exercitado com o store real (docs/lessons/qa.md).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from blog.infrastructure.in_memory import InMemoryIdempotencyStore, InMemoryPostRepository
from blog.main import create_app


@pytest.fixture()
def client() -> TestClient:
    """Client com app isolada por teste (estado limpo — adapters in-memory injetados)."""
    app = create_app(repo=InMemoryPostRepository(), idem=InMemoryIdempotencyStore())
    return TestClient(app, raise_server_exceptions=False)


VALID_BODY = {"title": "Meu primeiro post", "content": "Conteúdo do post."}
IDEM_KEY = "test-key-001"


# ---------------------------------------------------------------------------
# CA-F001-01: criação bem-sucedida → 201, id e status draft
# ---------------------------------------------------------------------------
def test_create_post_returns_201_with_id_and_draft_status(client: TestClient) -> None:
    resp = client.post(
        "/v1/posts",
        json=VALID_BODY,
        headers={"Idempotency-Key": IDEM_KEY},
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["id"]
    assert data["status"] == "draft"
    assert data["title"] == VALID_BODY["title"]
    assert data["content"] == VALID_BODY["content"]
    assert data["published_at"] is None


# ---------------------------------------------------------------------------
# CA-F001-02: replay com mesma chave+payload → 200 + Idempotent-Replayed: true
#             asserção de ESTADO: repositório tem 1 post (não 2)
# ---------------------------------------------------------------------------
def test_replay_returns_200_with_replayed_header_and_same_id(client: TestClient) -> None:
    first = client.post(
        "/v1/posts",
        json=VALID_BODY,
        headers={"Idempotency-Key": IDEM_KEY},
    )
    assert first.status_code == 201
    original_id = first.json()["id"]

    second = client.post(
        "/v1/posts",
        json=VALID_BODY,
        headers={"Idempotency-Key": IDEM_KEY},
    )

    assert second.status_code == 200
    assert second.headers.get("idempotent-replayed") == "true"
    assert second.json()["id"] == original_id

    # Asserção de ESTADO: nenhum post duplicado
    post_count = client.app.state.post_repo.count()  # type: ignore[union-attr]
    assert post_count == 1, f"Esperado 1 post no repositório, encontrado {post_count}"


# ---------------------------------------------------------------------------
# CA-F001-03: payload inválido em title → 422 com type validation_error
# Cobre: ausente, vazio (após strip) e tipo não-string (branch validator schemas.py)
# ---------------------------------------------------------------------------
# CA-F001-03 — título ausente: asserta especificamente field=title (requisito CA)
def test_missing_title_returns_422_pointing_title_field(client: TestClient) -> None:
    resp = client.post(
        "/v1/posts",
        json={"content": "Conteúdo sem título."},
        headers={"Idempotency-Key": IDEM_KEY},
    )

    assert resp.status_code == 422
    data = resp.json()
    assert data["type"].endswith("validation_error")
    assert resp.headers.get("content-type", "").startswith("application/problem+json")

    fields = [e["field"] for e in data.get("errors", [])]
    assert "title" in fields, f"Campo 'title' não encontrado em errors: {fields}"


# Variações de input inválido — cobrem branches dos validators (schemas.py:19,26)
@pytest.mark.parametrize(
    "body",
    [
        {"title": "", "content": "Conteúdo."},  # title vazio
        {"title": "   ", "content": "Conteúdo."},  # title só espaços (strip → "")
        {"title": 123, "content": "Conteúdo."},  # title não-string (branch schemas.py:19)
        {"title": "Título.", "content": 999},  # content não-string (branch schemas.py:26)
    ],
    ids=["empty_title", "whitespace_only_title", "title_non_string", "content_non_string"],
)
def test_invalid_payload_returns_422(client: TestClient, body: dict) -> None:
    resp = client.post(
        "/v1/posts",
        json=body,
        headers={"Idempotency-Key": IDEM_KEY},
    )

    assert resp.status_code == 422
    data = resp.json()
    assert data["type"].endswith("validation_error")
    fields = [e["field"] for e in data.get("errors", [])]
    assert fields, f"Nenhum campo em errors: {data}"


# ---------------------------------------------------------------------------
# CA-F001-04: sem header Idempotency-Key → 400 idempotency_key_required
# ---------------------------------------------------------------------------
def test_missing_idempotency_key_returns_400(client: TestClient) -> None:
    resp = client.post("/v1/posts", json=VALID_BODY)

    assert resp.status_code == 400
    data = resp.json()
    assert data["type"].endswith("idempotency_key_required")
    assert resp.headers.get("content-type", "").startswith("application/problem+json")

    # Asserção de ESTADO: nenhum post deve ter sido criado (guard disparou antes do caso de uso)
    assert client.app.state.post_repo.count() == 0  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Extra: mesma chave + payload divergente → 409 idempotency_key_conflict
# ---------------------------------------------------------------------------
def test_conflicting_payload_same_key_returns_409(client: TestClient) -> None:
    client.post(
        "/v1/posts",
        json=VALID_BODY,
        headers={"Idempotency-Key": IDEM_KEY},
    )

    resp = client.post(
        "/v1/posts",
        json={"title": "Título diferente", "content": "Conteúdo diferente."},
        headers={"Idempotency-Key": IDEM_KEY},
    )

    assert resp.status_code == 409
    data = resp.json()
    assert data["type"].endswith("idempotency_key_conflict")
