# 002 — Domain Model

**Status:** Rascunho mínimo _(escopo Sprint 1: só a entidade `Post`)_
**Versão:** 0.2.0
**Data:** 2026-06-24
**Responsável:** PO + TL (`tl-python`)
**Constitution:** v1.0.0

> **Rascunho mínimo de propósito** (princípio enxuto/didático): cobre apenas o necessário para `Post` em Sprint 1 (F001/F003). `Author`/`Comment` e a publicação completa (F002) entram em versão minor futura. Define a linguagem ubíqua e as invariantes que código, testes e specs compartilham.

## 1. Linguagem ubíqua (glossário)

| Termo | Definição | Evitar |
|---|---|---|
| Post | Unidade de conteúdo do blog (título + corpo) com um ciclo de vida `draft → published`. | "artigo", "matéria" |
| Rascunho (`draft`) | Post recém-criado, ainda não visível ao público. | — |
| Publicado (`published`) | Post visível em `GET /v1/posts`. | — |
| Chave de idempotência | Token fornecido pelo cliente (`Idempotency-Key`) que torna a criação repetível sem duplicar. | "request id" |
| Cursor | Token opaco de paginação keyset (ADR-0002). | "offset", "página N" |

## 2. Entidades e agregados

**`Post`** (agregado raiz, único no MVP):

| Atributo | Tipo | Notas |
|---|---|---|
| `id` | ULID (string) | identidade; ver §6 |
| `title` | string (1–200) | obrigatório |
| `content` | string (1–50000) | obrigatório |
| `status` | `draft \| published` | nasce `draft` |
| `created_at` | datetime (UTC) | imutável |
| `published_at` | datetime \| null | `null` enquanto rascunho |

> Shapes de API derivam daqui (`005` §3). O domínio é puro (sem framework) — ver `006` §1.

## 3. Máquina de estados

```
(criação F001) ──▶ [draft] ──publish (F002)──▶ [published]
```

| De | Evento | Para | Guarda / pré-condição |
|---|---|---|---|
| — | criar (F001) | `draft` | título e conteúdo válidos |
| `draft` | publicar (F002, Sprint 2) | `published` | autor é o dono (P-04); seta `published_at` |

> A transição `publish` é **F002 (Sprint 2)** — fora do escopo de Sprint 1. Em Sprint 1, posts publicados usados nos testes de F003 são semeados pelo adapter didático.

## 4. Invariantes (RN-D-NN)

> Cada uma vira teste negativo (P-07).

- **RN-D-01:** Um post sempre tem `title` e `content` não-vazios (1–200 / 1–50000). Violação → `422` (RF-003).
- **RN-D-02:** Um post `draft` tem `published_at == null`; um `published` tem `published_at != null`. (`published_at` só é setado na transição `publish`.)
- **RN-D-03:** `GET /v1/posts` retorna **apenas** posts `published` (allowlist) — rascunho nunca vaza ao público (RF-006, P-04).
- **RN-D-04:** Criar com a mesma `Idempotency-Key` (e mesmo payload) não gera novo `Post` (RF-002, P-03).

## 5. Eventos de domínio

> Não há eventos/mensageria no MVP (sem outbox — ADR-0001). Seção reservada para quando F005/integrações entrarem.

## 6. Identificadores

- **ULID** (Universally Unique Lexicographically Sortable Id): ordenável por tempo de criação, o que dá um desempate natural e estável para a paginação keyset (ADR-0002) e ordem determinística em teste.
- Gerado por um **id-generator injetado** (não no construtor da entidade) — mantém o domínio testável e determinístico (`docs/lessons/python.md`).
- Sem particionamento por tenant (não há multi-tenancy — `006` §4).
