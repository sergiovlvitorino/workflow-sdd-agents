# 005 — API Contract

**Status:** Vigente
**Versão:** 1.1.0
**Data:** 2026-06-25
**Responsável:** PO + TL (`tl-python`)
**Constitution:** v1.0.0
**Origem:** F001, F003 (Sprint 1) · F002, F004 (Sprint 2) · ADR-0001 (stack) · ADR-0002 (paginação) · ADR-0004 (publicação sem autenticação)

> Contrato é entregável **antes** da implementação (P-01). Idempotência obrigatória em escrita (P-03); versionamento por prefixo `/v1` (P-08). Este documento é a **fonte única** do contrato REST: o backend FastAPI o realiza e o frontend Angular o consome (tipos/mocks derivados deste schema — ver ADR-0001, condição anti-drift). Escopo desta versão: Sprint 1 (`POST /v1/posts`, `GET /v1/posts`) **+ Sprint 2** (`PUT /v1/posts/{id}/publish`, `GET /v1/posts/{id}`).

**Nota de mudança — v1.1.0 (2026-06-25, minor / aditivo):**
- **Novo endpoint** `PUT /v1/posts/{id}/publish` (§2.3) — publicação como **transição de estado aberta, sem autenticação** (ADR-0004 §4). `published_at` é preenchido na publicação.
- **Novo endpoint** `GET /v1/posts/{id}` (§2.4) — leitura por id; `404` (mesmo corpo) para **rascunho ou inexistente**, sem revelar existência (ADR-0004 §8; allowlist de leitura, P-04).
- **Novo erro tipado** `post_not_found` (`404`) no catálogo §4.
- Mudanças **aditivas** (novos endpoints + novo `type` de erro) ⇒ minor bump, sem quebra (P-08). O schema `Post` e `published_at` já existiam; nada removido/renomeado.

## 1. Convenções gerais

- **Base URL / versão:** `/v1` (P-08). Quebra de contrato → major bump + janela de coexistência (default 90–180 dias).
- **Autenticação:** **não há mecanismo de autenticação/autorização em nenhuma rota** (ADR-0004) — contexto local/monousuário/didático. As rotas de **escrita** (`POST /v1/posts`, `PUT /v1/posts/{id}/publish`) são **abertas**, protegidas apenas por idempotência (P-03), não por identidade. A "autorização" da constitution (P-04) é satisfeita **exclusivamente** pela **allowlist de leitura**: `GET /v1/posts` e `GET /v1/posts/{id}` só revelam posts `published`; rascunhos nunca vazam (retornam `404` no read-by-id). _Nota didática: em produção, escrita exige autenticação e autorização — ver ADR-0004 §99._
- **Content-Type:** `application/json; charset=utf-8` em request e response.
- **Idempotência (P-03):** rotas de escrita exigem o header `Idempotency-Key` (string não-vazia, ≤ 200 chars). Replay com a **mesma chave e mesmo payload** retorna a resposta original com `Idempotent-Replayed: true`. Mesma chave com **payload divergente** → `409 idempotency_key_conflict`. Ausência do header em rota de escrita → `400 idempotency_key_required`.
- **Paginação:** **keyset/cursor opaco** (ADR-0002). O cliente trata `next_cursor` como token cego: ecoa em `?cursor=`, nunca o constrói nem interpreta. `next_cursor = null` ⇒ última página.
- **Formato de erro:** **Problem Details (RFC 9457)** — `Content-Type: application/problem+json`. Ver §4 (`ApiError`). Todo erro é tipado e acionável (P-11); nunca fallback "best effort" silencioso.

## 2. Endpoints

### 2.1 `POST /v1/posts` — criar post (F001)

| | |
|---|---|
| **Descrição** | Cria um post. Nasce em `status = "draft"`. |
| **Auth** | autor (contexto de request — didático) |
| **Idempotente** | **sim** — header `Idempotency-Key` obrigatório (P-03) |

**Headers (request)**

| Header | Obrigatório | Descrição |
|---|---|---|
| `Idempotency-Key` | **sim** | Chave fornecida pelo cliente. String não-vazia, ≤ 200 chars. Ausência → `400`. |
| `Content-Type` | sim | `application/json` |

**Request body** — `CreatePostRequest`

```json
{
  "title": "Meu primeiro post",
  "content": "Conteúdo do post em texto."
}
```

| Campo | Tipo | Regra |
|---|---|---|
| `title` | string | obrigatório, 1–200 chars (após `strip`); vazio/ausente → `422` |
| `content` | string | obrigatório, 1–50000 chars; ausente → `422` |

**Respostas**

| Código | Quando | Corpo | Headers |
|---|---|---|---|
| `201 Created` | criado (chave nova, payload válido) | `Post` | — |
| `200 OK` | replay idempotente: mesma chave + mesmo payload (CA-F001-02) | `Post` (o **mesmo** da criação original) | `Idempotent-Replayed: true` |
| `400 Bad Request` | sem header `Idempotency-Key` (CA-F001-04) | `ApiError` (`type: ".../idempotency_key_required"`) | — |
| `409 Conflict` | mesma chave, payload divergente | `ApiError` (`type: ".../idempotency_key_conflict"`) | — |
| `422 Unprocessable Entity` | payload inválido (CA-F001-03) | `ApiError` com `errors[]` apontando o campo | — |

> **Nota de contrato (CA-F001-02):** o backlog admite "200 ou 201 idempotente". Este contrato **fixa `200` com `Idempotent-Replayed: true`** no replay, para o replay ser distinguível da primeira criação (`201`) — distinção observável e testável. O `id` retornado é sempre o da primeira chamada.

**Exemplo `201`**

```json
{
  "id": "01J9Z3K7Q2M4N5P6R7S8T9V0W1",
  "title": "Meu primeiro post",
  "content": "Conteúdo do post em texto.",
  "status": "draft",
  "created_at": "2026-06-24T14:30:00Z",
  "published_at": null
}
```

**Exemplo `422`**

```json
{
  "type": "https://blog-tutorial/errors/validation_error",
  "title": "Erro de validação",
  "status": 422,
  "detail": "O campo 'title' é obrigatório.",
  "errors": [
    { "field": "title", "code": "missing", "message": "Field required" }
  ]
}
```

---

### 2.2 `GET /v1/posts` — listar posts publicados (F003)

| | |
|---|---|
| **Descrição** | Lista posts **publicados** (allowlist — rascunhos nunca aparecem, RF-006), ordenados por `(published_at DESC, id DESC)`, paginados por cursor keyset (ADR-0002). |
| **Auth** | público / anônimo |
| **Idempotente** | sim (leitura, sem efeito) |

**Query params**

| Param | Tipo | Default | Regra |
|---|---|---|---|
| `limit` | int | `10` | 1–100; fora da faixa → `422` |
| `cursor` | string (opaco) | ausente | token devolvido por `next_cursor`; malformado → `400 invalid_cursor` (P-11) |

**Respostas**

| Código | Quando | Corpo |
|---|---|---|
| `200 OK` | sucesso (lista possivelmente vazia) | `Page<Post>` |
| `400 Bad Request` | `cursor` inválido/corrompido (CA-F003-03, P-11) | `ApiError` (`type: ".../invalid_cursor"`) |
| `422 Unprocessable Entity` | `limit` fora da faixa | `ApiError` |

**Exemplo `200`** — `Page<Post>`

```json
{
  "items": [
    {
      "id": "01J9Z3K7Q2M4N5P6R7S8T9V0W1",
      "title": "Post publicado",
      "content": "…",
      "status": "published",
      "created_at": "2026-06-24T14:30:00Z",
      "published_at": "2026-06-24T15:00:00Z"
    }
  ],
  "next_cursor": "eyJwIjoiMjAyNi0wNi0yNFQxNTowMDowMFoiLCJpZCI6IjAxSjlaM0s3In0",
  "limit": 10
}
```

> Última página ⇒ `next_cursor: null`. O front avança enquanto `next_cursor != null`.

---

### 2.3 `PUT /v1/posts/{id}/publish` — publicar post (F002)

| | |
|---|---|
| **Descrição** | Publica um post: transição de estado `draft → published`. **Aberta — sem autenticação/autorização/ownership** (ADR-0004 §4). Define `published_at` no momento da publicação. |
| **Auth** | nenhuma (transição aberta — qualquer cliente local) |
| **Idempotente** | **sim** — por estado (republicar `published` é no-op) **e** aceita header `Idempotency-Key` (P-03, ADR-0004 §8) |

**Path params**

| Param | Tipo | Descrição |
|---|---|---|
| `id` | string (ULID) | id do post a publicar. Inexistente → `404 post_not_found`. |

**Headers (request)**

| Header | Obrigatório | Descrição |
|---|---|---|
| `Idempotency-Key` | **sim** | Chave fornecida pelo cliente. String não-vazia, ≤ 200 chars. Ausência → `400 idempotency_key_required` (piso P-03 em toda escrita). |
| `Content-Type` | sim | `application/json` (sem corpo de negócio; a publicação não tem payload) |

**Request body** — vazio (a transição não recebe campos).

**Respostas**

| Código | Quando | Corpo | Headers |
|---|---|---|---|
| `200 OK` | post publicado **agora** (estava `draft`) — CA-F002-01 | `Post` (`status: "published"`, `published_at` preenchido) | — |
| `200 OK` | **no-op idempotente por estado**: post já estava `published` — `published_at` **inalterado** (RF-009) | `Post` (mesmo estado atual) | — |
| `200 OK` | replay idempotente: mesma `Idempotency-Key` (mesma rota/recurso) | `Post` (a mesma resposta original) | `Idempotent-Replayed: true` |
| `400 Bad Request` | sem header `Idempotency-Key` | `ApiError` (`type: ".../idempotency_key_required"`) | — |
| `404 Not Found` | id inexistente (CA-F002-03) | `ApiError` (`type: ".../post_not_found"`) | — |
| `409 Conflict` | mesma `Idempotency-Key` reutilizada em recurso/operação divergente | `ApiError` (`type: ".../idempotency_key_conflict"`) | — |

> **Nota de contrato (idempotência em dois níveis):** a operação é idempotente **por estado** (republicar `published` não muda `published_at` — semântica de domínio, RF-009) **e** honra o **piso `Idempotency-Key`** como toda escrita (replay → `Idempotent-Replayed: true`). São camadas complementares: a primeira garante a regra de negócio mesmo sem a chave; a segunda garante o piso P-03 do projeto (ADR-0004 §8 fechou que não se abre desvio).

**Exemplo `200` (publicado)**

```json
{
  "id": "01J9Z3K7Q2M4N5P6R7S8T9V0W1",
  "title": "Meu primeiro post",
  "content": "Conteúdo do post em texto.",
  "status": "published",
  "created_at": "2026-06-24T14:30:00Z",
  "published_at": "2026-06-25T10:00:00Z"
}
```

**Exemplo `404`** (id inexistente — mesmo corpo do read-by-id de rascunho, não revela existência)

```json
{
  "type": "https://blog-tutorial/errors/post_not_found",
  "title": "Post não encontrado",
  "status": 404,
  "detail": "Nenhum post publicado com o id informado."
}
```

---

### 2.4 `GET /v1/posts/{id}` — ler post por id (F004)

| | |
|---|---|
| **Descrição** | Lê um post **publicado** pelo id. Rascunho **ou** inexistente → `404` com **o mesmo corpo** (não revela a existência de rascunhos). Coerente com a allowlist de leitura de `GET /v1/posts` (P-04, ADR-0004 §8). |
| **Auth** | público / anônimo |
| **Idempotente** | sim (leitura, sem efeito) |

**Path params**

| Param | Tipo | Descrição |
|---|---|---|
| `id` | string (ULID) | id do post. Rascunho ou inexistente → `404 post_not_found`. |

**Respostas**

| Código | Quando | Corpo |
|---|---|---|
| `200 OK` | post existe **e** está `published` (CA-F004-01) | `Post` |
| `404 Not Found` | post está em `draft` **ou** não existe — **mesma resposta** (CA-F004-02; não revela existência) | `ApiError` (`type: ".../post_not_found"`) |

> **Nota de contrato (P-04, ADR-0004 §8):** rascunho e id inexistente retornam **resposta indistinguível** (mesmo `status`, mesmo `type`, mesmo `title`). Diferenciá-los (ex.: `403` para rascunho) reintroduziria vazamento de autorização — proibido. O `detail` é texto livre e **não** deve permitir inferir a existência.

**Exemplo `200`**

```json
{
  "id": "01J9Z3K7Q2M4N5P6R7S8T9V0W1",
  "title": "Post publicado",
  "content": "…",
  "status": "published",
  "created_at": "2026-06-24T14:30:00Z",
  "published_at": "2026-06-25T10:00:00Z"
}
```

**Exemplo `404`** (rascunho ou inexistente — corpo idêntico)

```json
{
  "type": "https://blog-tutorial/errors/post_not_found",
  "title": "Post não encontrado",
  "status": 404,
  "detail": "Nenhum post publicado com o id informado."
}
```

## 3. Schemas (shapes canônicos)

### `Post`

| Campo | Tipo | Nullable | Descrição |
|---|---|---|---|
| `id` | string (ULID) | não | Identidade do post (ver `002` §6). |
| `title` | string | não | Título (1–200). |
| `content` | string | não | Corpo (1–50000). |
| `status` | enum `"draft" \| "published"` | não | Estado. Nasce `draft` (F001); transiciona para `published` via `PUT /v1/posts/{id}/publish` (F002, ADR-0004). |
| `created_at` | string (RFC 3339, UTC `Z`) | não | Instante de criação. |
| `published_at` | string (RFC 3339, UTC `Z`) | **sim** | `null` enquanto rascunho; **preenchido na publicação** (F002) e **inalterado** em republicação/replay (RF-009). |

> Extensibilidade (P-06): novos campos são **aditivos e opcionais**; consumidores ignoram campos desconhecidos. Remover/renomear campo ou apertar nullabilidade = breaking (major bump, P-08).

### `Page<T>`

| Campo | Tipo | Nullable | Descrição |
|---|---|---|---|
| `items` | `T[]` | não | Itens da página (≤ `limit`); pode ser `[]`. |
| `next_cursor` | string | **sim** | Token opaco da próxima página; `null` ⇒ fim (ADR-0002). |
| `limit` | int | não | Eco do `limit` efetivo aplicado. |

> Deliberadamente **sem `total`/`page`/`offset`** — keyset não os oferece de graça e o blog didático não precisa (ADR-0002). Adicioná-los exige novo ADR.

## 4. `ApiError` — Problem Details (RFC 9457)

`Content-Type: application/problem+json`.

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `type` | string (URI) | sim | Identificador estável do tipo de erro. Sufixo é o **code tipado** (`validation_error`, `idempotency_key_required`, `idempotency_key_conflict`, `invalid_cursor`, `post_not_found`). |
| `title` | string | sim | Resumo legível, estável por `type`. |
| `status` | int | sim | Código HTTP (espelha o status da resposta). |
| `detail` | string | não | Explicação específica desta ocorrência. |
| `errors` | array | não | Só em `validation_error`: lista `{ field, code, message }` (P-11 — aponta o campo). |

**Catálogo de erros (Sprint 1 + Sprint 2)**

| `type` (sufixo) | HTTP | Quando |
|---|---|---|
| `validation_error` | 422 | payload/query inválido (RF-003) |
| `idempotency_key_required` | 400 | escrita sem `Idempotency-Key` (RF-004, RF-010) |
| `idempotency_key_conflict` | 409 | mesma chave, payload/recurso divergente |
| `invalid_cursor` | 400 | cursor malformado em `GET /v1/posts` (RF-007) |
| `post_not_found` | 404 | publicar id inexistente (RF-010); ler por id rascunho **ou** inexistente (RF-011) — **mesmo corpo nos dois casos** (não revela existência, ADR-0004 §8) |

> O sufixo de `type` é o **code tipado** que o frontend Angular mapeia no `HttpInterceptor` (ADR-0001) — é o contrato de erro entre fronteiras. O front nunca faz `string-match` no `detail` (texto livre, pode mudar); discrimina por `type`/`status`.

## 5. Versionamento e depreciação

- Prefixo `/v1` (P-08). Mudança aditiva (campo opcional novo, novo endpoint) → minor, sem bump de major.
- Quebra (remover/renomear campo, mudar tipo/nullabilidade, mudar semântica de status) → `/v2` + janela de coexistência (90–180 dias) + ADR.
- Este contrato é o schema de origem do contract test cross-language (ADR-0001): mutar um campo aqui **tem** que deixar o contract test do front vermelho.
