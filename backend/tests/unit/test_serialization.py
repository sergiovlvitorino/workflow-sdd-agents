"""Testes unitários de blog.application.serialization.to_response_dict."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from blog.application.serialization import to_response_dict
from blog.domain.post import Post, PostStatus

_NOW = datetime(2024, 3, 15, 10, 30, 0, tzinfo=timezone.utc)
_PUB = datetime(2024, 3, 16, 12, 0, 0, tzinfo=timezone.utc)


def _make_post(*, published: bool) -> Post:
    return Post(
        id="abc-123",
        title="Titulo do Post",
        content="Conteudo aqui.",
        status=PostStatus.PUBLISHED if published else PostStatus.DRAFT,
        created_at=_NOW,
        published_at=_PUB if published else None,
    )


def test_to_response_dict_post_publicado() -> None:
    """Todos os campos presentes; datetimes com sufixo Z; status como string."""
    result = to_response_dict(_make_post(published=True))

    assert result == {
        "id": "abc-123",
        "title": "Titulo do Post",
        "content": "Conteudo aqui.",
        "status": "published",
        "created_at": "2024-03-15T10:30:00Z",
        "published_at": "2024-03-16T12:00:00Z",
    }


def test_to_response_dict_rascunho_published_at_none() -> None:
    """Rascunho: published_at deve ser None (não ausente, mas explicitamente null)."""
    result = to_response_dict(_make_post(published=False))

    assert result == {
        "id": "abc-123",
        "title": "Titulo do Post",
        "content": "Conteudo aqui.",
        "status": "draft",
        "created_at": "2024-03-15T10:30:00Z",
        "published_at": None,
    }
    # Garante que a chave exists com valor None, não simplesmente ausente
    assert "published_at" in result
    assert result["published_at"] is None


@pytest.mark.parametrize("suffix", ["+00:00", "UTC"])
def test_created_at_nao_contem_offset_nao_z(suffix: str) -> None:
    """Confirma que o formato Z substitui +00:00 corretamente."""
    result = to_response_dict(_make_post(published=False))
    assert suffix not in result["created_at"]
    assert result["created_at"].endswith("Z")
