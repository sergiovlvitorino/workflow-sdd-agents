"""Caso de uso: publicar post (CA-F002-01/02/03, ADR-0004 §8)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from blog.application.ports import PostRepository
from blog.application.serialization import to_response_dict


class PostNotFound(Exception):
    """Post não encontrado para publicação → router mapeia a 404 post_not_found (T-S2-06)."""


class PublishPost:
    def __init__(
        self,
        repo: PostRepository,
        *,
        clock: Callable[[], datetime],
    ) -> None:
        self._repo = repo
        self._clock = clock

    def execute(self, post_id: str) -> dict[str, Any]:
        """Publica o post identificado por `post_id`.

        - Draft → published (published_at = now do relógio injetado).
        - Already published → no-op idempotente (published_at inalterado).
        - Inexistente → levanta PostNotFound.
        """
        post = self._repo.get(post_id)
        if post is None:
            raise PostNotFound(post_id)

        published = post.publish(self._clock())
        if published is not post:
            # Houve transição real; persiste via upsert (add idempotente de T-S2-04)
            self._repo.add(published)

        return to_response_dict(published)
