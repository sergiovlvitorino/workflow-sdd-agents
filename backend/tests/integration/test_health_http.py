"""Testes do endpoint de healthcheck (T-S3-05 / CA-F006-01) — TestClient HTTP real.

Cobre:
- GET /v1/health → 200 com corpo exato {"status": "ok"}.
- Rota pública: sem Idempotency-Key, sem Authorization.
- POST /v1/health → 405 (método não permitido).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from blog.infrastructure.in_memory import InMemoryIdempotencyStore, InMemoryPostRepository
from blog.main import create_app


@pytest.fixture()
def client() -> TestClient:
    app = create_app(
        repo=InMemoryPostRepository(),
        idem=InMemoryIdempotencyStore(),
    )
    return TestClient(app, raise_server_exceptions=False)


def test_health_returns_200_ok(client: TestClient) -> None:
    """CA-F006-01: GET /v1/health → 200 com corpo exato."""
    resp = client.get("/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_health_public_no_auth_no_idempotency_key(client: TestClient) -> None:
    """Rota pública: responde 200 sem Idempotency-Key nem Authorization."""
    resp = client.get("/v1/health")
    assert resp.status_code == 200


def test_health_method_not_allowed(client: TestClient) -> None:
    """POST /v1/health → 405 (apenas GET exposto)."""
    resp = client.post("/v1/health")
    assert resp.status_code == 405
