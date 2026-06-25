# 003 — Functional Requirements

**Status:** Vigente
**Versão:** 1.1.0
**Data:** 2026-06-25
**Responsável:** PO (autoria de RFs no sprint-flow: `tl-python`)
**Constitution:** v1.0.0
**Origem:** `specs/backlog-blog-tutorial.md`

> Escopo desta versão: **Sprint 1** (F001 criar post idempotente, F003 listar paginado) **+ Sprint 2** (F002 publicar, F004 ler por id). Cada RF é rastreável a uma feature e a pelo menos um critério de aceite `CA-FXXX-NN` (P-02). Os RFs de F005/F008 entram em versões minor futuras.

**Nota de mudança — v1.1.0 (2026-06-25):**
- Adicionados os RFs de **F002 (publicar)** e **F004 (ler por id)** para a Sprint 2.
- **Publicação modelada como transição de estado ABERTA, sem autenticação/autorização/ownership** — conforme **ADR-0004** §4. Removida a linguagem herdada "com autorização": no contexto local/monousuário/didático não há identidade no domínio. A "autorização" da constitution (P-04) é satisfeita **exclusivamente** pela allowlist de leitura (rascunho nunca vaza).
- O cenário de ownership/403 que ocupava `CA-F002-02` foi removido pelo ADR-0004; o id foi reatribuído à **republicação idempotente** (backlog reescrito pelo PO).

## Requisitos funcionais

| ID | Requisito | MoSCoW | Feature | Notas |
|---|---|---|---|---|
| **RF-001** | O sistema **DEVE** permitir criar um post via `POST /v1/posts` com `title` e `content` válidos, retornando `201` com o `id` e `status = "draft"` (rascunho). | Must | F001 | CA-F001-01. Post nasce em rascunho. P-01. |
| **RF-002** | O sistema **DEVE** aceitar uma chave de idempotência fornecida pelo cliente (header `Idempotency-Key`) em `POST /v1/posts` e garantir que requisições repetidas com a mesma chave **não criam post novo** e retornam o **mesmo `id`** da primeira chamada. | Must | F001 | CA-F001-02. P-03. Idempotência obrigatória em escrita. |
| **RF-003** | O sistema **DEVE** rejeitar payload inválido em `POST /v1/posts` com `422` e corpo de erro tipado `validation_error` apontando o(s) campo(s) inválido(s). | Must | F001 | CA-F001-03. P-11 falha explícita. |
| **RF-004** | O sistema **DEVE** rejeitar `POST /v1/posts` sem o header `Idempotency-Key` com `400` e erro tipado `idempotency_key_required`. | Must | F001 | CA-F001-04. P-03 + P-11. |
| **RF-005** | O sistema **DEVE** listar posts publicados via `GET /v1/posts` de forma paginada por cursor (keyset), retornando `200` com até `limit` itens e um `next_cursor` para a próxima página. | Must | F003 | CA-F003-01. P-01, P-06. Paginação keyset — ADR-0002. |
| **RF-006** | O sistema **DEVE** retornar em `GET /v1/posts` **apenas posts publicados**; rascunhos não aparecem para o público. | Must | F003 | CA-F003-02. P-04 isolamento de autorização (allowlist, não marker — ver `docs/lessons/qa.md`). |
| **RF-007** | O sistema **DEVE** garantir que a página seguinte, obtida via `?cursor=`, retorna os itens seguintes **sem repetir nem omitir** os já vistos, mesmo sob inserção concorrente de novos posts publicados. | Must | F003 | CA-F003-03. ADR-0002 (keyset estável). Cursor inválido → `400 invalid_cursor` (P-11). |
| **RF-008** | O sistema **DEVE** permitir publicar um post via `PUT /v1/posts/{id}/publish`, realizando a transição de estado `draft → published` **sem qualquer autenticação, autorização ou ownership** (transição aberta), retornando `200` com o post em `status = "published"` e `published_at` preenchido. | Must | F002 | CA-F002-01. ADR-0004 §4 (transição aberta — sem identidade no domínio). P-08. |
| **RF-009** | O sistema **DEVE** tornar a publicação **idempotente por estado**: republicar um post já `published` é um **no-op** que retorna `200` com o estado atual, mantendo o **mesmo `published_at`** da primeira publicação (sem efeito colateral, sem duplicar a transição). | Must | F002 | CA-F002-01. ADR-0004 §4, §8 (idempotência por estado; `published_at` inalterado em replay). P-03. |
| **RF-010** | O sistema **DEVE** aceitar o header `Idempotency-Key` em `PUT /v1/posts/{id}/publish` (piso de idempotência em toda escrita) e **DEVE** rejeitar a publicação de um id inexistente com `404` e erro tipado `post_not_found`, sem revelar existência. | Must | F002 | CA-F002-03. ADR-0004 §8 (manter piso P-03 na escrita; transição inválida → `404 post_not_found`). P-03 + P-11. |
| **RF-011** | O sistema **DEVE** permitir ler um post pelo id via `GET /v1/posts/{id}`, retornando `200` com o post quando ele estiver **publicado**, e `404` com erro tipado `post_not_found` quando o post estiver em **rascunho** **ou** não existir — **mesma resposta nos dois casos, sem revelar a existência** de rascunhos. | Must | F004 | CA-F004-01, CA-F004-02. P-04 (allowlist de leitura — read-by-id coerente com `GET /v1/posts`). P-11. ADR-0004 §8. |

## Rastreabilidade

| RF | Feature(s) | CA(s) | Princípios | Status |
|---|---|---|---|---|
| RF-001 | F001 | CA-F001-01 | P-01 | aberto |
| RF-002 | F001 | CA-F001-02 | P-03 | aberto |
| RF-003 | F001 | CA-F001-03 | P-11 | aberto |
| RF-004 | F001 | CA-F001-04 | P-03, P-11 | aberto |
| RF-005 | F003 | CA-F003-01 | P-01, P-06 | aberto |
| RF-006 | F003 | CA-F003-02 | P-04 | aberto |
| RF-007 | F003 | CA-F003-03 | P-06 (ADR-0002) | aberto |
| RF-008 | F002 | CA-F002-01 | P-08 (ADR-0004) | aberto |
| RF-009 | F002 | CA-F002-02 | P-03 (ADR-0004) | aberto |
| RF-010 | F002 | CA-F002-03 | P-03, P-11 (ADR-0004) | aberto |
| RF-011 | F004 | CA-F004-01, CA-F004-02 | P-04, P-11 (ADR-0004) | aberto |

> Cobertura inversa (todo CA de Sprint 1+2 em escopo tem RF): CA-F001-01→RF-001, CA-F001-02→RF-002, CA-F001-03→RF-003, CA-F001-04→RF-004, CA-F003-01→RF-005, CA-F003-02→RF-006, CA-F003-03→RF-007, CA-F002-01→RF-008, CA-F002-02→RF-009, CA-F002-03→RF-010, CA-F004-01→RF-011, CA-F004-02→RF-011. Sem CA órfão.

## Fora de escopo (explícito)

- **Autenticação / autorização / ownership na escrita:** **removido por ADR-0004** (§4, §8). Não há conceito de usuário/sessão/token no domínio — a publicação (e a edição, quando entrar) é uma **transição de estado aberta**. O cenário "autor B recebe `403` ao editar post de A", que ocupava `CA-F002-02` no backlog antigo, foi **eliminado**; o número `CA-F002-02` foi **reatribuído** à republicação idempotente (RF-009) no backlog reescrito pelo PO. Não há RF de `403` por ownership nesta versão.
- **Edição de conteúdo (`PUT /v1/posts/{id}`, title/content):** o backlog cita edição em F002 (`CA-F002-03` fala em "editar"), mas esta versão entrega **apenas a transição de publicação**. `RF-010` cobre o caso negativo de id inexistente (`404 post_not_found`) **na rota de publicação**; a edição de campos, se necessária, entra em minor futura com seu próprio RF. _(Decisão de contrato — confirmar com PO; ver resumo.)_
- **F005 (observabilidade), F008 (guia):** Sprint 2 / recomendado. Não são RFs de comportamento de domínio do blog.
- **Semeadura de publicados para F003:** com F002 entregue, posts publicados passam a existir via `PUT /v1/posts/{id}/publish` (publicação real), não apenas via seed didático do adapter. O seed permanece válido como conveniência de teste.
- **F009 (categorias/tags), F010 (comentários):** Wont v1 (backlog §6).
