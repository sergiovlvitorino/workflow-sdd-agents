"""Contract test: verifica que o OpenAPI gerado pelo FastAPI está alinhado com 005-api-contract.md.

Pino 005 → OpenAPI: enum status, published_at nullable, campos obrigatórios,
catálogo de erros. Complementa o gate de drift do frontend (ADR-0005 §8).

Este teste é distinto do gate de drift do frontend:
- Gate de drift (frontend): verifica que os TIPOS TS estão sincronizados com o OpenAPI atual.
- Este teste (backend): verifica que o OpenAPI atual está alinhado com a SPEC 005.

Se o Pydantic divergir do 005, este teste fica vermelho ANTES do frontend.
"""
from __future__ import annotations

import pytest
from blog.main import create_app


@pytest.fixture(scope="module")
def openapi_schema() -> dict:
    """Schema OpenAPI gerado pelo FastAPI (derivado dos schemas Pydantic)."""
    app = create_app()
    return app.openapi()


@pytest.fixture(scope="module")
def schemas(openapi_schema: dict) -> dict:
    return openapi_schema["components"]["schemas"]


class TestPostResponseSchema:
    """PostResponse deve estar alinhado com 005-api-contract.md §3."""

    def test_post_response_existe(self, schemas: dict) -> None:
        assert "PostResponse" in schemas, "PostResponse ausente dos schemas OpenAPI"

    def test_campos_obrigatorios(self, schemas: dict) -> None:
        required = schemas["PostResponse"].get("required", [])
        # 005 §3: id, title, content, status, created_at são obrigatórios
        for campo in ["id", "title", "content", "status", "created_at"]:
            assert campo in required, f"Campo '{campo}' não está em required do PostResponse"

    def test_status_e_enum_draft_published(self, schemas: dict) -> None:
        """005 §3: status é enum "draft" | "published" — nunca string genérica."""
        props = schemas["PostResponse"]["properties"]
        assert "status" in props
        status_prop = props["status"]
        enum_values = status_prop.get("enum", [])
        assert "draft" in enum_values, "status não contém 'draft'"
        assert "published" in enum_values, "status não contém 'published'"

    def test_published_at_e_nullable(self, schemas: dict) -> None:
        """005 §3: published_at é string | null (nullable) — null enquanto draft."""
        props = schemas["PostResponse"]["properties"]
        assert "published_at" in props
        published_at = props["published_at"]
        # anyOf com string e null, ou type com null
        any_of = published_at.get("anyOf", [])
        types_in_any_of = [item.get("type") for item in any_of]
        assert "null" in types_in_any_of, "published_at não é nullable no schema OpenAPI"
        assert "string" in types_in_any_of, "published_at não tem type string no schema OpenAPI"

    def test_published_at_nao_e_obrigatorio(self, schemas: dict) -> None:
        """published_at não está em required (é opcional/nullable)."""
        required = schemas["PostResponse"].get("required", [])
        assert "published_at" not in required, "published_at não deveria ser required (é nullable)"


class TestPageResponseSchema:
    """PageResponse deve estar alinhado com 005-api-contract.md §3."""

    def test_page_response_existe(self, schemas: dict) -> None:
        assert "PageResponse" in schemas

    def test_campos_obrigatorios(self, schemas: dict) -> None:
        required = schemas["PageResponse"].get("required", [])
        for campo in ["items", "next_cursor", "limit"]:
            assert campo in required, f"Campo '{campo}' não está em required do PageResponse"

    def test_next_cursor_nullable(self, schemas: dict) -> None:
        """005 §3: next_cursor é string | null."""
        props = schemas["PageResponse"]["properties"]
        next_cursor = props["next_cursor"]
        any_of = next_cursor.get("anyOf", [])
        types = [item.get("type") for item in any_of]
        assert "null" in types, "next_cursor não é nullable"
        assert "string" in types, "next_cursor não tem type string"


class TestApiErrorSchema:
    """ApiError deve estar alinhado com 005-api-contract.md §4 (RFC 9457)."""

    def test_api_error_existe(self, schemas: dict) -> None:
        assert "ApiError" in schemas

    def test_campos_obrigatorios(self, schemas: dict) -> None:
        required = schemas["ApiError"].get("required", [])
        for campo in ["type", "title", "status"]:
            assert campo in required, f"Campo '{campo}' não está em required do ApiError"

    def test_detail_e_opcional(self, schemas: dict) -> None:
        """005 §4: detail é texto livre e opcional."""
        required = schemas["ApiError"].get("required", [])
        assert "detail" not in required, "detail não deveria ser required em ApiError"


class TestEndpointsPresentes:
    """Verifica que todos os endpoints de 005-api-contract.md estão no OpenAPI."""

    def test_post_posts(self, openapi_schema: dict) -> None:
        assert "/v1/posts" in openapi_schema["paths"]
        assert "post" in openapi_schema["paths"]["/v1/posts"]

    def test_get_posts(self, openapi_schema: dict) -> None:
        assert "get" in openapi_schema["paths"]["/v1/posts"]

    def test_put_publish(self, openapi_schema: dict) -> None:
        assert "/v1/posts/{post_id}/publish" in openapi_schema["paths"]
        assert "put" in openapi_schema["paths"]["/v1/posts/{post_id}/publish"]

    def test_get_post_by_id(self, openapi_schema: dict) -> None:
        assert "/v1/posts/{post_id}" in openapi_schema["paths"]
        assert "get" in openapi_schema["paths"]["/v1/posts/{post_id}"]

    def test_get_health(self, openapi_schema: dict) -> None:
        assert "/v1/health" in openapi_schema["paths"]
        assert "get" in openapi_schema["paths"]["/v1/health"]

    def test_versao_api(self, openapi_schema: dict) -> None:
        """O info.version deve estar alinhado com 005-api-contract.md v1.1.0."""
        assert openapi_schema["info"]["version"] == "1.1.0", (
            f"Versão da API {openapi_schema['info']['version']} difere de 005 v1.1.0"
        )
