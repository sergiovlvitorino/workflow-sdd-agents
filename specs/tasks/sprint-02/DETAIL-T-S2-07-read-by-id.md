# DETAIL — T-S2-07 — F004 interface + aplicação: `GET /v1/posts/{id}` (read-by-id com allowlist)

**Sprint:** 2
**Tamanho:** S _(estimativa)_
**Papel:** BE (+ TL revisão)
**Depende de:** T-S2-04 (`get(id)` na porta), T-S2-06 (`PostNotFound` + `handle_post_not_found` já registrados)
**Bloqueia:** —

> Produzido por um `tl-*` no `sprint-flow` (detalhamento técnico); consumido pelo `review-loop` (implementação + revisão). Descreve a tarefa no **presente** — o status real vive no índice/board, não aqui (ver `docs/lessons/process.md`).

---

## 1. Objetivo

Permitir ler um post por id via `GET /v1/posts/{id}`, devolvendo `200` apenas para posts **publicados** e `404` **indistinguível** para rascunho ou inexistente — fechando o vazamento de autorização que F004 poderia reintroduzir (allowlist de leitura, P-04 / ADR-0004 §8).

## 2. CAs / RNs cobertos

- **CA-F004-01 (RF-011):** post existe **e** publicado → `200` com `Post`.
- **CA-F004-02 (RF-011):** post em `draft` **ou** inexistente → `404 post_not_found`, **mesma resposta nos dois casos** (não revela existência).
- **ADR-0004 §8 (vinculante) — esta tarefa materializa:**
  - **Read-by-id coerente com a allowlist:** rascunho **não vaza** — responde `404` como se não existisse (P-04).
  - **Catálogo de erros:** reusa o **mesmo** `404 post_not_found` (mesmo `type`/`title`/`detail`) — diferenciar (ex.: `403` para rascunho) é proibido.

## 3. Arquivos a criar/alterar

| Path | Ação | Descrição |
|---|---|---|
| `src/blog/application/get_post.py` | criar | Caso de uso `GetPublishedPost` (allowlist por status; `None`/draft → `PostNotFound`). |
| `src/blog/interfaces/posts_router.py` | alterar | Adicionar `GET /{id}` (rota leitura, pública). |
| `src/blog/main.py` | alterar | Registrar `GetPublishedPost` em `app.state`. _(handler `post_not_found` já vem de T-S2-06.)_ |
| `tests/unit/test_get_post_usecase.py` | criar | Unit do caso de uso (publicado→ok; draft→not-found; ausente→not-found). |
| `tests/integration/test_read_by_id_http.py` | criar | Integração HTTP (CA-F004-01/02 + indistinguibilidade). |

## 4. Design da solução

### 4.1 Caso de uso — allowlist por status (P-04)

```text
# application/get_post.py
from blog.application.publish_post import PostNotFound   # REUSA a mesma exceção

class GetPublishedPost:
    def __init__(self, repo: PostRepository) -> None:
        self._repo = repo

    def execute(self, post_id: str) -> dict[str, Any]:
        post = self._repo.get(post_id)
        # ALLOWLIST (P-04): só PUBLISHED é visível. draft E ausente → MESMO caminho.
        if post is None or post.status is not PostStatus.PUBLISHED:
            raise PostNotFound()
        return _to_response_dict(post)
```

Decisão-chave (ADR-0004 §8): a guarda é **allowlist** (`status is not PUBLISHED → 404`), não denylist/marker. `None` (inexistente) e `draft` colapsam no **mesmo** `raise PostNotFound()` → resposta indistinguível **por construção**, não por coincidência de mensagem. Espelha a allowlist do `list_published` (ver `in_memory.py`, lição `docs/lessons/qa.md`: allowlist, não marker).

**Reuso de `PostNotFound`:** a mesma exceção de T-S2-05/06 → o **mesmo** `handle_post_not_found` → o **mesmo** corpo RFC 9457. Garante que o `404` de publicar-inexistente e o `404` de ler-rascunho/inexistente são byte-a-byte iguais (requisito §2.4 do `005`).

### 4.2 Rota (router)

```text
@router.get("/{post_id}", status_code=200)
async def get_post(request: Request, post_id: str) -> JSONResponse:
    """Lê post publicado por id (CA-F004-01/02). Rascunho/inexistente → 404 (P-04)."""
    use_case = request.app.state.get_post_use_case
    response_dict = use_case.execute(post_id)       # PostNotFound → handler → 404
    return JSONResponse(status_code=200, content=response_dict)
```

- **Rota pública** (sem `Idempotency-Key` — é leitura, sem efeito).
- **Ordem de rotas (FastAPI):** `GET /{post_id}` deve ser registrada de forma a **não** colidir com `GET ""` (listagem) — caminhos distintos (`/v1/posts` vs `/v1/posts/{id}`), sem ambiguidade. Conferir que `GET /v1/posts` (sem id) continua resolvendo para a listagem e não é capturado por `/{post_id}`.

### 4.3 Wiring (`main.py`)

```text
app.state.get_post_use_case = GetPublishedPost(repo=post_repo)
# handler de PostNotFound já registrado em T-S2-06 — não duplicar
```

## 5. Impacto em testes e quality gates

- **Unit (`test_get_post_usecase.py`):**
  - Post publicado no repo → `execute` retorna o dict; `status=="published"`.
  - Post **draft** no repo → `pytest.raises(PostNotFound)` (não vaza).
  - Post **ausente** → `pytest.raises(PostNotFound)`.
- **Integração HTTP (`test_read_by_id_http.py`)** — wiring completo:
  - **CA-F004-01:** cria + publica + `GET /v1/posts/{id}` → `200`, corpo `Post` correto.
  - **CA-F004-02 (draft):** cria (fica draft), `GET /v1/posts/{id}` → `404 post_not_found`.
  - **CA-F004-02 (inexistente):** `GET /v1/posts/INEXISTENTE` → `404 post_not_found`.
  - **Indistinguibilidade (âncora P-04):** capturar os dois `404` (draft e inexistente) e assertar **corpos idênticos** (`type`, `title`, `status`, `detail`) e mesmo `content-type` — diferença reintroduziria vazamento.
- **Cruzamento com F003:** o rascunho que dá `404` por id **também** não aparece em `GET /v1/posts` (teste negativo de visibilidade, P-04 — pode consolidar aqui ou em T-S2-06).
- **Mutation-âncora:** trocar a allowlist (`status is not PUBLISHED`) por aceitar qualquer status (remover a guarda) → rascunho passa a vazar com `200` → teste de CA-F004-02 vermelho.
- **Gates:** unit + integração; cobertura ≥ 95% nos módulos novos; `mypy --strict`.

## 6. Riscos

- **Diferenciar rascunho de inexistente** (qualquer divergência de status/type/title/detail) → vazamento de autorização (ADR-0004 §8). A indistinguibilidade é testada explicitamente (corpos byte-a-byte).
- **Denylist em vez de allowlist:** filtrar "esconder rascunhos" por exceção em vez de "só publicados" tende a vazar status novos no futuro. Usar **allowlist** (`is PUBLISHED`) — lição `qa.md`.
- **Colisão de rota** `GET /{post_id}` vs listagem: confirmar que `/v1/posts` (sem segmento) continua na listagem.
- **`detail` vazando existência:** texto genérico ("Nenhum post publicado com o id informado.") — mesmo do `404` de publicação.

## 7. Definition of Done (verificável)

- [ ] `GET /v1/posts/{id}` → `200` só para `published`; `draft` e inexistente → `404 post_not_found`.
- [ ] Allowlist por status no caso de uso (`is PUBLISHED`), não denylist/marker.
- [ ] `404` de draft e de inexistente são **byte-a-byte idênticos** (teste de indistinguibilidade verde).
- [ ] Reusa `PostNotFound` + `handle_post_not_found` de T-S2-06 (mesmo corpo do `404` de publicação).
- [ ] Rota pública (sem `Idempotency-Key`); listagem `GET /v1/posts` não quebrou (sem colisão de rota).
- [ ] Mutation-âncora (remover allowlist) faz CA-F004-02 vermelho.
- [ ] Cobertura ≥ 95%; `ruff` + `mypy --strict` verdes; sem regressão.
- [ ] Revisão aprovada (tl-python + tl-qa) sem ressalvas.
