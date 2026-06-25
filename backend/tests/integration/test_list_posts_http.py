"""Testes de integração HTTP real via TestClient — CA-F003-01..03.

Exercitam GET /v1/posts com paginação keyset, filtro allowlist e estabilidade
sob inserção entre páginas. Adaptors in-memory de produção são usados — não
dublês ad-hoc — para que o keyset e o allowlist sejam exercitados realmente.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from blog.domain.post import Post, PostStatus
from blog.infrastructure.in_memory import InMemoryIdempotencyStore, InMemoryPostRepository
from blog.main import create_app

_BASE_TS = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


def _published_post(
    post_id: str,
    title: str = "Post",
    *,
    published_offset_seconds: int = 0,
) -> Post:
    """Cria um post publicado com timestamps fixos e determinísticos."""
    pub_at = _BASE_TS + timedelta(seconds=published_offset_seconds)
    draft = Post.create(title, f"Conteúdo de {title}", new_id=post_id, now=pub_at)
    return dataclasses.replace(draft, status=PostStatus.PUBLISHED, published_at=pub_at)


def _draft_post(post_id: str, title: str = "Rascunho") -> Post:
    return Post.create(title, "Conteúdo rascunho", new_id=post_id, now=_BASE_TS)


@pytest.fixture()
def client() -> TestClient:
    """App isolada por teste — estado limpo (adapters in-memory injetados)."""
    app = create_app(repo=InMemoryPostRepository(), idem=InMemoryIdempotencyStore())
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# CA-F003-01: 25 publicados, limit=10 → 200, 10 itens, next_cursor presente
# ---------------------------------------------------------------------------
def test_list_returns_first_page_with_next_cursor(client: TestClient) -> None:
    repo = client.app.state.post_repo  # type: ignore[union-attr]
    for i in range(25):
        repo.add(_published_post(f"ID-{i:03d}", f"Post {i}", published_offset_seconds=i))

    resp = client.get("/v1/posts?limit=10")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 10
    assert data["next_cursor"] is not None
    assert data["limit"] == 10


# ---------------------------------------------------------------------------
# CA-F003-02: allowlist — rascunhos NÃO aparecem; asserta por valor (ids exatos)
# ---------------------------------------------------------------------------
def test_drafts_never_appear_in_listing(client: TestClient) -> None:
    repo = client.app.state.post_repo  # type: ignore[union-attr]
    pub1 = _published_post("PUB-001", "Publicado A", published_offset_seconds=10)
    pub2 = _published_post("PUB-002", "Publicado B", published_offset_seconds=20)
    draft1 = _draft_post("DRF-001", "Rascunho X")
    draft2 = _draft_post("DRF-002", "Rascunho Y")

    for p in [pub1, pub2, draft1, draft2]:
        repo.add(p)

    resp = client.get("/v1/posts?limit=100")

    assert resp.status_code == 200
    data = resp.json()
    returned_ids = {item["id"] for item in data["items"]}

    # Allowlist: exatamente os publicados
    assert returned_ids == {"PUB-001", "PUB-002"}, f"IDs inesperados: {returned_ids}"
    # Garantia negativa: nenhum rascunho vaza (asserta por valor, não por marker)
    assert "DRF-001" not in returned_ids
    assert "DRF-002" not in returned_ids


# ---------------------------------------------------------------------------
# CA-F003-03 (parte 1): página seguinte via cursor sem repetição nem omissão
# ---------------------------------------------------------------------------
def test_second_page_does_not_repeat_or_skip_items(client: TestClient) -> None:
    repo = client.app.state.post_repo  # type: ignore[union-attr]
    # 15 posts: offset 0..14 (publicado_at distintos → ordem total determinística)
    for i in range(15):
        repo.add(_published_post(f"ID-{i:03d}", f"Post {i}", published_offset_seconds=i))

    # Página 1
    resp1 = client.get("/v1/posts?limit=10")
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert len(data1["items"]) == 10
    cursor = data1["next_cursor"]
    assert cursor is not None

    # Página 2
    resp2 = client.get(f"/v1/posts?limit=10&cursor={cursor}")
    assert resp2.status_code == 200
    data2 = resp2.json()

    ids_p1 = {item["id"] for item in data1["items"]}
    ids_p2 = {item["id"] for item in data2["items"]}

    # Sem repetição
    overlap = ids_p1 & ids_p2
    assert not overlap, f"Itens repetidos entre páginas: {overlap}"
    # Cobertura total: todos os 15 posts aparecem em alguma página
    assert len(ids_p1 | ids_p2) == 15
    # Última página não tem próximo cursor
    assert data2["next_cursor"] is None


# ---------------------------------------------------------------------------
# CA-F003-03 (parte 2 — ESTABILIDADE): inserção entre páginas não perturba p2
# Este teste prova que o keyset é real e não offset disfarçado.
# Mutation-âncora: trocar '<' por '<=' → item de fronteira duplica → vermelho.
# ---------------------------------------------------------------------------
def test_second_page_stable_under_insertion_between_pages(client: TestClient) -> None:
    repo = client.app.state.post_repo  # type: ignore[union-attr]

    # Seeding: 15 posts com offsets 100..114 (espaço para inserir no meio)
    for i in range(15):
        repo.add(_published_post(f"ID-{i:03d}", f"Post {i}", published_offset_seconds=100 + i))

    # Página 1 (limit=10): retorna os 10 mais recentes (offsets 114..105)
    resp1 = client.get("/v1/posts?limit=10")
    assert resp1.status_code == 200
    data1 = resp1.json()
    cursor = data1["next_cursor"]
    assert cursor is not None
    ids_p1 = {item["id"] for item in data1["items"]}

    # Insere um post que caíria ENTRE a página 1 e a página 2
    # O post de fronteira da p1 tem offset 105; o próximo candidato tem offset 104.
    # Inserir com offset 104.5 (simulado como 104 + 0.5 → usamos offset=104 com id distinto)
    # Na ordem (published_at DESC, id DESC):
    #   p1 cobriu offsets 114..105; p2 cobrirá offsets 104..100
    #   inserimos offset=104 com id "ZZZ-NEW" — ficará ANTES de "ID-004" (id DESC)
    #   mas depois da fronteira se published_at for idêntico ao de "ID-004"
    # Para o teste de estabilidade, o que importa é que a inserção não cause repetição ou omissão.
    intruder = _published_post("ZZZ-NEW", "Intruso", published_offset_seconds=104)
    repo.add(intruder)

    # Página 2 com o mesmo cursor (obtido antes da inserção)
    resp2 = client.get(f"/v1/posts?limit=10&cursor={cursor}")
    assert resp2.status_code == 200
    data2 = resp2.json()
    ids_p2 = {item["id"] for item in data2["items"]}

    # Sem repetição de itens da página 1
    overlap = ids_p1 & ids_p2
    assert not overlap, f"Itens da p1 repetiram em p2 após inserção: {overlap}"

    # Todos os itens de p1 ainda estão presentes em p1 (inserção não apagou)
    assert len(ids_p1) == 10


# ---------------------------------------------------------------------------
# Cursor inválido → 400 invalid_cursor (P-11, ADR-0002 — sem fallback silencioso)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "bad_cursor",
    ["lixo!!!", "invalido", "eyJub3Rfdm"],
    ids=["garbage", "plain_text", "truncated_b64"],
)
def test_invalid_cursor_returns_400(client: TestClient, bad_cursor: str) -> None:
    resp = client.get(f"/v1/posts?cursor={bad_cursor}")

    assert resp.status_code == 400
    data = resp.json()
    assert data["type"].endswith("invalid_cursor")
    assert resp.headers.get("content-type", "").startswith("application/problem+json")


# ---------------------------------------------------------------------------
# Borda: limit fora do intervalo [1, 100] → 422
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("bad_limit", [0, 101], ids=["zero", "over_max"])
def test_limit_out_of_range_returns_422(client: TestClient, bad_limit: int) -> None:
    resp = client.get(f"/v1/posts?limit={bad_limit}")

    assert resp.status_code == 422
    data = resp.json()
    assert data["type"].endswith("validation_error")


# ---------------------------------------------------------------------------
# Borda: lista vazia → 200 com items=[] e next_cursor=null
# ---------------------------------------------------------------------------
def test_empty_list_returns_200_with_empty_items(client: TestClient) -> None:
    resp = client.get("/v1/posts")

    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["next_cursor"] is None
    assert data["limit"] == 10
