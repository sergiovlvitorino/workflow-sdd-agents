"""Cursor opaco para paginação keyset (ADR-0002).

Codec: base64url(json{"p": published_at_iso, "id": post_id}).
O cliente trata o cursor como token cego — nunca o constrói nem interpreta.
Qualquer falha de decodificação/validação → InvalidCursor (→ 400, P-11).
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone


class InvalidCursor(Exception):
    """Cursor malformado ou corrompido — nunca silencioso (P-11, ADR-0002)."""


def encode_cursor(published_at: datetime, post_id: str) -> str:
    """Codifica (published_at, post_id) em cursor opaco base64url."""
    payload = json.dumps(
        {"p": published_at.isoformat(), "id": post_id},
        separators=(",", ":"),
    )
    return base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")


def decode_cursor(raw: str) -> tuple[datetime, str]:
    """Decodifica cursor opaco → (published_at, post_id).

    Levanta InvalidCursor para qualquer entrada malformada:
    padding inválido, JSON corrompido, campo ausente, data inválida.
    """
    try:
        # Repadding: base64url pode ter padding removido
        padding = 4 - len(raw) % 4
        padded = raw + "=" * (padding % 4)
        decoded = base64.urlsafe_b64decode(padded).decode()
        data = json.loads(decoded)
        published_at = datetime.fromisoformat(data["p"])
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)
        post_id: str = data["id"]
        if not isinstance(post_id, str) or not post_id:
            raise InvalidCursor()
        return published_at, post_id
    except (KeyError, ValueError, UnicodeDecodeError, Exception) as exc:
        raise InvalidCursor() from exc
