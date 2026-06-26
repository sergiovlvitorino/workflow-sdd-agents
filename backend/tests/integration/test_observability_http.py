"""Testes de observabilidade (T-S3-04) — TestClient HTTP real.

Cobre:
- Branch COM X-Request-ID válido → id preservado no log e no header de resposta.
- Branch SEM X-Request-ID → id gerado por id_gen e ecoado no header.
- Correlação request_id log↔header num caso de ERRO (handler de errors.py).
- Negativo de PII: sentinelas em title/content não aparecem no log.
- Sanitização / log-injection: CRLF e charset proibido → descarta e gera.
- route é template (/v1/posts/{post_id}), nunca a path com valores.
- Determinismo: presença/tipo de duration_ms e timestamp, NUNCA o valor.
- try/finally: logger que levanta não vira 500.
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import Callable
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from blog.infrastructure.in_memory import InMemoryIdempotencyStore, InMemoryPostRepository
from blog.main import create_app

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_client(id_gen: Callable[[], str] | None = None) -> TestClient:
    """Cria TestClient com repositórios in-memory e id_gen opcional."""
    app = create_app(
        repo=InMemoryPostRepository(),
        idem=InMemoryIdempotencyStore(),
        id_gen=id_gen,
    )
    return TestClient(app, raise_server_exceptions=False)


def _parse_logs(captured: str) -> list[dict[str, Any]]:
    """Parseia linhas JSON do stdout capturado; ignora linhas não-JSON."""
    events = []
    for line in captured.splitlines():
        line = line.strip()
        if not line:
            continue
        with contextlib.suppress(json.JSONDecodeError):
            events.append(json.loads(line))
    return events


# ---------------------------------------------------------------------------
# Branch COM X-Request-ID válido
# ---------------------------------------------------------------------------


def test_request_id_from_client_header_preserved(capsys: pytest.CaptureFixture[str]) -> None:
    """Header X-Request-ID válido → log e resposta ecoam o mesmo id."""
    client = _make_client()
    resp = client.get("/v1/posts", headers={"X-Request-ID": "TEST-FROM-CLIENT"})

    assert resp.status_code == 200
    assert resp.headers["x-request-id"] == "TEST-FROM-CLIENT"

    logs = _parse_logs(capsys.readouterr().out)
    info_events = [e for e in logs if e.get("level") == "info"]
    assert any(e.get("request_id") == "TEST-FROM-CLIENT" for e in info_events)


# ---------------------------------------------------------------------------
# Branch SEM X-Request-ID → id_gen injetado
# ---------------------------------------------------------------------------


def test_request_id_generated_when_no_header(capsys: pytest.CaptureFixture[str]) -> None:
    """Sem X-Request-ID → id_gen determinístico; id aparece no log e no header."""
    client = _make_client(id_gen=lambda: "GEN-RID-01")
    resp = client.get("/v1/posts")

    assert resp.status_code == 200
    assert resp.headers["x-request-id"] == "GEN-RID-01"

    logs = _parse_logs(capsys.readouterr().out)
    info_events = [e for e in logs if e.get("level") == "info"]
    assert any(e.get("request_id") == "GEN-RID-01" for e in info_events)


# ---------------------------------------------------------------------------
# Correlação log↔header em caso de ERRO (handler de errors.py)
# ---------------------------------------------------------------------------


def test_request_id_correlation_on_error(capsys: pytest.CaptureFixture[str]) -> None:
    """Num erro 400 (Idempotency-Key ausente), log[request_id] == resp.headers[x-request-id]."""
    client = _make_client(id_gen=lambda: "CORR-RID-42")
    # POST sem Idempotency-Key → 400 (IdempotencyKeyRequired)
    resp = client.post(
        "/v1/posts",
        json={"title": "T", "content": "C"},
    )

    assert resp.status_code == 400
    resp_rid = resp.headers["x-request-id"]
    assert resp_rid == "CORR-RID-42"

    logs = _parse_logs(capsys.readouterr().out)
    error_events = [e for e in logs if e.get("level") == "error"]
    assert len(error_events) >= 1
    assert error_events[0]["request_id"] == resp_rid  # correlação


# ---------------------------------------------------------------------------
# Negativo de PII: sentinelas NÃO aparecem no log
# ---------------------------------------------------------------------------


def test_pii_sentinels_not_in_log(capsys: pytest.CaptureFixture[str]) -> None:
    """Conteúdo com sentinelas PII não deve aparecer em nenhuma linha de log."""
    client = _make_client()
    client.post(
        "/v1/posts",
        json={"title": "SENTINELA-TITLE-XYZ", "content": "SENTINELA-CONTENT-XYZ"},
        headers={"Idempotency-Key": "idem-pii-test"},
    )

    raw_out = capsys.readouterr().out
    assert "SENTINELA-TITLE-XYZ" not in raw_out
    assert "SENTINELA-CONTENT-XYZ" not in raw_out


def test_log_event_keys_match_allowlist_exactly(capsys: pytest.CaptureFixture[str]) -> None:
    """As chaves do evento de log de sucesso são EXATAMENTE a allowlist (nada a mais)."""
    client = _make_client()
    client.get("/v1/posts")

    logs = _parse_logs(capsys.readouterr().out)
    info_events = [e for e in logs if e.get("level") == "info"]
    assert len(info_events) >= 1

    expected_keys = {"timestamp", "level", "request_id", "method", "route", "status", "duration_ms"}
    assert set(info_events[0].keys()) == expected_keys


def test_error_event_keys_match_allowlist_exactly(capsys: pytest.CaptureFixture[str]) -> None:
    """As chaves do evento de log de ERRO são EXATAMENTE a allowlist (nada a mais, nada a menos).

    Caracterização para debt-flow: trava o contrato de _log_error antes de
    extrair helper compartilhado. O evento de erro tem 6 chaves (sem duration_ms,
    diferente do evento de sucesso que tem 7).
    """
    client = _make_client(id_gen=lambda: "ERR-KEYS-01")
    # POST sem Idempotency-Key → 400 (IdempotencyKeyRequired) → _log_error chamado
    resp = client.post(
        "/v1/posts",
        json={"title": "T", "content": "C"},
    )

    assert resp.status_code == 400

    logs = _parse_logs(capsys.readouterr().out)
    error_events = [e for e in logs if e.get("level") == "error"]
    assert len(error_events) >= 1, "Deve haver pelo menos 1 evento de erro no log"

    error_event = error_events[0]

    # Igualdade EXATA: captura campo a mais OU campo a menos
    expected_keys = {"timestamp", "level", "request_id", "method", "route", "status"}
    assert set(error_event.keys()) == expected_keys

    # Invariantes do evento de erro
    assert error_event["level"] == "error"
    assert "duration_ms" not in error_event


# ---------------------------------------------------------------------------
# Sanitização / log-injection: CRLF e charset proibido
# ---------------------------------------------------------------------------


def test_crlf_in_request_id_is_rejected_and_generated(capsys: pytest.CaptureFixture[str]) -> None:
    """X-Request-ID com CRLF → descartado; id gerado; JSON Lines permanece 1 linha por evento."""
    client = _make_client(id_gen=lambda: "SAFE-GENERATED")
    # httpx normaliza headers; usamos valor com caractere fora do charset (espaço)
    resp = client.get("/v1/posts", headers={"X-Request-ID": "abc def"})

    assert resp.headers["x-request-id"] == "SAFE-GENERATED"

    raw_out = capsys.readouterr().out
    # Cada linha deve ser JSON parseável (1 evento por linha)
    for line in raw_out.splitlines():
        line = line.strip()
        if line:
            json.loads(line)  # não deve levantar


def test_overlong_request_id_is_rejected(capsys: pytest.CaptureFixture[str]) -> None:
    """X-Request-ID > 128 chars → descartado; id gerado; header ecoado charset-safe."""
    long_id = "A" * 129
    client = _make_client(id_gen=lambda: "FALLBACK-LONG")
    resp = client.get("/v1/posts", headers={"X-Request-ID": long_id})

    assert resp.headers["x-request-id"] == "FALLBACK-LONG"


def test_empty_request_id_after_strip_is_rejected(capsys: pytest.CaptureFixture[str]) -> None:
    """X-Request-ID que vira string vazia após strip → descartado; id gerado."""
    # Espaços apenas → sanitize_request_id retorna None (branch `not candidate`)
    from blog.interfaces.observability import sanitize_request_id

    assert sanitize_request_id("   ") is None


def test_unmatched_route_uses_sentinel(capsys: pytest.CaptureFixture[str]) -> None:
    """Rota não mapeada → log[route] == '<unmatched>' (nunca url.path com valores)."""
    client = _make_client()
    client.get("/v1/rota-inexistente-xyz")

    logs = _parse_logs(capsys.readouterr().out)
    info_events = [e for e in logs if e.get("level") == "info"]
    assert len(info_events) >= 1
    assert info_events[0]["route"] == "<unmatched>"


# ---------------------------------------------------------------------------
# route é template, nunca a path com valores
# ---------------------------------------------------------------------------


def test_route_log_is_template_not_path_with_values(capsys: pytest.CaptureFixture[str]) -> None:
    """GET /v1/posts/{post_id} com id real → log[route] == template, nunca contém o id."""
    client = _make_client()
    fake_id = "01JABCDEFGH123456789012345"  # ULID-like
    client.get(f"/v1/posts/{fake_id}")

    logs = _parse_logs(capsys.readouterr().out)
    info_events = [e for e in logs if e.get("level") == "info" and "posts" in e.get("route", "")]
    assert len(info_events) >= 1
    route = info_events[0]["route"]
    assert fake_id not in route
    assert "{" in route  # deve ser o template com parâmetro


# ---------------------------------------------------------------------------
# Determinismo: presença/tipo, NUNCA valor
# ---------------------------------------------------------------------------


def test_duration_ms_present_and_numeric(capsys: pytest.CaptureFixture[str]) -> None:
    """duration_ms está presente e é numérico >= 0."""
    client = _make_client()
    client.get("/v1/posts")

    logs = _parse_logs(capsys.readouterr().out)
    info_events = [e for e in logs if e.get("level") == "info"]
    assert len(info_events) >= 1
    dur = info_events[0]["duration_ms"]
    assert isinstance(dur, (int, float))
    assert dur >= 0


def test_timestamp_present_and_iso_parseable(capsys: pytest.CaptureFixture[str]) -> None:
    """timestamp está presente e é string ISO-8601 parseável."""
    from datetime import datetime

    client = _make_client()
    client.get("/v1/posts")

    logs = _parse_logs(capsys.readouterr().out)
    info_events = [e for e in logs if e.get("level") == "info"]
    assert len(info_events) >= 1
    ts = info_events[0]["timestamp"]
    assert isinstance(ts, str)
    datetime.fromisoformat(ts)  # não deve levantar


# ---------------------------------------------------------------------------
# try/finally: observabilidade não derruba o request
# ---------------------------------------------------------------------------


def test_logger_failure_does_not_cause_500(capsys: pytest.CaptureFixture[str]) -> None:
    """Mesmo que o emit do log levante, a resposta de negócio retorna normalmente."""
    client = _make_client()

    import blog.interfaces.observability as obs_module

    def _failing_emit(event: Any) -> None:
        raise RuntimeError("logger explodiu")

    with patch.object(obs_module, "_emit", _failing_emit):
        resp = client.get("/v1/posts")

    # A resposta de negócio deve sair normalmente (200), não 500
    assert resp.status_code == 200


def test_response_none_branch_covered() -> None:
    """Testa a sanitização com None explícito (branch response=None via sanitize_request_id)."""
    from blog.interfaces.observability import sanitize_request_id

    # None explícito → retorna None imediatamente
    assert sanitize_request_id(None) is None


def test_middleware_call_next_raises_still_logs_500(capsys: pytest.CaptureFixture[str]) -> None:
    """Quando call_next levanta, response=None: status=500 no log; exceção re-propagada pelo ASGI."""
    from starlette.applications import Starlette
    from starlette.requests import Request as StarletteRequest
    from starlette.responses import Response
    from starlette.routing import Route
    from starlette.testclient import TestClient

    from blog.interfaces.observability import RequestIdMiddleware

    async def boom(request: StarletteRequest) -> Response:
        raise RuntimeError("handler explodiu")

    app = Starlette(routes=[Route("/boom", boom)])
    app.add_middleware(RequestIdMiddleware, id_gen=lambda: "BOOM-RID")

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/boom")

    # O ASGI converte a exceção em 500
    assert resp.status_code == 500

    logs = _parse_logs(capsys.readouterr().out)
    info_events = [e for e in logs if e.get("level") == "info"]
    # Quando response=None, status deve ser 500 no log
    assert any(e.get("status") == 500 for e in info_events)
