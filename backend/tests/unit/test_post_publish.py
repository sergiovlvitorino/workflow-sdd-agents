"""Unit tests de Post.publish — domínio puro (ADR-0004 §8).

Cobre:
- Transição draft → published com relógio injetado.
- No-op idempotente ao republicar (published_at inalterado).
- Imutabilidade: publish retorna novo objeto.
- Mutation-âncora: remover a guarda no-op mata o teste de republicação.
"""

from __future__ import annotations

from datetime import datetime, timezone

from blog.domain.post import Post, PostStatus

T1 = datetime(2026, 6, 25, 10, 0, 0, tzinfo=timezone.utc)
T2 = datetime(2026, 6, 25, 11, 0, 0, tzinfo=timezone.utc)
FIXED_ID = "01JWXYZ000000000000000001"
CREATED_AT = datetime(2026, 6, 25, 9, 0, 0, tzinfo=timezone.utc)


def _draft() -> Post:
    return Post.create("Título", "Conteúdo", new_id=FIXED_ID, now=CREATED_AT)


# ---------------------------------------------------------------------------
# Transição draft → published
# ---------------------------------------------------------------------------


def test_publish_draft_returns_new_post_with_published_status() -> None:
    post = _draft()
    published = post.publish(T1)

    assert published.status == PostStatus.PUBLISHED


def test_publish_draft_sets_published_at_to_injected_now() -> None:
    post = _draft()
    published = post.publish(T1)

    assert published.published_at == T1


def test_publish_draft_returns_new_object_preserving_immutability() -> None:
    post = _draft()
    published = post.publish(T1)

    # Post é frozen=True — publish devolve novo objeto
    assert published is not post
    assert post.status == PostStatus.DRAFT  # original inalterado


def test_publish_preserves_other_fields() -> None:
    post = _draft()
    published = post.publish(T1)

    assert published.id == post.id
    assert published.title == post.title
    assert published.content == post.content
    assert published.created_at == post.created_at


# ---------------------------------------------------------------------------
# No-op: republicar post já publicado (mutation-âncora ADR-0004 §8)
# ---------------------------------------------------------------------------


def test_republish_is_noop_returns_same_object() -> None:
    """Republicar retorna self — objeto idêntico por identidade."""
    post = _draft().publish(T1)
    republished = post.publish(T2)

    assert republished is post


def test_republish_does_not_reset_published_at() -> None:
    """published_at não é re-setado ao republicar — mutation-âncora.

    Remover a guarda `if self.status is PUBLISHED: return self` em Post.publish
    faz T2 substituir T1, tornando este teste VERMELHO.
    """
    first_published = _draft().publish(T1)
    republished = first_published.publish(T2)

    # published_at deve ser T1 (primeira publicação), não T2
    assert republished.published_at == T1
    assert republished.published_at != T2


def test_republish_status_remains_published() -> None:
    post = _draft().publish(T1)
    republished = post.publish(T2)

    assert republished.status == PostStatus.PUBLISHED
