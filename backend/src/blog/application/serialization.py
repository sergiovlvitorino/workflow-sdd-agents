"""Serialização compartilhada de Post → dict de resposta HTTP."""

from __future__ import annotations

from typing import Any

from blog.domain.post import Post


def to_response_dict(post: Post) -> dict[str, Any]:
    """Serializa Post para o formato de resposta da API (005-api-contract).

    - datetime com sufixo Z (não +00:00).
    - status como string (.value).
    - published_at = null quando rascunho.
    """
    return {
        "id": post.id,
        "title": post.title,
        "content": post.content,
        "status": post.status.value,
        "created_at": post.created_at.isoformat().replace("+00:00", "Z"),
        "published_at": post.published_at.isoformat().replace("+00:00", "Z") if post.published_at is not None else None,
    }
