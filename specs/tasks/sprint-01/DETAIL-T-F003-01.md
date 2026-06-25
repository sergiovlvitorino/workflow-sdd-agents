# DETAIL — T-F003-01 — Listar posts publicados com paginação keyset (`GET /v1/posts`)

**Sprint:** 01
**Tamanho:** S _(estimativa)_
**Papel:** BE (`dev-python`) + TL revisão (`tl-python` + `tl-qa`)
**Depende de:** T-F001-01 (entidade `Post`, app FastAPI, adapter in-memory)
**Bloqueia:** — (front consome `GET /v1/posts` depois, a partir de `005`)

> Produzido por `tl-python` no sprint-flow; consumido pelo review-loop. Realiza RF-005..007 e o shape `Page<Post>` de `005-api-contract.md`. A decisão de paginação é **ADR-0002** (keyset/cursor opaco) — não reabrir aqui.

---

## 1. Objetivo

Entregar `GET /v1/posts` listando **apenas posts publicados** (allowlist), paginados por cursor keyset estável: até `limit` itens + `next_cursor`; avançar via `?cursor=` não repete nem omite itens, mesmo com inserção concorrente; cursor inválido falha explícito. Demonstra **paginação como contrato de API estável** (P-06) — valor pedagógico de F003.

## 2. CAs / RNs cobertos

- **CA-F003-01 (RF-005):** 25 publicados, `GET /v1/posts?limit=10` → `200`, 10 itens, `next_cursor` não-nulo.
- **CA-F003-02 (RF-006, P-04):** com rascunhos + publicados, anônimo recebe **só os publicados** (allowlist, não marker).
- **CA-F003-03 (RF-007, ADR-0002):** página seguinte via `?cursor=C1` retorna os itens seguintes **sem repetir** os já vistos, estável sob inserção. Cursor inválido → `400 invalid_cursor` (P-11).

## 3. Arquivos a criar/alterar

| Path | Ação | Descrição |
|---|---|---|
| `backend/src/blog/application/list_published_posts.py` | criar | Caso de uso `ListPublishedPosts` (filtro allowlist + keyset + codec de cursor). |
| `backend/src/blog/application/cursor.py` | criar | `encode_cursor((published_at, id))` / `decode_cursor(str)` (base64url de JSON); `decode` valida e levanta `InvalidCursor`. |
| `backend/src/blog/application/ports.py` | alterar | Adicionar `PostRepository.list_published(after, limit) -> list[Post]` (keyset). |
| `backend/src/blog/infrastructure/in_memory.py` | alterar | Implementar `list_published`: filtra `published`, ordena `(published_at DESC, id DESC)`, corta em `after`, fatia `limit`. |
| `backend/src/blog/interfaces/schemas.py` | alterar | `PageResponse` (`items`, `next_cursor`, `limit`) conforme `005` §3. |
| `backend/src/blog/interfaces/posts_router.py` | alterar | `GET /v1/posts` com `limit` (1–100, default 10) e `cursor` opcional. |
| `backend/src/blog/interfaces/errors.py` | alterar | Handler `InvalidCursor` → `400 invalid_cursor`. |
| `backend/tests/integration/test_list_posts_http.py` | criar | Teste HTTP real dos 3 CAs + estabilidade sob inserção + cursor inválido. |
| `backend/tests/unit/test_cursor_codec.py` | criar | Round-trip e rejeição de cursor corrompido. |

## 4. Design da solução

**Ordenação total e keyset (ADR-0002):** ordenar por `(published_at DESC, id DESC)`; `id` (ULID) desempata para ordem total mesmo com `published_at` iguais. Cursor codifica `(published_at, id)` do **último item** da página.

```python
# cursor opaco: base64url(json{"p": published_at_iso, "id": post_id})
def encode_cursor(published_at: datetime, post_id: str) -> str: ...
def decode_cursor(raw: str) -> tuple[datetime, str]:
    # base64url-decode + json-parse + validar campos;
    # qualquer falha (padding, json, campo ausente, data inválida) -> raise InvalidCursor()
```

**Porta keyset (in-memory implementa o equivalente do `WHERE (published_at, id) < (:p, :id)`):**

```python
class PostRepository(Protocol):
    def list_published(self, *, after: tuple[datetime, str] | None, limit: int) -> list[Post]: ...
```

```python
# in-memory:
items = [p for p in self._posts if p.status is PostStatus.PUBLISHED]   # allowlist (RF-006)
items.sort(key=lambda p: (p.published_at, p.id), reverse=True)
if after is not None:
    items = [p for p in items if (p.published_at, p.id) < after]        # estrito '<' (não '<=')
return items[:limit]
```

**Caso de uso:**

```python
class ListPublishedPosts:
    def execute(self, *, limit: int, cursor: str | None) -> dict:
        after = decode_cursor(cursor) if cursor else None     # InvalidCursor -> 400
        page = self.repo.list_published(after=after, limit=limit + 1)  # pega 1 a mais p/ saber se há próxima
        has_more = len(page) > limit
        items = page[:limit]
        next_cursor = encode_cursor(items[-1].published_at, items[-1].id) if has_more else None
        return {"items": [to_response_dict(p) for p in items],
                "next_cursor": next_cursor, "limit": limit}
```

> Padrão `limit + 1`: busca um item além do `limit` para decidir `has_more` sem `COUNT` (coerente com ADR-0002: sem `total`). `next_cursor = null` na última página — sinal único de fim.

**Interface HTTP:** `limit: int = Query(10, ge=1, le=100)` (fora da faixa → `422` Pydantic); `cursor: str | None = Query(None)`; `GET` é público (sem dependency de idempotência). Handler `InvalidCursor` → `ApiError` `400` (`005` §4).

## 5. Impacto em testes e quality gates

- **Testes novos:**
  - **Integração HTTP real (`TestClient`):**
    - CA-F003-01: semear **25 publicados**, `?limit=10` → `200`, `len(items)==10`, `next_cursor` não-nulo.
    - CA-F003-02 (allowlist, P-04): semear 3 rascunhos + 2 publicados → resposta tem **exatamente os 2 publicados**; asserir que **nenhum** `id` de rascunho aparece (allowlist por valor, não "marker 404" — `docs/lessons/qa.md`).
    - **CA-F003-03 (estabilidade — o teste que prova o ponto da feature):** obter página 1; **inserir um post publicado** que ordenaria *entre* páginas; buscar página 2 via `next_cursor`; asserir que **nenhum `id` se repete** entre p1 e p2 **e** que nenhum item de p1 some. Não basta paginar lista estática (`docs/lessons/qa.md`: exercite a fronteira / inserção concorrente).
    - Cursor inválido: `?cursor=lixo!!!` → `400`, `type` sufixo `invalid_cursor`.
    - Borda: `limit=0` e `limit=101` → `422`.
  - **Unit do codec:** round-trip `encode`→`decode` preserva `(published_at, id)`; cursor corrompido (base64 inválido, json sem `id`, data inválida) → `InvalidCursor`.
- **Mutation-âncora:**
  - Trocar `<` por `<=` na comparação keyset → o item de fronteira **duplica** → CA-F003-03 vermelho (esta é a âncora central do ADR-0002).
  - Remover o filtro `status == PUBLISHED` → CA-F003-02 vermelho (rascunho vaza).
  - Fazer `decode_cursor` engolir erro e retornar `None` (volta ao início) → teste de cursor inválido vermelho.
  - Fixar `next_cursor=None` sempre → CA-F003-01 vermelho.
- **Cobertura esperada:** API 100% endpoints; allowlist/isolamento = **100% dos cenários** (P-07); codec de cursor ≥ 90% + branch de erro coberto.
- **Gates:** ratchet backend por-stack (ADR-0001); sem `skip`.

## 6. Riscos

- **`OFFSET` disfarçado:** se a implementação cair para slice por índice ignorando o keyset, CA-F003-03 quebra sob inserção. Mitigação: o teste insere entre páginas (não paginação estática) e a mutação `<`/`<=` ancora.
- **Marker vs allowlist (`docs/lessons/qa.md`):** testar só "não retorna 404" não prova filtro. Mitigação: asserir o **valor** (ids exatos publicados, nenhum rascunho).
- **Off-by-one na fronteira do cursor:** item com `published_at` igual ao do cursor pode repetir/sumir se a comparação não incluir `id`. Mitigação: ordem total `(published_at, id)` + teste com `published_at` empatado.
- **`now()` no seed dos posts** torna o teste não-determinístico. Mitigação: relógio injetado (vem de T-F001-01) e timestamps fixos no seed.
- **Cobertura async/coverage:** in-memory é síncrono; se evoluir para adapter async, lembrar `concurrency=["greenlet"]` (`docs/lessons/qa.md`). Não aplicável no MVP.

## 7. Definition of Done (verificável)

- [ ] CA-F003-01..03 automatizados e **verdes com execução real** (`TestClient`).
- [ ] CA-F003-03 prova estabilidade **inserindo um post entre páginas** (não lista estática).
- [ ] Allowlist testada por **valor** (ids publicados presentes, rascunhos ausentes).
- [ ] Cursor inválido → `400 invalid_cursor` coberto.
- [ ] Mutation-âncoras da §5 verificadas (`<`→`<=` derruba CA-F003-03).
- [ ] Cobertura ≥ piso P-07.
- [ ] Sem regressão na suíte completa.
- [ ] `mypy --strict` no `src/` inteiro limpo.
- [ ] Revisão aprovada (`tl-python` + `tl-qa`) sem ressalvas.
