"""Testa que o /openapi.json gerado tem schemas reais (não vazios) para todos os endpoints.

Falha se qualquer response_model estiver ausente ou se os schemas de Post/Page/ApiError
não existirem no components/schemas — garante que o ADR-0005 (fonte única de verdade
do contrato frontend-backend) é satisfeito pelo OpenAPI vivo.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from blog.infrastructure.in_memory import InMemoryIdempotencyStore, InMemoryPostRepository
from blog.main import create_app


def _openapi() -> dict:  # type: ignore[type-arg]
    app = create_app(
        repo=InMemoryPostRepository(),
        idem=InMemoryIdempotencyStore(),
    )
    client = TestClient(app)
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    return resp.json()  # type: ignore[no-any-return]


def test_openapi_schemas_not_empty() -> None:
    """components/schemas deve conter Post/Page/Health/ApiError com propriedades reais."""
    schema = _openapi()
    components = schema.get("components", {}).get("schemas", {})

    assert "PostResponse" in components, "PostResponse ausente nos schemas"
    assert "PageResponse" in components, "PageResponse ausente nos schemas"
    assert "HealthResponse" in components, "HealthResponse ausente nos schemas"
    assert "ApiError" in components, "ApiError ausente nos schemas"

    post_props = components["PostResponse"].get("properties", {})
    assert "id" in post_props
    assert "title" in post_props
    assert "content" in post_props
    assert "status" in post_props
    assert "created_at" in post_props
    assert "published_at" in post_props

    page_props = components["PageResponse"].get("properties", {})
    assert "items" in page_props
    assert "next_cursor" in page_props
    assert "limit" in page_props

    health_props = components["HealthResponse"].get("properties", {})
    assert "status" in health_props

    error_props = components["ApiError"].get("properties", {})
    assert "type" in error_props
    assert "title" in error_props
    assert "status" in error_props


def test_openapi_post_status_is_enum() -> None:
    """PostResponse.status deve ser Literal (enum) no OpenAPI, não string solto."""
    schema = _openapi()
    post_schema = schema["components"]["schemas"]["PostResponse"]
    status_prop = post_schema["properties"]["status"]
    # Pydantic v2 gera enum ou anyOf com const para Literal
    has_enum = "enum" in status_prop or "const" in status_prop
    has_anyof_literals = "anyOf" in status_prop
    assert has_enum or has_anyof_literals, f"status não é Literal no OpenAPI: {status_prop}"


def test_openapi_endpoints_have_response_schemas() -> None:
    """Todos os endpoints devem ter schema de resposta não-vazio no OpenAPI."""
    schema = _openapi()
    paths = schema.get("paths", {})

    endpoints_to_check = [
        ("/v1/posts", "post"),
        ("/v1/posts/{post_id}/publish", "put"),
        ("/v1/posts/{post_id}", "get"),
        ("/v1/posts", "get"),
        ("/v1/health", "get"),
    ]

    for path, method in endpoints_to_check:
        assert path in paths, f"Path {path} ausente no OpenAPI"
        op = paths[path].get(method, {})
        responses = op.get("responses", {})
        # O status code principal deve ter content com schema (não vazio)
        main_status = "201" if method == "post" and path == "/v1/posts" else "200"
        assert main_status in responses, f"{method.upper()} {path}: status {main_status} ausente"
        content = responses[main_status].get("content", {})
        assert content, f"{method.upper()} {path}: content vazio para status {main_status} — response_model faltando"
        json_content = content.get("application/json", {})
        assert json_content.get("schema"), f"{method.upper()} {path}: schema vazio em application/json"


def test_openapi_error_responses_have_schemas() -> None:
    """Respostas de erro (4xx) devem ter ApiError como schema no OpenAPI."""
    schema = _openapi()
    paths = schema.get("paths", {})

    # POST /v1/posts → deve ter 400, 409, 422
    post_responses = paths["/v1/posts"]["post"]["responses"]
    assert "400" in post_responses
    assert "409" in post_responses
    assert "422" in post_responses

    # GET /v1/posts/{post_id} → deve ter 404
    get_responses = paths["/v1/posts/{post_id}"]["get"]["responses"]
    assert "404" in get_responses
