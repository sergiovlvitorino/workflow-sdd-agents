"""
Adapters in-memory — DIDÁTICO (ADR-0001).

Propósito exclusivamente pedagógico: mostra a separação de portas e adapters
sem exigir infraestrutura externa. Substituível por SQLite/Postgres sem alterar
o domínio ou os casos de uso (P-06/P-12).

NAO use em produção.
"""

from __future__ import annotations

import threading
from datetime import datetime

from blog.domain.post import Post, PostStatus


class InMemoryPostRepository:
    """Repositório de posts em memória — DIDÁTICO."""

    def __init__(self) -> None:
        self._store: dict[str, Post] = {}

    def add(self, post: Post) -> None:
        self._store[post.id] = post

    def get(self, id: str) -> Post | None:
        return self._store.get(id)

    def count(self) -> int:
        return len(self._store)

    def list_published(
        self,
        *,
        after: tuple[datetime, str] | None,
        limit: int,
    ) -> list[Post]:
        """Keyset in-memory equivalente a WHERE (published_at, id) < (:p, :id).

        Ordenação total: (published_at DESC, id DESC).
        Filtro allowlist: só PostStatus.PUBLISHED (RF-006, P-04).
        Keyset estrito '<' (ADR-0002): nunca repete a fronteira.
        """
        # Allowlist: só publicados (nunca rascunhos — RF-006)
        items: list[Post] = [p for p in self._store.values() if p.status is PostStatus.PUBLISHED]
        # Ordenação total determinística (published_at DESC, id DESC)
        items.sort(key=lambda p: (p.published_at, p.id), reverse=True)

        if after is not None:
            after_ts, after_id = after
            # Keyset estrito '<': exclui o item de fronteira e tudo antes (ADR-0002)
            items = [p for p in items if (p.published_at, p.id) < (after_ts, after_id)]

        return items[:limit]


class InMemoryIdempotencyStore:
    """Idempotency store em memória — DIDÁTICO."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[str, dict[str, object]]] = {}
        self._lock = threading.Lock()  # NOVO (ADR-0007): torna o check-and-set atômico

    def get(self, key: str) -> tuple[str, dict[str, object]] | None:
        return self._store.get(key)

    def put(self, key: str, payload_hash: str, response_json: dict[str, object]) -> bool:
        """Claim write-once atômico (ADR-0007): retorna True sse esta chamada venceu.

        Sem o lock, `if key not in store` / `store[key]=...` é check-then-set
        não-atômico: sob threads concorrentes, mais de uma passaria pelo `if`
        e todas retornariam True — o bool mentiria sob corrida (P-03/C-1).

        Correto por construção, mas NÃO ancorável pela suíte threaded padrão:
        a corrida é interna a este `put` (entre o `if` e o `store[key]=`), e em
        operações Python puras rápidas sem I/O o GIL raramente interleava
        threads dentro dessa janela estreita — um `Barrier` externo ao redor
        de chamadas a `put()` não a expõe de forma confiável (mutation-teste
        threaded fica verde mesmo sem o lock, neste ambiente). Demonstrado via
        sonda de corrida forçada (monkeypatch com `time.sleep` entre o `if` e o
        `store[key]=`, fora da suíte): sem lock, N/N threads retornam `True`.
        Registrado honestamente como obrigação diferida (ADR-0007 §5/§8.5) —
        não é lacuna silenciosa.
        """
        with self._lock:
            if key in self._store:
                return False
            self._store[key] = (payload_hash, response_json)
            return True
