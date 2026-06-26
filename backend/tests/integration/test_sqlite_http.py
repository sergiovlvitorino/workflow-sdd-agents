"""Integração HTTP com wiring de produção SQLite — ADR-0003 §8.

Monta a app com SqlitePostRepository e SqliteIdempotencyStore reais (arquivo tmp_path).
Garante que o wiring de DI de produção funciona end-to-end (anti-falso-verde).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from blog.infrastructure.sqlite_repository import (
    SqliteHandle,
    SqliteIdempotencyStore,
    SqlitePostRepository,
    init_schema,
    make_connection,
)
from blog.main import create_app


@pytest.fixture()
def sqlite_client(tmp_path: Path) -> TestClient:  # type: ignore[misc]
    """TestClient com app montada sobre SQLite real em arquivo temporário."""
    handle: SqliteHandle = make_connection(str(tmp_path / "http_test.db"))
    init_schema(handle.conn)
    repo = SqlitePostRepository(handle.conn, handle.lock)
    idem = SqliteIdempotencyStore(handle.conn, handle.lock)
    app = create_app(repo=repo, idem=idem)
    yield TestClient(app, raise_server_exceptions=False)
    handle.conn.close()


VALID_BODY = {"title": "Post SQLite HTTP", "content": "Conteúdo via SQLite."}
IDEM_KEY = "sqlite-http-key-001"


def test_create_post_sqlite_wiring_returns_201(sqlite_client: TestClient) -> None:
    """CA-F001-01 com wiring SQLite real: criação bem-sucedida → 201."""
    resp = sqlite_client.post(
        "/v1/posts",
        json=VALID_BODY,
        headers={"Idempotency-Key": IDEM_KEY},
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["id"]
    assert data["status"] == "draft"
    assert data["title"] == VALID_BODY["title"]


def test_replay_sqlite_returns_200_with_replayed_header(sqlite_client: TestClient) -> None:
    """Replay de idempotência com SqliteIdempotencyStore real → count==1."""
    first = sqlite_client.post(
        "/v1/posts",
        json=VALID_BODY,
        headers={"Idempotency-Key": IDEM_KEY},
    )
    assert first.status_code == 201
    original_id = first.json()["id"]

    second = sqlite_client.post(
        "/v1/posts",
        json=VALID_BODY,
        headers={"Idempotency-Key": IDEM_KEY},
    )

    assert second.status_code == 200
    assert second.headers.get("idempotent-replayed") == "true"
    assert second.json()["id"] == original_id

    # Estado: apenas 1 post no repositório SQLite
    count = sqlite_client.app.state.post_repo.count()  # type: ignore[union-attr]
    assert count == 1, f"Esperado 1 post, encontrado {count}"


def test_conflicting_payload_sqlite_returns_409(sqlite_client: TestClient) -> None:
    """Conflito de idempotência com store SQLite real → 409."""
    sqlite_client.post(
        "/v1/posts",
        json=VALID_BODY,
        headers={"Idempotency-Key": IDEM_KEY},
    )

    resp = sqlite_client.post(
        "/v1/posts",
        json={"title": "Título diferente", "content": "Conteúdo diferente."},
        headers={"Idempotency-Key": IDEM_KEY},
    )

    assert resp.status_code == 409


def test_missing_idempotency_key_sqlite_returns_400(sqlite_client: TestClient) -> None:
    """Guard de idempotency-key com wiring SQLite → 400 sem criar post."""
    resp = sqlite_client.post("/v1/posts", json=VALID_BODY)

    assert resp.status_code == 400
    count = sqlite_client.app.state.post_repo.count()  # type: ignore[union-attr]
    assert count == 0
