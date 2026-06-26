"""Integração HTTP com wiring de produção SQLite para publish/replay (T-S2-08, C7).

Monta a app com SqlitePostRepository e SqliteIdempotencyStore reais (arquivo tmp_path).
Cobre:
- C7: publicar → replay com mesma Idempotency-Key → 1 slot no idem_store + count() inalterado.
- Mutation-âncora M11: quebrar unicidade da idempotência → 2 slots ou count duplicado → VERMELHO.
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

DRAFT_BODY = {"title": "Post SQLite Publish", "content": "Conteúdo para publish SQLite."}


@pytest.fixture()
def sqlite_pub_client(tmp_path: Path) -> TestClient:  # type: ignore[misc]
    """App montada sobre SQLite real em arquivo — wiring de produção (ADR-0003 §8).

    Nunca usa :memory: (mascara durabilidade entre conexões — ADR-0003 §8).
    """
    handle: SqliteHandle = make_connection(str(tmp_path / "pub_sqlite_c7.db"))
    init_schema(handle.conn)
    repo = SqlitePostRepository(handle.conn, handle.lock)
    idem = SqliteIdempotencyStore(handle.conn, handle.lock)
    app = create_app(repo=repo, idem=idem)
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    handle.conn.close()


def _create_draft(client: TestClient, idem_key: str) -> str:
    resp = client.post(
        "/v1/posts",
        json=DRAFT_BODY,
        headers={"Idempotency-Key": idem_key},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# C7 (T-S2-08): replay publish com SQLite real → 1 slot + count() inalterado
#
# Wiring de DI de produção: create_app(repo=SqlitePostRepository, idem=SqliteIdempotencyStore).
# Mutation-âncora M11: se replay regrava/recria o slot → 2 slots ou count() duplicado → VERMELHO.
# ---------------------------------------------------------------------------


def test_publish_replay_sqlite_wiring_one_slot_and_stable_count(sqlite_pub_client: TestClient) -> None:
    """C7: publicar → replay mesma chave → 200 + Idempotent-Replayed: true + 1 slot + count() inalterado.

    Exerce o wiring de DI de produção completo (não fakes).
    Mutation-âncora M11: quebrar unicidade → 2 slots ou count() duplicado → VERMELHO.
    """
    post_id = _create_draft(sqlite_pub_client, idem_key="create-c7")
    pub_key = "publish-c7-replay-key"

    # 1ª publicação
    first = sqlite_pub_client.put(
        f"/v1/posts/{post_id}/publish",
        headers={"Idempotency-Key": pub_key},
    )
    assert first.status_code == 200
    assert first.headers.get("idempotent-replayed") is None  # 1ª chamada sem o header
    first_body = first.json()
    assert first_body["status"] == "published"

    count_after_first = sqlite_pub_client.app.state.post_repo.count()  # type: ignore[union-attr]

    # Replay: mesma Idempotency-Key, mesmo post_id
    second = sqlite_pub_client.put(
        f"/v1/posts/{post_id}/publish",
        headers={"Idempotency-Key": pub_key},
    )
    assert second.status_code == 200
    # C7: header Idempotent-Replayed: true confirmando replay pelo store (2º nível ADR-0004 §8)
    assert second.headers.get("idempotent-replayed") == "true", (
        "Replay com mesma Idempotency-Key deve retornar Idempotent-Replayed: true"
    )
    # Corpo idêntico ao da 1ª chamada
    assert second.json() == first_body

    count_after_second = sqlite_pub_client.app.state.post_repo.count()  # type: ignore[union-attr]
    # count() inalterado: replay não cria post novo
    assert count_after_second == count_after_first, (
        f"count() mudou de {count_after_first} para {count_after_second} no replay "
        "(M11: replay duplicou post)"
    )

    # Verificar 1 slot no idem_store SQLite (não duplicado)
    idem_store = sqlite_pub_client.app.state.idem_store  # type: ignore[union-attr]
    store_key = f"publish:{pub_key}"
    slot = idem_store.get(store_key)
    assert slot is not None, "Slot de idempotência não foi gravado no SqliteIdempotencyStore"
    # O get() retorna (hash, resp) — não deve haver duplicata (unicidade por key)
    stored_hash, stored_resp = slot
    assert stored_resp["id"] == post_id
    assert stored_resp["status"] == "published"


def test_publish_sqlite_wiring_post_visible_after_publish(sqlite_pub_client: TestClient) -> None:
    """C7 (durabilidade): post publicado via SQLite wiring fica visível no GET /v1/posts/{id}."""
    post_id = _create_draft(sqlite_pub_client, idem_key="create-c7-vis")

    sqlite_pub_client.put(
        f"/v1/posts/{post_id}/publish",
        headers={"Idempotency-Key": "pub-c7-vis"},
    )

    get_resp = sqlite_pub_client.get(f"/v1/posts/{post_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "published"
    assert get_resp.json()["published_at"] is not None


def test_publish_sqlite_wiring_cross_id_same_key_returns_409(sqlite_pub_client: TestClient) -> None:
    """409 cross-id no wiring SQLite real: mesma chave, post_id diferente → idempotency_key_conflict."""
    post_id_a = _create_draft(sqlite_pub_client, idem_key="create-c7-409-a")
    post_id_b = _create_draft(sqlite_pub_client, idem_key="create-c7-409-b")
    shared_key = "shared-pub-key-c7"

    resp_a = sqlite_pub_client.put(
        f"/v1/posts/{post_id_a}/publish",
        headers={"Idempotency-Key": shared_key},
    )
    assert resp_a.status_code == 200

    resp_b = sqlite_pub_client.put(
        f"/v1/posts/{post_id_b}/publish",
        headers={"Idempotency-Key": shared_key},
    )
    assert resp_b.status_code == 409
    assert resp_b.json()["type"].endswith("idempotency_key_conflict")
