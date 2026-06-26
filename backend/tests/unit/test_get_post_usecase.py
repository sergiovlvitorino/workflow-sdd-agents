"""Unit tests — GetPublishedPost (CA-F004-01/02, ADR-0004 §8 allowlist P-04).

Exercitam o caso de uso isolado via InMemoryPostRepository.
Mutation-âncora: remover a guarda de allowlist (aceitar qualquer status) faz
CA-F004-02 vermelho.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from blog.application.get_post import GetPublishedPost
from blog.application.publish_post import PostNotFound
from blog.domain.post import Post, PostStatus
from blog.infrastructure.in_memory import InMemoryPostRepository

_NOW = datetime(2026, 6, 25, 10, 0, 0, tzinfo=timezone.utc)
_PUBLISHED_AT = datetime(2026, 6, 25, 11, 0, 0, tzinfo=timezone.utc)


def _make_repo_with(*posts: Post) -> InMemoryPostRepository:
    repo = InMemoryPostRepository()
    for p in posts:
        repo.add(p)
    return repo


def _draft(post_id: str = "draft-001") -> Post:
    return Post(
        id=post_id,
        title="Rascunho",
        content="Conteúdo do rascunho.",
        status=PostStatus.DRAFT,
        created_at=_NOW,
        published_at=None,
    )


def _published(post_id: str = "pub-001") -> Post:
    return Post(
        id=post_id,
        title="Post Publicado",
        content="Conteúdo publicado.",
        status=PostStatus.PUBLISHED,
        created_at=_NOW,
        published_at=_PUBLISHED_AT,
    )


# ---------------------------------------------------------------------------
# CA-F004-01: post publicado → retorna dict com campos corretos
# ---------------------------------------------------------------------------


def test_execute_returns_dict_for_published_post() -> None:
    post = _published()
    use_case = GetPublishedPost(repo=_make_repo_with(post))

    result = use_case.execute(post.id)

    assert result["id"] == post.id
    assert result["title"] == post.title
    assert result["content"] == post.content
    assert result["status"] == "published"
    assert result["published_at"] is not None


# ---------------------------------------------------------------------------
# CA-F004-02: draft → PostNotFound (não revela existência, P-04)
# ---------------------------------------------------------------------------


def test_execute_raises_post_not_found_for_draft() -> None:
    post = _draft()
    use_case = GetPublishedPost(repo=_make_repo_with(post))

    with pytest.raises(PostNotFound):
        use_case.execute(post.id)


# ---------------------------------------------------------------------------
# CA-F004-02: inexistente → PostNotFound (mesmo caminho que draft)
# ---------------------------------------------------------------------------


def test_execute_raises_post_not_found_for_nonexistent() -> None:
    use_case = GetPublishedPost(repo=InMemoryPostRepository())

    with pytest.raises(PostNotFound):
        use_case.execute("ID-QUE-NAO-EXISTE")


# ---------------------------------------------------------------------------
# Mutation-âncora: allowlist (is PUBLISHED) — se aceitar draft, este teste falha
# ---------------------------------------------------------------------------


def test_allowlist_draft_does_not_return_dict() -> None:
    """Garante que draft NUNCA retorna dados — qualquer liberação faz este teste vermelho."""
    post = _draft()
    use_case = GetPublishedPost(repo=_make_repo_with(post))

    with pytest.raises(PostNotFound):
        use_case.execute(post.id)
