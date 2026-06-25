"""Caso de uso: ler post publicado por id (CA-F004-01/02, ADR-0004 §8 — allowlist P-04)."""

from __future__ import annotations

from typing import Any

from blog.application.ports import PostRepository
from blog.application.publish_post import PostNotFound
from blog.application.serialization import to_response_dict
from blog.domain.post import Post, PostStatus


class GetPublishedPost:
    """Lê um post publicado por id.

    Allowlist por status (P-04): apenas PUBLISHED é visível.
    `None` (inexistente) e `draft` colapsam no MESMO `raise PostNotFound()` —
    resposta indistinguível por construção, não por coincidência de mensagem.
    """

    def __init__(self, repo: PostRepository) -> None:
        self._repo = repo

    def execute(self, post_id: str) -> dict[str, Any]:
        """Retorna dict do post se publicado; levanta PostNotFound caso contrário.

        ADR-0004 §8: não revela existência de rascunhos.
        """
        post: Post | None = self._repo.get(post_id)
        # ALLOWLIST (P-04): só PUBLISHED é visível — draft e ausente → mesmo caminho
        if post is None or post.status is not PostStatus.PUBLISHED:
            raise PostNotFound()
        return to_response_dict(post)
