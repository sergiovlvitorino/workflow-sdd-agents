# 006 — Architecture

**Status:** Vigente
**Versão:** 1.0.0
**Data:** 2026-06-24
**Responsável:** TL (`tl-python`)
**Constitution:** v1.0.0
**Origem:** ADR-0001 (stack) · ADR-0002 (paginação)

> Descreve *como* o backend do blog realiza as specs. Enxuto de propósito (ADR-0001: magro). Decisões não óbvias vivem em `adr/`. Escopo: backend FastAPI de Sprint 1; o frontend Angular (consumidor de `005`) é detalhado em sua própria trilha.

## 1. Estilo e princípios

**Hexagonal leve (ports & adapters)** com domínio puro. O domínio não conhece FastAPI, HTTP nem o mecanismo de persistência. Quatro camadas:

- **domain** — entidade `Post`, value objects, regras puras (sem framework/I/O).
- **application** — casos de uso (orquestram domínio + portas). Idempotência decidida aqui.
- **infrastructure** — adapters concretos das portas (repositório in-memory, idempotency store in-memory) — **marcados como didáticos** (ADR-0001); trocáveis por SQLite/Postgres sem tocar domínio (P-06/P-12).
- **interfaces** — camada HTTP FastAPI (routers, schemas Pydantic v2, dependencies, exception handlers → Problem Details).

Portas são `typing.Protocol` (P-12: adapter injetado, substituível). É exatamente o gancho onde cada princípio vira peça nomeável (ADR-0001).

## 2. Stack

| Camada | Tecnologia | Por quê (ADR) |
|---|---|---|
| Linguagem/runtime | Python 3.10+, FastAPI + Uvicorn | ADR-0001 |
| Validação/serialização | Pydantic v2 | ADR-0001 (gera `422` e OpenAPI/`/docs` — P-01) |
| Persistência (MVP) | Adapter **in-memory** (didático); SQLite trocável | ADR-0001 (sem ORM pesado no MVP) |
| Paginação | Keyset/cursor opaco | ADR-0002 |
| Testes | `pytest` + `TestClient` (teste HTTP real) | ADR-0001 / `docs/lessons/qa.md` |

## 3. Componentes e fronteiras

```
[cliente HTTP] ──▶ [interfaces: FastAPI router]
                        │  (Pydantic valida → 422; dependency Idempotency-Key → 400)
                        ▼
                   [application: caso de uso]
                        │  (consulta idempotency store; cria Post; persiste)
                        ├──▶ [port: PostRepository]      ──▶ [adapter in-memory]
                        └──▶ [port: IdempotencyStore]    ──▶ [adapter in-memory]
                        ▼
                   [domain: Post] (puro)
```

- **router** traduz HTTP↔caso de uso; não tem regra de negócio.
- **caso de uso** é o único que orquestra idempotência + domínio + portas.
- **exception handler** converte erro de domínio/validação → `ApiError` Problem Details (P-11), centralizado (não espalhado por router).

## 4. Decisões transversais

- **Isolamento de autorização (P-04):** sem multi-tenancy. `GET /v1/posts` filtra por **allowlist** `status == "published"` no caso de uso/porta — nunca confia no cliente, e é allowlist (lista filtrada `200`), não marker (`404`) — ver `docs/lessons/qa.md`.
- **Idempotência (P-03):** chave (`Idempotency-Key`) + **resposta persistida** (abordagem simples do ADR-0001, sem outbox). O store guarda `key → (hash do payload, resposta serializada)`. Replay com mesmo payload devolve a resposta gravada (`200` + `Idempotent-Replayed: true`); payload divergente → `409`. Hash do payload por `sha256` (determinístico — **não** `hash()` do Python, que é aleatorizado por `PYTHONHASHSEED`; `docs/lessons/python.md`).
- **Paginação (P-06):** keyset opaco, ordenação total `(published_at DESC, id DESC)` com `id` de desempate; cursor codifica `(published_at, id)` do último item (ADR-0002). Cursor é input externo → validado (P-11).
- **Identidade:** ULID (ordenável por tempo, ver `002` §6) — bom desempate keyset e estável para teste (relógio injetado, não `now()` no construtor — `docs/lessons/python.md`).
- **Observabilidade (P-05):** fora do escopo de Sprint 1 como entregável (F005, Sprint 2). A arquitetura reserva um ponto único (middleware ASGI) para RED + `request_id` quando F005 entrar — não se espalha por router.

## 5. ADRs relacionados

| ADR | Decisão | Status |
|---|---|---|
| [ADR-0001](adr/ADR-0001-stack-python-backend-angular-frontend.md) | Stack: FastAPI + Pydantic v2 (back) + Angular (front); adapter in-memory didático | Aceito |
| [ADR-0002](adr/ADR-0002-paginacao-keyset-vs-offset.md) | Paginação keyset/cursor opaco em `GET /v1/posts` | Aceito |

## 6. Estrutura de pastas (repo layout)

```
backend/
  src/blog/
    domain/          # Post, value objects, regras puras
    application/     # casos de uso (create_post, list_published_posts) + Protocols (portas)
    infrastructure/  # adapters in-memory (PostRepository, IdempotencyStore) — DIDÁTICO
    interfaces/      # FastAPI: routers, schemas Pydantic, dependencies, error handlers
    main.py          # composição: instancia adapters, injeta nos casos de uso, monta app
  tests/
    unit/            # domínio + casos de uso (com fakes)
    integration/     # HTTP real via TestClient (cobre middleware/DI/serialização)
```

> O domínio em `domain/` é o núcleo estável; tudo que muda por decisão de stack vive nas bordas (`infrastructure`/`interfaces`). É a lição de P-06/P-12 materializada na árvore de pastas.
