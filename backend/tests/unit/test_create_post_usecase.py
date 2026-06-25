"""Unit tests do caso de uso CreatePost com fakes.

Os fakes retornam o objeto visível no estado (não None quando há registro)
para que as mutation-âncoras sejam alcançáveis (docs/lessons/qa.md).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from blog.application.create_post import CreatePost, IdempotencyConflict
from blog.domain.post import Post, PostStatus
from blog.infrastructure.in_memory import InMemoryIdempotencyStore, InMemoryPostRepository

FIXED_ID = "01JWXYZ000000000000000001"
FIXED_NOW = datetime(2026, 6, 24, 14, 30, 0, tzinfo=timezone.utc)


def _make_use_case(
    repo: InMemoryPostRepository | None = None,
    idem: InMemoryIdempotencyStore | None = None,
) -> CreatePost:
    return CreatePost(
        repo=repo or InMemoryPostRepository(),
        idem=idem or InMemoryIdempotencyStore(),
        clock=lambda: FIXED_NOW,
        id_gen=lambda: FIXED_ID,
    )


# ---------------------------------------------------------------------------
# Criação: post novo, id e status corretos
# ---------------------------------------------------------------------------
def test_execute_creates_post_with_injected_id_and_clock() -> None:
    repo = InMemoryPostRepository()
    uc = _make_use_case(repo=repo)

    resp, replayed = uc.execute("key-1", "Título", "Conteúdo")

    assert replayed is False
    assert resp["id"] == FIXED_ID
    assert resp["status"] == PostStatus.DRAFT.value
    assert repo.count() == 1


# ---------------------------------------------------------------------------
# Replay: mesma chave + payload → devolve resposta gravada, sem criar novo post
# ---------------------------------------------------------------------------
def test_replay_returns_stored_response_without_creating_new_post() -> None:
    repo = InMemoryPostRepository()
    idem = InMemoryIdempotencyStore()
    uc = _make_use_case(repo=repo, idem=idem)

    first_resp, _ = uc.execute("key-1", "Título", "Conteúdo")
    second_resp, replayed = uc.execute("key-1", "Título", "Conteúdo")

    assert replayed is True
    assert second_resp["id"] == first_resp["id"]
    # Estado: apenas 1 post criado
    assert repo.count() == 1


# ---------------------------------------------------------------------------
# Conflito: mesma chave, payload diferente → IdempotencyConflict
# ---------------------------------------------------------------------------
def test_conflicting_payload_raises_idempotency_conflict() -> None:
    uc = _make_use_case()
    uc.execute("key-1", "Título original", "Conteúdo original")

    with pytest.raises(IdempotencyConflict):
        uc.execute("key-1", "Título diferente", "Conteúdo diferente")


# ---------------------------------------------------------------------------
# Determinismo do hash: mesmo payload → mesmo hash (não depende de PYTHONHASHSEED)
# ---------------------------------------------------------------------------
def test_sha256_hash_is_deterministic_across_calls() -> None:
    from blog.application.create_post import _sha256_payload

    h1 = _sha256_payload("Título", "Conteúdo")
    h2 = _sha256_payload("Título", "Conteúdo")
    assert h1 == h2


def test_sha256_differs_for_different_payloads() -> None:
    from blog.application.create_post import _sha256_payload

    h1 = _sha256_payload("Título A", "Conteúdo")
    h2 = _sha256_payload("Título B", "Conteúdo")
    assert h1 != h2


# ---------------------------------------------------------------------------
# _error_body: branch detail=None (campo omitido no corpo)
# ---------------------------------------------------------------------------
def test_error_body_without_detail_omits_detail_key() -> None:
    from blog.interfaces.errors import _error_body

    body = _error_body(type_suffix="some_error", title="Erro", status=400)
    assert "detail" not in body
    assert "errors" not in body


# ---------------------------------------------------------------------------
# Domínio puro: Post.create usa id e clock injetados
# ---------------------------------------------------------------------------
def test_post_create_uses_injected_id_and_clock() -> None:
    post = Post.create("Título", "Conteúdo", new_id=FIXED_ID, now=FIXED_NOW)

    assert post.id == FIXED_ID
    assert post.created_at == FIXED_NOW
    assert post.status == PostStatus.DRAFT
    assert post.published_at is None
