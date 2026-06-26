#!/usr/bin/env python3
"""Dump de fixtures reais do backend para contract tests do frontend.

Roda o backend via TestClient (sem servidor HTTP real) e grava as respostas
reais de cada endpoint num JSON determinístico.

Uso:
    python backend/scripts/dump_contract_fixtures.py [output_path]

Output padrão: frontend/src/app/api/fixtures/contract-fixtures.json

As fixtures são usadas pelo contract.spec.ts do frontend para validar
payload real do backend contra os tipos TypeScript gerados e o schema OpenAPI.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path

# Garante que o src do backend está no path
src = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src))

from fastapi.testclient import TestClient  # noqa: E402, I001
from blog.main import create_app  # noqa: E402, I001

# Força stdout UTF-8 no Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", newline="\n")


def main(output_path: str | None = None) -> None:
    # Banco efêmero e isolado: cada execução começa limpa, nunca toca blog.db.
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_db:
        tmp_db_path = tmp_db.name
    _prev_db_path = os.environ.get("BLOG_DB_PATH")
    os.environ["BLOG_DB_PATH"] = tmp_db_path
    try:
        app = create_app()

        # TestClient via Starlette/FastAPI (sem servidor HTTP real)
        with TestClient(app, raise_server_exceptions=False) as client:
            fixtures: dict[str, object] = {}

            # --- POST /v1/posts → 201 ---
            idem_key = "fixture-key-create-001"
            create_resp = client.post(
                "/v1/posts",
                json={"title": "Post de Fixture", "content": "Conteúdo da fixture de contrato."},
                headers={"Idempotency-Key": idem_key, "Content-Type": "application/json"},
            )
            assert create_resp.status_code == 201, f"Expected 201, got {create_resp.status_code}: {create_resp.text}"
            post_created = create_resp.json()
            post_id = post_created["id"]
            fixtures["post_created_201"] = post_created

            # --- POST /v1/posts replay → 200 + Idempotent-Replayed ---
            replay_resp = client.post(
                "/v1/posts",
                json={"title": "Post de Fixture", "content": "Conteúdo da fixture de contrato."},
                headers={"Idempotency-Key": idem_key, "Content-Type": "application/json"},
            )
            assert replay_resp.status_code == 200, f"Expected 200 (replay), got {replay_resp.status_code}"
            assert replay_resp.headers.get("Idempotent-Replayed") == "true"
            fixtures["post_replay_200"] = replay_resp.json()

            # --- PUT /v1/posts/{id}/publish → 200 ---
            publish_resp = client.put(
                f"/v1/posts/{post_id}/publish",
                headers={"Idempotency-Key": "fixture-key-publish-001", "Content-Type": "application/json"},
            )
            assert publish_resp.status_code == 200, (
                f"Expected 200 (publish), got {publish_resp.status_code}: {publish_resp.text}"
            )
            post_published = publish_resp.json()
            fixtures["post_published_200"] = post_published

            # --- GET /v1/posts/{id} → 200 (post publicado) ---
            get_resp = client.get(f"/v1/posts/{post_id}")
            assert get_resp.status_code == 200, f"Expected 200, got {get_resp.status_code}"
            fixtures["post_get_200"] = get_resp.json()

            # --- GET /v1/posts → 200 (página com 1 item) ---
            list_resp = client.get("/v1/posts", params={"limit": 10})
            assert list_resp.status_code == 200, f"Expected 200 (list), got {list_resp.status_code}"
            fixtures["posts_list_200"] = list_resp.json()

            # --- GET /v1/posts/{id} de draft → 404 (ApiError post_not_found) ---
            # Criar um post sem publicar para gerar um draft
            draft_resp = client.post(
                "/v1/posts",
                json={"title": "Draft Fixture", "content": "Conteúdo do draft."},
                headers={"Idempotency-Key": "fixture-key-draft-001", "Content-Type": "application/json"},
            )
            assert draft_resp.status_code == 201
            draft_id = draft_resp.json()["id"]

            get_draft_resp = client.get(f"/v1/posts/{draft_id}")
            assert get_draft_resp.status_code == 404, f"Expected 404 for draft, got {get_draft_resp.status_code}"
            fixtures["post_not_found_404"] = get_draft_resp.json()

            # --- GET /v1/posts/{id} inexistente → 404 ---
            notfound_resp = client.get("/v1/posts/ID-INEXISTENTE-000")
            assert notfound_resp.status_code == 404, f"Expected 404, got {notfound_resp.status_code}"
            fixtures["post_not_found_404_nonexistent"] = notfound_resp.json()

            # --- GET /v1/posts?cursor=invalido → 400 ApiError invalid_cursor ---
            cursor_resp = client.get("/v1/posts", params={"cursor": "cursor-invalido-xxx"})
            assert cursor_resp.status_code == 400, f"Expected 400 (invalid cursor), got {cursor_resp.status_code}"
            fixtures["invalid_cursor_400"] = cursor_resp.json()

            # --- POST /v1/posts sem Idempotency-Key → 400 ApiError idempotency_key_required ---
            no_key_resp = client.post(
                "/v1/posts",
                json={"title": "Sem key", "content": "Conteúdo."},
                headers={"Content-Type": "application/json"},
            )
            assert no_key_resp.status_code == 400, f"Expected 400 (no key), got {no_key_resp.status_code}"
            fixtures["idempotency_key_required_400"] = no_key_resp.json()

            # --- POST /v1/posts conflito → 409 ApiError idempotency_key_conflict ---
            conflict_resp = client.post(
                "/v1/posts",
                json={"title": "Titulo diferente", "content": "Conteudo diferente."},
                headers={"Idempotency-Key": idem_key, "Content-Type": "application/json"},
            )
            assert conflict_resp.status_code == 409, f"Expected 409 (conflict), got {conflict_resp.status_code}"
            fixtures["idempotency_key_conflict_409"] = conflict_resp.json()

            # --- POST /v1/posts payload inválido → 422 ApiError validation_error ---
            invalid_resp = client.post(
                "/v1/posts",
                json={"title": "", "content": "c"},
                headers={"Idempotency-Key": "fixture-key-invalid-001", "Content-Type": "application/json"},
            )
            assert invalid_resp.status_code == 422, f"Expected 422, got {invalid_resp.status_code}"
            fixtures["validation_error_422"] = invalid_resp.json()

            # --- GET /v1/health → 200 HealthResponse ---
            health_resp = client.get("/v1/health")
            assert health_resp.status_code == 200
            fixtures["health_200"] = health_resp.json()

        # Determina o output
        if output_path is None:
            repo_root = Path(__file__).parent.parent.parent
            output_path = str(repo_root / "frontend" / "src" / "app" / "api" / "fixtures" / "contract-fixtures.json")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # sort_keys=True para determinismo (diff legível no PR)
        output = json.dumps(fixtures, indent=2, sort_keys=True, ensure_ascii=False)
        Path(output_path).write_text(output + "\n", encoding="utf-8")

        print(f"[dump_contract_fixtures] Fixtures gravadas em {output_path}")
        print(f"[dump_contract_fixtures] {len(fixtures)} fixtures geradas: {list(fixtures.keys())}")
    finally:
        # Restaura BLOG_DB_PATH para não contaminar o processo caso main()
        # seja chamada múltiplas vezes em-processo (ex.: testes de integração).
        if _prev_db_path is None:
            os.environ.pop("BLOG_DB_PATH", None)
        else:
            os.environ["BLOG_DB_PATH"] = _prev_db_path

        # Remove o banco temporário e os sidecars WAL criados pelo SQLite.
        # No Windows, a conexão pode ainda estar aberta no GC — supprimimos
        # OSError/PermissionError; o OS coletará os arquivos eventualmente.
        for _suffix in ("", "-wal", "-shm"):
            with contextlib.suppress(OSError):
                Path(tmp_db_path + _suffix).unlink(missing_ok=True)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
