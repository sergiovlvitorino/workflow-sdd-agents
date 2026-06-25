"""Middleware ASGI único de observabilidade (ADR-0006 §8 / T-S3-04).

Responsabilidades:
- Gerar/sanitizar X-Request-ID por requisição (input externo → sanitização por rejeição total).
- Propagar request_id via request.state.request_id + ContextVar de fallback.
- Emitir log JSON Lines em stdout com allowlist de campos (anti-PII).
- Ecoar request_id no header de resposta X-Request-ID.
- try/finally: observabilidade nunca causa 500 (único except Exception: pass justificado).
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Callable
from contextvars import ContextVar
from datetime import datetime, timezone
from time import perf_counter
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

# ---------------------------------------------------------------------------
# ContextVar de fallback — permite propagar o request_id fora do ciclo HTTP
# ---------------------------------------------------------------------------
_request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")

# ---------------------------------------------------------------------------
# Sanitização de X-Request-ID (charset allowlist + tamanho máximo)
# ---------------------------------------------------------------------------
_RID_CHARSET = re.compile(r"[^A-Za-z0-9._-]")
_RID_MAXLEN = 128


def sanitize_request_id(raw: str | None) -> str | None:
    """Sanitiza X-Request-ID de entrada por rejeição total.

    Retorna None se o valor for inservível (charset proibido, excede limite,
    vazio). Rejeição total evita id ambíguo/colidente e fecha log-injection (CRLF).
    """
    if raw is None:
        return None
    candidate = raw.strip()
    if not candidate:
        return None
    if len(candidate) > _RID_MAXLEN:
        return None
    if _RID_CHARSET.search(candidate):
        return None
    return candidate


def _emit(event: dict[str, Any]) -> None:
    """Emite um evento JSON Lines em stdout (1 linha, flush imediato)."""
    print(json.dumps(event, separators=(",", ":")), flush=True, file=sys.stdout)


def emit_event(
    *,
    timestamp: str,
    level: str,
    request_id: str,
    method: str,
    route: str,
    status: int,
    duration_ms: float | None = None,
) -> None:
    """Monta e emite um evento de log estruturado com allowlist de campos.

    A ordem das chaves é FIXA (timestamp, level, request_id, method, route, status)
    e duration_ms é adicionado ao FINAL somente se fornecido (evento de sucesso).
    Evento de erro omite duration_ms passando o argumento como None (default).
    """
    event: dict[str, Any] = {
        "timestamp": timestamp,
        "level": level,
        "request_id": request_id,
        "method": method,
        "route": route,
        "status": status,
    }
    if duration_ms is not None:
        event["duration_ms"] = duration_ms
    _emit(event)


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _route_template(request: Request) -> str:
    """Retorna o template da rota (ex: /v1/posts/{post_id}), nunca a path com valores."""
    route = request.scope.get("route")
    if route is not None and hasattr(route, "path"):
        return str(route.path)
    return "<unmatched>"


def _ms(start: float) -> float:
    return round((perf_counter() - start) * 1000, 3)


# ---------------------------------------------------------------------------
# Middleware ASGI único
# ---------------------------------------------------------------------------
class RequestIdMiddleware(BaseHTTPMiddleware):
    """Middleware ASGI único de observabilidade (ADR-0006 §8).

    Parâmetros:
        app: aplicação ASGI subjacente.
        id_gen: callable que gera um novo ID (injetável nos testes).
        clock: callable que retorna ISO-8601 UTC (injetável nos testes).
    """

    def __init__(
        self,
        app: ASGIApp,
        id_gen: Callable[[], str],
        clock: Callable[[], str] = _utc_now,
    ) -> None:
        super().__init__(app)
        self._id_gen = id_gen
        self._clock = clock

    async def dispatch(self, request: Request, call_next: Callable[..., Any]) -> Response:
        rid = sanitize_request_id(request.headers.get("x-request-id")) or self._id_gen()
        request.state.request_id = rid
        token = _request_id_ctx.set(rid)

        start = perf_counter()
        response: Response | None = None
        try:
            response = await call_next(request)
            return response
        finally:
            try:
                status = response.status_code if response is not None else 500
                emit_event(
                    timestamp=self._clock(),
                    level="info",
                    request_id=rid,
                    method=request.method,
                    route=_route_template(request),
                    status=status,
                    duration_ms=_ms(start),
                )
                if response is not None:
                    response.headers["X-Request-ID"] = rid
            except Exception:  # noqa: BLE001 — observabilidade não pode derrubar request
                pass  # nunca propaga; log/duração best-effort
            finally:
                _request_id_ctx.reset(token)


def install_observability(
    app: Any,
    id_gen: Callable[[], str],
    clock: Callable[[], str] = _utc_now,
) -> None:
    """Registra o middleware único de observabilidade na app FastAPI."""
    app.add_middleware(RequestIdMiddleware, id_gen=id_gen, clock=clock)


def request_id_of(request: Request) -> str:
    """Helper compartilhado: lê request_id do state ou ContextVar de fallback."""
    return getattr(request.state, "request_id", None) or _request_id_ctx.get("")
