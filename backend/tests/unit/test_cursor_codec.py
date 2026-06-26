"""Unit tests do codec de cursor (ADR-0002).

Round-trip encode→decode e rejeição de cursores corrompidos/malformados.
Mutation-âncora: fazer decode_cursor engolir erro e retornar None
deve deixar o teste de cursor inválido vermelho.
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone

import pytest

from blog.application.cursor import InvalidCursor, decode_cursor, encode_cursor

_DT = datetime(2026, 6, 24, 14, 30, 0, tzinfo=timezone.utc)
_ID = "01JWXYZ000000000000000001"


# ---------------------------------------------------------------------------
# Round-trip: encode → decode preserva (published_at, id)
# ---------------------------------------------------------------------------
def test_round_trip_preserves_published_at_and_id() -> None:
    raw = encode_cursor(_DT, _ID)
    dt_out, id_out = decode_cursor(raw)

    assert dt_out == _DT
    assert id_out == _ID


def test_encode_produces_url_safe_string() -> None:
    raw = encode_cursor(_DT, _ID)
    # Não deve conter '+', '/' nem '=' (base64url sem padding)
    assert "+" not in raw
    assert "/" not in raw
    assert "=" not in raw


def test_round_trip_with_timezone_naive_stored_as_utc() -> None:
    """decode_cursor converte naive → UTC (robustez de stored data)."""
    # Codifica manualmente um cursor sem tz info
    payload = json.dumps({"p": "2026-06-24T14:30:00", "id": _ID}, separators=(",", ":"))
    raw = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    dt_out, id_out = decode_cursor(raw)

    assert dt_out.tzinfo is not None
    assert id_out == _ID


# ---------------------------------------------------------------------------
# Cursores corrompidos → InvalidCursor (P-11: nunca silencioso)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "bad_cursor",
    [
        "nao_e_base64!!!",  # caracteres inválidos
        base64.urlsafe_b64encode(b"nao_e_json").decode().rstrip("="),  # base64 ok, JSON ruim
        base64.urlsafe_b64encode(b'{"p":"2026-06-24T14:30:00Z"}').decode().rstrip("="),  # sem "id"
        base64.urlsafe_b64encode(b'{"id":"abc"}').decode().rstrip("="),  # sem "p"
        base64.urlsafe_b64encode(b'{"p":"nao_e_data","id":"abc"}').decode().rstrip("="),  # data inválida
        base64.urlsafe_b64encode(b'{"p":"2026-06-24T14:30:00Z","id":""}').decode().rstrip("="),  # id vazio
        "",  # vazio
        "eyJub3Rfdm",  # truncado
    ],
    ids=[
        "invalid_b64_chars",
        "valid_b64_bad_json",
        "missing_id_field",
        "missing_p_field",
        "invalid_date",
        "empty_id",
        "empty_string",
        "truncated",
    ],
)
def test_invalid_cursor_raises(bad_cursor: str) -> None:
    with pytest.raises(InvalidCursor):
        decode_cursor(bad_cursor)
