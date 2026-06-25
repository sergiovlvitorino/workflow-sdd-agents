"""Adapter SQLite — PostRepository + IdempotencyStore (ADR-0003).

Estratégia de concorrência: conexão única compartilhada + threading.Lock ÚNICO
(criado junto com a conexão e injetado em ambos os adapters) nas escritas
+ PRAGMA journal_mode=WAL. Leituras são consistentes sob WAL sem lock adicional.

O lock compartilhado é essencial: SqlitePostRepository.add() e
SqliteIdempotencyStore.put() são chamados em sequência pelo mesmo request
(create_post.py). Locks separados não se excluem mutuamente e permitem
que ambos entrem em `with self._conn:` concorrentemente → transações
intercaladas → comportamento intermitente (P-11, ADR-0003 §4.3).
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from datetime import datetime, timezone
from typing import NamedTuple

from blog.domain.post import Post, PostStatus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers de serialização de datetime
# ---------------------------------------------------------------------------

def _iso(dt: datetime | None) -> str | None:
    """Serializa datetime tz-aware UTC para ISO-8601 com sufixo +00:00."""
    return dt.isoformat() if dt is not None else None


def _parse(s: str | None) -> datetime | None:
    """Desserializa string ISO-8601 para datetime tz-aware. Nunca devolve naive."""
    if s is None:
        return None
    dt = datetime.fromisoformat(s)
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Schema e conexão
# ---------------------------------------------------------------------------

_DDL = """
CREATE TABLE IF NOT EXISTS posts (
    id           TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    content      TEXT NOT NULL,
    status       TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    published_at TEXT
);

CREATE INDEX IF NOT EXISTS ix_posts_published
    ON posts (published_at DESC, id DESC)
    WHERE status = 'published';

CREATE TABLE IF NOT EXISTS idempotency_keys (
    key           TEXT PRIMARY KEY,
    payload_hash  TEXT NOT NULL,
    response_json TEXT NOT NULL
);
"""


def init_schema(conn: sqlite3.Connection) -> None:
    """Cria tabelas e índices de forma idempotente (CREATE ... IF NOT EXISTS)."""
    conn.executescript(_DDL)
    conn.commit()
    logger.debug("Schema SQLite inicializado")


class SqliteHandle(NamedTuple):
    """Holder da conexão e do lock de escrita compartilhado.

    O lock DEVE ser o mesmo objeto para PostRepository e IdempotencyStore
    que usam a mesma conexão — caso contrário as escritas sequenciais do
    mesmo request não se excluem mutuamente (ADR-0003 §4.3, P-11).
    """

    conn: sqlite3.Connection
    lock: threading.Lock


def make_connection(db_path: str) -> SqliteHandle:
    """Abre conexão SQLite e cria o lock compartilhado (ADR-0003 §4.3).

    Retorna SqliteHandle(conn, lock) — passe o mesmo handle para
    SqlitePostRepository e SqliteIdempotencyStore.
    """
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return SqliteHandle(conn=conn, lock=threading.Lock())


# ---------------------------------------------------------------------------
# Mapeamento row → Post
# ---------------------------------------------------------------------------

def _row_to_post(row: sqlite3.Row) -> Post:
    return Post(
        id=row["id"],
        title=row["title"],
        content=row["content"],
        status=PostStatus(row["status"]),
        created_at=_parse(row["created_at"]),  # type: ignore[arg-type]
        published_at=_parse(row["published_at"]),
    )


# ---------------------------------------------------------------------------
# SqlitePostRepository
# ---------------------------------------------------------------------------

class SqlitePostRepository:
    """Repositório de posts com persistência SQLite (ADR-0003).

    add() usa UPSERT (INSERT ... ON CONFLICT DO UPDATE) para suportar a
    transição de status draft → published sem duplicar o registro (requisito
    da futura T-S2-05). A idempotência de criação é garantida pelo
    IdempotencyStore (P-03).

    O lock de escrita deve ser o MESMO objeto injetado no SqliteIdempotencyStore
    que usa a mesma conexão (ver SqliteHandle).
    """

    def __init__(self, conn: sqlite3.Connection, lock: threading.Lock) -> None:
        self._conn = conn
        self._lock = lock

    def add(self, post: Post) -> None:
        """UPSERT: insere ou atualiza todos os campos por id (suporta publicação futura)."""
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO posts (id, title, content, status, created_at, published_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title        = excluded.title,
                    content      = excluded.content,
                    status       = excluded.status,
                    created_at   = excluded.created_at,
                    published_at = excluded.published_at
                """,
                (
                    post.id,
                    post.title,
                    post.content,
                    post.status.value,
                    _iso(post.created_at),
                    _iso(post.published_at),
                ),
            )

    def get(self, id: str) -> Post | None:
        """Retorna Post por PK ou None se ausente."""
        row = self._conn.execute(
            "SELECT * FROM posts WHERE id = ?", (id,)
        ).fetchone()
        return _row_to_post(row) if row is not None else None

    def count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM posts").fetchone()
        return int(row[0])

    def list_published(
        self,
        *,
        after: tuple[datetime, str] | None,
        limit: int,
    ) -> list[Post]:
        """Keyset (published_at DESC, id DESC) com row-value estrito '<' (ADR-0002)."""
        if after is None:
            rows = self._conn.execute(
                "SELECT * FROM posts WHERE status = 'published' "
                "ORDER BY published_at DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        else:
            after_ts, after_id = after
            rows = self._conn.execute(
                "SELECT * FROM posts WHERE status = 'published' "
                "AND (published_at < ? OR (published_at = ? AND id < ?)) "
                "ORDER BY published_at DESC, id DESC LIMIT ?",
                (_iso(after_ts), _iso(after_ts), after_id, limit),
            ).fetchall()
        return [_row_to_post(r) for r in rows]


# ---------------------------------------------------------------------------
# SqliteIdempotencyStore
# ---------------------------------------------------------------------------

class SqliteIdempotencyStore:
    """Idempotency store write-once com INSERT OR IGNORE + UNIQUE (P-03, ADR-0003 §4.4).

    put() é naturalmente idempotente: segunda chamada com mesma key é no-op.

    O lock de escrita deve ser o MESMO objeto injetado no SqlitePostRepository
    que usa a mesma conexão (ver SqliteHandle).
    """

    def __init__(self, conn: sqlite3.Connection, lock: threading.Lock) -> None:
        self._conn = conn
        self._lock = lock

    def get(self, key: str) -> tuple[str, dict[str, object]] | None:
        row = self._conn.execute(
            "SELECT payload_hash, response_json FROM idempotency_keys WHERE key = ?",
            (key,),
        ).fetchone()
        if row is None:
            return None
        return row["payload_hash"], json.loads(row["response_json"])

    def put(self, key: str, payload_hash: str, response_json: dict[str, object]) -> None:
        """Write-once: INSERT OR IGNORE garante atomicidade sem sobrescrever (P-03)."""
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR IGNORE INTO idempotency_keys (key, payload_hash, response_json) "
                "VALUES (?, ?, ?)",
                (key, payload_hash, json.dumps(response_json, ensure_ascii=False)),
            )
