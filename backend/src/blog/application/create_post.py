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

        replayed=True → mesma chave+payload, resposta original recuperada
        (via fast-path sequencial ou replay do vencedor do claim concorrente).
        replayed=False → criação nova (só o vencedor do claim cria).
        Levanta IdempotencyConflict se a chave já existe com payload diferente
        (sequencial ou sob concorrência — P-11).

        Claim-antes-de-criar (ADR-0007): fecha o TOCTOU. O `get` de fast-path
        cobre replay/409 sequenciais (inalterado). Quando duas chamadas
        atravessam `existing is None` na mesma janela, o `put` (claim write-once
        atômico) decide quem cria; o perdedor faz replay do vencedor ou 409.

        Assimetria deliberada de lock (fronteira do SEC-06): só o `get`/`put`
        do `IdempotencyStore` (a porta que decide o claim) é serializado sob
        `_lock` no adapter SQLite. Leituras de `PostRepository` (`get`/`count`/
        `list_published`) seguem sem lock — não são chamadas concorrentemente
        com escrita neste use-case. Se algum caminho futuro passar a chamar
        `PostRepository` sob concorrência real, revisar (workstream SEC-06).
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
        candidate_resp = to_response_dict(post)
        won = self._idem.put(key, payload_hash, candidate_resp)

        if won:
            self._repo.add(post)  # só o VENCEDOR do claim persiste o post
            return dict(candidate_resp), False  # cópia defensiva (evita aliasing com o store)

        # PERDEDOR: outra chamada concorrente reivindicou a key primeiro.
        winner = self._idem.get(key)
        assert winner is not None  # write-once (C-4/C-5): perdeu → vencedor já visível
        stored_hash, stored_resp = winner
        if stored_hash != payload_hash:
            raise IdempotencyConflict()  # 409 sob concorrência (payload divergente) — P-11
        return dict(stored_resp), True  # replay do vencedor; não faz add


def _sha256_payload(title: str, content: str) -> str:
    """Hash determinístico do payload (não usa hash() — PYTHONHASHSEED)."""
    canonical = json.dumps({"title": title, "content": content}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()
