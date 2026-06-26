"""Unit tests do caso de uso PublishPost com fakes in-memory.

Cobre:
- Publicação de draft: estado persistido no repositório.
- Republicação idempotente: published_at não muda (relógio avançado para T2).
- Id inexistente: levanta PostNotFound sem efeito colateral.
- Contagem de publicados não muda ao republicar.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from blog.application.publish_post import PostNotFound, PublishPost
from blog.domain.post import Post, PostStatus
from blog.infrastructure.in_memory import InMemoryPostRepository

T1 = datetime(2026, 6, 25, 10, 0, 0, tzinfo=timezone.utc)
T2 = datetime(2026, 6, 25, 11, 0, 0, tzinfo=timezone.utc)
CREATED_AT = datetime(2026, 6, 25, 9, 0, 0, tzinfo=timezone.utc)
FIXED_ID = "01JWXYZ000000000000000001"
MISSING_ID = "00000000000000000000000000"


def _repo_with_draft() -> InMemoryPostRepository:
    repo = InMemoryPostRepository()
    draft = Post.create("Título", "Conteúdo", new_id=FIXED_ID, now=CREATED_AT)
    repo.add(draft)
    return repo


def _make_uc(repo: InMemoryPostRepository, clock_time: datetime) -> PublishPost:
    return PublishPost(repo=repo, clock=lambda: clock_time)


# ---------------------------------------------------------------------------
# Publicação de draft
# ---------------------------------------------------------------------------


def test_execute_publishes_draft_and_returns_published_status() -> None:
    repo = _repo_with_draft()
    uc = _make_uc(repo, T1)

    resp = uc.execute(FIXED_ID)

    assert resp["status"] == PostStatus.PUBLISHED.value


def test_execute_sets_published_at_in_response() -> None:
    repo = _repo_with_draft()
    uc = _make_uc(repo, T1)

    resp = uc.execute(FIXED_ID)

    assert resp["published_at"] is not None
    assert "2026-06-25" in resp["published_at"]


def test_execute_persists_published_state_in_repo() -> None:
    repo = _repo_with_draft()
    uc = _make_uc(repo, T1)

    uc.execute(FIXED_ID)

    persisted = repo.get(FIXED_ID)
    assert persisted is not None
    assert persisted.status == PostStatus.PUBLISHED
    assert persisted.published_at == T1


# ---------------------------------------------------------------------------
# Republicação idempotente (CA-F002-02 / RF-009)
# ---------------------------------------------------------------------------


def test_republish_is_idempotent_published_at_unchanged() -> None:
    """published_at da 1ª publicação (T1) não é substituído por T2 ao republicar.

    Prova que a guarda de no-op no domínio está ativa: relógio avança para T2
    mas published_at permanece T1.
    """
    repo = _repo_with_draft()

    # 1ª publicação com relógio em T1
    _make_uc(repo, T1).execute(FIXED_ID)
    published_at_first = repo.get(FIXED_ID).published_at  # type: ignore[union-attr]

    # Republicação com relógio em T2
    _make_uc(repo, T2).execute(FIXED_ID)
    published_at_second = repo.get(FIXED_ID).published_at  # type: ignore[union-attr]

    assert published_at_second == published_at_first
    assert published_at_second == T1


def test_republish_does_not_increase_published_count() -> None:
    """Contagem de publicados não muda ao republicar (CA-F002-02)."""
    repo = _repo_with_draft()

    _make_uc(repo, T1).execute(FIXED_ID)
    count_after_first = len(repo.list_published(after=None, limit=100))

    _make_uc(repo, T2).execute(FIXED_ID)
    count_after_second = len(repo.list_published(after=None, limit=100))

    assert count_after_second == count_after_first == 1


# ---------------------------------------------------------------------------
# Id inexistente → PostNotFound (CA-F002-03)
# ---------------------------------------------------------------------------


def test_execute_raises_post_not_found_for_missing_id() -> None:
    repo = InMemoryPostRepository()  # vazio
    uc = _make_uc(repo, T1)

    with pytest.raises(PostNotFound):
        uc.execute(MISSING_ID)


def test_execute_post_not_found_has_no_side_effects() -> None:
    """Nenhum post é criado ou alterado ao tentar publicar id inexistente."""
    repo = InMemoryPostRepository()
    uc = _make_uc(repo, T1)

    with pytest.raises(PostNotFound):
        uc.execute(MISSING_ID)

    assert repo.count() == 0
