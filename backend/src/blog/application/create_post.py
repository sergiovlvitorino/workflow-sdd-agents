"""Caso de uso: criar post com idempotência (ADR-0001)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import datetime
from typing import Any

from blog.application.ports import IdempotencyStore, PostRepository
from blog.application.serialization import to_response_dict
from blog.domain.post import Post


class IdempotencyConflict(Exception):
    """Mesma chave, payload divergente → 409."""


class CreatePost:
    def __init__(
        self,
        repo: PostRepository,
        idem: IdempotencyStore,
        *,
        clock: Callable[[], datetime],
        id_gen: Callable[[], str],
    ) -> None:
        self._repo = repo
        self._idem = idem
        self._clock = clock
        self._id_gen = id_gen

    def execute(
        self,
        key: str,
        title: str,
        content: str,
    ) -> tuple[dict[str, Any], bool]:
        """Retorna (response_dict, replayed).

        replayed=True → mesma chave+payload, resposta original recuperada.
        replayed=False → criação nova.
        Levanta IdempotencyConflict se a chave já existe com payload diferente.
        """
        payload_hash = _sha256_payload(title, content)
        existing = self._idem.get(key)

        if existing is not None:
            stored_hash, stored_resp = existing
            if stored_hash != payload_hash:
                raise IdempotencyConflict()
            return dict(stored_resp), True

        post = Post.create(
            title,
            content,
            new_id=self._id_gen(),
            now=self._clock(),
        )
        self._repo.add(post)
        resp = to_response_dict(post)
        self._idem.put(key, payload_hash, resp)
        return resp, False


def _sha256_payload(title: str, content: str) -> str:
    """Hash determinístico do payload (não usa hash() — PYTHONHASHSEED)."""
    canonical = json.dumps({"title": title, "content": content}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


