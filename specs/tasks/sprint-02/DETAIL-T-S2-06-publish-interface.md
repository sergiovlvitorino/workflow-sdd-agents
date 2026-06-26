# DETAIL — T-S2-06 — F002 interface: `PUT /v1/posts/{id}/publish` + erro `post_not_found`

**Sprint:** 2
**Tamanho:** M _(estimativa)_
**Papel:** BE (+ TL revisão)
**Depende de:** T-S2-05 (`PublishPost` + `PostNotFound`), T-S2-04 (wiring de produção parametrizável)
**Bloqueia:** —

> Produzido por um `tl-*` no `sprint-flow` (detalhamento técnico); consumido pelo `review-loop` (implementação + revisão). Descreve a tarefa no **presente** — o status real vive no índice/board, não aqui (ver `docs/lessons/process.md`).

---

## 1. Objetivo

Expor a publicação via `PUT /v1/posts/{id}/publish`, honrando o piso de idempotência (`Idempotency-Key`, P-03) em toda escrita e o catálogo de erros (`404 post_not_found` centralizado, RFC 9457) — o contrato §2.3 do `005` ganha realização HTTP.

## 2. CAs / RNs cobertos

- **CA-F002-01 (RF-008):** `PUT .../publish` em draft → `200` com `status="published"`, `published_at` preenchido.
- **CA-F002-02 (RF-009):** republicar já `published` → `200`, `published_at` inalterado.
- **CA-F002-03 (RF-010):** id inexistente → `404 post_not_found`; ausência de `Idempotency-Key` → `400 idempotency_key_required` (piso P-03).
- **ADR-0004 §8 (vinculante) — esta tarefa materializa:**
  - **Piso P-03 na escrita:** a rota **aceita/exige** `Idempotency-Key` (PO fechou: não se abre desvio por simplificação didática).
  - **Catálogo de erros centralizado:** `404 post_not_found` (novo `type` RFC 9457) no handler centralizado em `interfaces/errors.py` — **não** espalhar no router.
  - Transição aberta — **sem autenticação/autorização/ownership** (nenhuma identidade entra na rota).

## 3. Arquivos a criar/alterar

| Path | Ação | Descrição |
|---|---|---|
| `src/blog/interfaces/posts_router.py` | alterar | Adicionar `PUT /{id}/publish` (reusa `require_idempotency_key`). |
| `src/blog/interfaces/errors.py` | alterar | Adicionar `handle_post_not_found` (importa `PostNotFound` de `application/publish_post`). |
| `src/blog/main.py` | alterar | Registrar `PublishPost` em `app.state` + registrar `handle_post_not_found`. |
| `tests/integration/test_publish_http.py` | criar | Integração HTTP (CA-F002-01/02/03 + replay + sem-chave). |

## 4. Design da solução

### 4.1 Rota (router)

```text
@router.put("/{post_id}/publish", status_code=200)
async def publish_post(
    request: Request,
    post_id: str,
    idem_key: Annotated[str, Depends(require_idempotency_key)],   # piso P-03 reutilizado
) -> JSONResponse:
    """Publica um post (CA-F002-01..03). Transição aberta — sem auth (ADR-0004)."""
    use_case = request.app.state.publish_post_use_case
    response_dict = use_case.execute(post_id)         # PostNotFound → handler → 404
    return JSONResponse(status_code=200, content=response_dict)
```

Notas de design:
- **Reutiliza `require_idempotency_key`** (já existe, dispara `IdempotencyKeyRequired` → `400`). Não duplicar a validação no router.
- **Sem corpo de negócio** (contrato §2.3: request body vazio). Não declarar `body` Pydantic.
- `post_id` é path param `str` (ULID); validação de formato fica fora de escopo (id inexistente cai em `404`, não `422`).

### 4.2 Nível de idempotência — decisão explícita

O contrato §2.3 descreve **dois níveis**: (a) idempotência **por estado** (no-op de republicação — já garantida em T-S2-05 no domínio) e (b) **piso `Idempotency-Key`** (replay → `Idempotent-Replayed: true`).

| Critério | A. Só por estado + exigir header | B. Replay completo via `IdempotencyStore` _(DECIDIDA)_ |
|---|---|---|
| Atende RF-008/009/010 | sim | sim |
| Atende piso P-03 (header exigido) | sim | sim |
| `Idempotent-Replayed: true` no replay | não emite | **emite** |
| Coerência com `POST /v1/posts` e `005 §2.3` | parcial (omite o header do contrato) | **total** |
| Complexidade | baixa — reusa no-op do domínio | maior — reusa o `IdempotencyStore` por rota/recurso |

**Decisão: B — replay completo via `IdempotencyStore`** (reconciliada no review-loop antes da execução; orquestrador, alinhada ao princípio que o PO fixou: piso P-03 sem atalho didático).

Racional: o `POST /v1/posts` já emite `Idempotent-Replayed: true` no replay por chave, e o contrato `005 §2.3` descreve o mesmo para a publicação. Adotar a opção A criaria uma **divergência observável** entre o que o contrato promete (header no replay) e o que a rota entrega — exatamente o tipo de incoerência spec×código que P-02 proíbe. A idempotência **por estado** (RF-009, no-op do domínio) permanece como camada inferior inegociável; sobre ela, a rota reusa o `IdempotencyStore`.

**Esquema de chave (preciso — o `IdempotencyStore` é COMPARTILHADO com `POST /v1/posts`):**
- **`store_key = f"publish:{idem_key}"`** — o prefixo `publish:` namespaceia por rota (evita colisão com a chave crua que o `create_post` usa no mesmo store); o `idem_key` (header do cliente) mantém o piso P-03 keyed pela chave do cliente.
- **`payload_hash = sha256(post_id)`** — discrimina o recurso-alvo. Permite o `409` quando a mesma `Idempotency-Key` é reusada para um `post_id` divergente (store_key igual, hash diferente → conflito), sem virar cache-miss.

> ⚠️ NÃO usar a `Idempotency-Key` crua no store (colide com `POST /v1/posts`, que grava no mesmo `idem_store` com a chave crua → `409` espúrio quando o cliente reusa a mesma chave entre as duas rotas). NÃO usar `publish:{post_id}` como store_key sem o `idem_key` (perderia o piso P-03 — replays de chaves diferentes colapsariam).

**Inegociável:**
- Sem `Idempotency-Key` → `400 idempotency_key_required` (piso P-03), **nada publicado**.
- Replay com a mesma chave (mesmo `post_id`) → `200` + header `Idempotent-Replayed: true` + corpo idêntico (CA real ancorado por T-S2-08 A5/M4).
- Mesma `Idempotency-Key` reusada para `post_id` divergente → `409 idempotency_key_conflict`.
- **Sem colisão cross-rota:** a mesma `Idempotency-Key` usada em `POST /v1/posts` e depois em `PUT .../publish` NÃO conflita (namespaces distintos) — exigir teste que prove isso.
- Idempotência por estado (RF-009) continua válida mesmo sem replay por chave (já vem do domínio de T-S2-05).

### 4.3 Erro `post_not_found` centralizado (ADR-0004 §8)

```text
# interfaces/errors.py
from blog.application.publish_post import PostNotFound

async def handle_post_not_found(request, exc) -> JSONResponse:
    body = _error_body(
        type_suffix="post_not_found",
        title="Post não encontrado",
        status=404,
        detail="Nenhum post publicado com o id informado.",   # NÃO revela existência
    )
    return JSONResponse(status_code=404, content=body, media_type=PROBLEM_JSON)
```

- **Mesmo corpo** que o `404` do read-by-id (T-S2-07) — o `detail` é genérico e **não** permite inferir existência (ADR-0004 §8; alinhado ao §2.3/§2.4 do `005`).
- Registrado em `main.py`: `app.add_exception_handler(PostNotFound, handle_post_not_found)`.
- **Reuso por T-S2-07:** o read-by-id levantará a **mesma** `PostNotFound` (ver T-S2-07) → mesmo handler, mesmo corpo, garantindo resposta indistinguível por construção (não por coincidência de texto).

### 4.4 Wiring (`main.py`)

```text
app.state.publish_post_use_case = PublishPost(repo=post_repo, clock=_utc_now)
app.add_exception_handler(PostNotFound, handle_post_not_found)  # type: ignore[arg-type]
```

`_utc_now` já existe e produz UTC tz-aware (coerente com keyset/serialização).

## 5. Impacto em testes e quality gates

- **Integração HTTP (`test_publish_http.py`)** — exercita o wiring de DI completo (anti-falso-verde):
  - **CA-F002-01:** cria draft (`POST`), publica (`PUT .../publish`) → `200`, `status=="published"`, `published_at` não-nulo.
  - **CA-F002-02:** publica duas vezes → 2ª `200` com `published_at` **idêntico** ao da 1ª (asserção de valor exato); contagem de publicados estável.
  - **CA-F002-03 (not found):** `PUT /v1/posts/INEXISTENTE/publish` com chave → `404`, `type` termina em `post_not_found`, `content-type: application/problem+json`; **nada publicado** (asserção de estado).
  - **CA-F002-03 (sem chave):** `PUT .../publish` sem `Idempotency-Key` → `400 idempotency_key_required`; **nada publicado** (guard antes do caso de uso).
  - **Replay:** mesma chave duas vezes → ambos `200`, estado consistente, `published_at` estável.
- **Visibilidade (cruza com F003/F004):** após publicar, o post aparece em `GET /v1/posts`; rascunho não publicado **não** aparece (teste negativo P-04 — pode morar aqui ou em T-S2-07).
- **Gates:** cobertura ≥ 95% no router/handler novos; `mypy --strict` no `src/` inteiro (o `type: ignore[arg-type]` segue o padrão dos handlers existentes).

## 6. Riscos

- **Espalhar tratamento de `404` no router** (anti-pattern §8): manter no handler centralizado — router só levanta/deixa propagar `PostNotFound`.
- **`detail` que vaza existência:** se o `detail` distinguir "rascunho" de "inexistente", reintroduz vazamento de autorização (ADR-0004 §8). Texto genérico obrigatório.
- **Esquecer de exigir o header:** sem `require_idempotency_key`, viola o piso P-03 (PO fechou que não se abre desvio).
- **Status code:** `PUT .../publish` retorna **`200`** (não `201` — não cria recurso, transiciona estado existente). Conferir contra §2.3.
- **Contaminação:** integração usa `create_app` isolada por teste (in-memory injetado), como a suíte de Sprint 1.

## 7. Definition of Done (verificável)

- [ ] `PUT /v1/posts/{id}/publish` exige `Idempotency-Key` (piso P-03) e retorna `200` com `Post` publicado.
- [ ] **Replay com a mesma `Idempotency-Key` → `200` + header `Idempotent-Replayed: true` + corpo idêntico** (opção B; reusa `IdempotencyStore` com chave `publish:{id}`).
- [ ] Mesma chave reusada para `post_id` divergente → `409 idempotency_key_conflict`.
- [ ] Republicar (idempotência por estado, RF-009) → `200`, `published_at` inalterado (valor exato), contagem de publicados estável.
- [ ] Id inexistente → `404 post_not_found` (corpo RFC 9457, `application/problem+json`), nada publicado.
- [ ] Sem header → `400 idempotency_key_required`, nada publicado.
- [ ] `handle_post_not_found` no handler **centralizado** (não no router); registrado em `main.py`.
- [ ] `detail` genérico — não revela existência (mesmo corpo do `404` de read-by-id).
- [ ] Nenhuma identidade/auth na rota (transição aberta — ADR-0004).
- [ ] Cobertura ≥ 95%; `ruff` + `mypy --strict` verdes; sem regressão.
- [ ] Revisão aprovada (tl-python + tl-qa) sem ressalvas.
