"""Router de healthcheck (CA-F006-01 / T-S3-05).

Liveness puro: responde 200 {"status": "ok"} se o processo está de pé.
Sem auth, sem Idempotency-Key, sem checar dependências (readiness é dívida do resto de F006).
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from blog.interfaces.schemas import HealthResponse

router = APIRouter(prefix="/v1", tags=["health"])


@router.get("/health", status_code=200, response_model=HealthResponse)
async def health() -> JSONResponse:
    """Liveness público (CA-F006-01). Sem auth, sem Idempotency-Key, sem checar deps."""
    return JSONResponse(status_code=200, content={"status": "ok"})
