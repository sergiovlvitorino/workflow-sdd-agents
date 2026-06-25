# DETAIL — T-S2-08 — Plano de testes de F002 (publicar) e F004 (ler por id)

**Sprint:** 02
**Tamanho:** L _(estimativa)_
**Papel:** QA (`qa` / `spec-qa`) + TL revisão (`tl-qa` + `tl-python`)
**Depende de:** T-S2-04 (adapter `SqlitePostRepository` + `SqliteIdempotencyStore`; `get(id)` na porta; **factory `create_app(*, repo, idem)` parametrizável** — `main.py` §4.6), T-S2-05 (`Post.publish(now)` + caso de uso `PublishPost` + `PostNotFound`), T-S2-06 (`PUT /v1/posts/{id}/publish` + `handle_post_not_found`), T-S2-07 (`GET /v1/posts/{id}` — read-by-id indistinguível)
**Bloqueia:** T-S2-09 (gate ratchet — o novo piso só sobe depois que estes testes existem e medem)

> Produzido por `tl-qa` no sprint-flow (detalhamento técnico); consumido pelo `review-loop` (implementação + revisão). Descreve a tarefa no presente — o status real vive no board, não aqui. Realiza o **mapa CA→teste** da Sprint 2 (extensão de `007-test-strategy.md` §4), com a **asserção que morde** e a **mutation-âncora** cravadas por CA (ADR-0003 §8, ADR-0004 §8).

---

## 1. Objetivo

Cravar, por CA de F002/F004, a **asserção que falharia se o CA fosse violado** e a **mutation-âncora** que prova que o teste morde pelo motivo certo — fechando os pontos vinculantes dos painéis: idempotência em dois níveis (por estado + `Idempotency-Key`), durabilidade entre conexões do SQLite, suíte de contrato de porta parametrizada nos 2 adapters, e teste HTTP real que cobre o **wiring de DI de produção** com SQLite. Esta tarefa **especifica o plano**; a escrita dos testes ocorre no `review-loop`.

## 2. CAs / RNs cobertos

- **CA-F002-01 (RF-008, ADR-0004 §4):** publicar `draft` → `200`, `status="published"`, `published_at` preenchido, estado persistido.
- **CA-F002-02 (RF-009, P-03, ADR-0004 §8):** republicar `published` → no-op idempotente; `published_at` **inalterado**; sem duplicar transição (relógio congelado/injetado).
- **CA-F002-03 (RF-010, P-11, ADR-0004 §8):** publicar id inexistente → `404 post_not_found` tipado **e nada publicado**; ausência de `Idempotency-Key` → `400 idempotency_key_required`.
- **CA-F004-01 (RF-011):** `GET /v1/posts/{id}` de post publicado → `200` com o `Post`.
- **CA-F004-02 (RF-011, P-04, ADR-0004 §8):** `GET /v1/posts/{id}` de rascunho **ou** inexistente → `404 post_not_found` **indistinguível** (mesmo `type`/`status`/`title`); não vaza existência.
- **Transversais (ADR-0003 §8):** suíte de contrato de porta parametrizada (`InMemory` × `Sqlite`); durabilidade entre conexões em arquivo; ≥1 integração HTTP com app montada sobre SQLite (wiring de produção); replay idempotente contra `SqliteIdempotencyStore` real.

## 3. Arquivos a criar/alterar

| Path | Ação | Descrição |
|---|---|---|
| `backend/tests/integration/test_publish_post_http.py` | criar | HTTP real (`TestClient`) dos CA-F002-01/02/03 + idempotência em 2 níveis + asserção de estado persistido. |
| `backend/tests/integration/test_read_post_by_id_http.py` | criar | HTTP real dos CA-F004-01/02; indistinguibilidade rascunho×inexistente. |
| `backend/tests/integration/test_publish_post_sqlite_http.py` | criar | ≥1 integração HTTP **com a app montada sobre `SqlitePostRepository`/`SqliteIdempotencyStore`** (wiring de produção real — ADR-0003 §8). Publicar → durabilidade → replay. |
| `backend/tests/unit/test_publish_post_usecase.py` | criar | Unit de `PublishPost` com fakes: idempotência por estado, transição inválida, replay por chave. |
| `backend/tests/unit/test_post_publish_domain.py` | criar | Unit de `Post.publish(now)` (frozen `replace`, no-op se já published). |
| `backend/tests/contract/test_post_repository_contract.py` | criar | **Suíte de contrato de porta parametrizada** (`pytest.fixture(params=["in_memory","sqlite"])`) rodando os mesmos casos nos 2 adapters. |
| `backend/tests/contract/test_idempotency_store_contract.py` | criar | Contrato parametrizado do `IdempotencyStore` (get/put, formato persistido, replay → `count==1`). |
| `backend/tests/conftest.py` | criar/alterar | Fixtures: `frozen_clock`, `sqlite_db_path` (`tmp_path`, **nunca `:memory:`**), `app_factory(adapter=...)`, parametrização dos adapters. |

## 4. Design da solução — asserção-âncora × mutation por CA

> Convenção: **A** = asserção que morde (falha se o CA for violado); **M** = mutation-âncora (reverter o fix de produção → este teste **tem** que ficar vermelho). Toda âncora segue `docs/lessons/qa.md`: assertar **estado/efeito**, não só status; input válido-o-suficiente para alcançar o mecanismo; mutação ataca a invariante **alegada**, não a vizinha.

### CA-F002-01 — publicar `draft` → `200` + `published_at` preenchido + estado persistido (Integration HTTP)

- **Setup:** cria post via `POST /v1/posts` (status `draft`, `published_at == null`); relógio congelado em `T_pub`.
- **A1 (status + corpo):** `PUT /v1/posts/{id}/publish` → `200`; corpo `status == "published"`; `published_at == T_pub` (valor exato em RFC 3339 UTC `Z`, **não** `is not None`).
- **A2 (estado persistido, não só resposta):** reler via `GET /v1/posts/{id}` → `200` com `status == "published"` e o **mesmo** `published_at`. Provar que a transição foi gravada, não só serializada na resposta (`qa.md`: "status não pega bug de estado").
- **M1:** se `PublishPost` montar a resposta sem persistir (`repo.add`/`update` removido) → A2 vermelho (read-by-id ainda vê `draft`/`404`).
- **M2:** se `Post.publish` não setar `published_at` (deixar `None`) → A1 vermelho.

### CA-F002-02 — republicar `published` é no-op idempotente (Integration HTTP + Unit) — **a âncora central de F002**

- **Setup:** publica em `T1` (relógio congelado); **avança o relógio** para `T2 != T1`; republica.
- **A3 (`published_at` inalterado — valor exato):** após a 2ª publicação, `published_at_2 == published_at_1 == T1` (**não** `T2`). Relógio congelado/injetado torna o assert determinístico (`qa.md`: injetar o relógio, congelar no teste).
- **A4 (sem duplicar transição / efeito):** contagem de publicados **não muda** entre a 1ª e a 2ª publicação (`repo.list_published` ou contador de publicados estável); `status` segue `published`. Asserir o **efeito**, não só `200`.
- **A5 (replay por `Idempotency-Key` — 2º nível):** repetir o `PUT` com a **mesma** `Idempotency-Key` e mesmo recurso → `200` **+ header `Idempotent-Replayed: true`**, corpo idêntico ao original. (No-op por estado **e** replay por chave são camadas distintas — ADR-0004 §8; `005` §2.3.)
  > **⚠ Divergência a resolver no review-loop (não rebaixar em silêncio):** o DETAIL-T-S2-06 §4.2 escolheu a **opção A** — exigir o header mas **não emitir `Idempotent-Replayed: true`** (apoia-se só no no-op por estado). O contrato `005` §2.3 e ADR-0004 §8 descrevem o header como o **2º nível** do piso P-03. **A5 (e M4/C7) ficam como condição dura**; se o PO/`tl-qa` ratificarem a opção A de T-S2-06, A5/M4 viram `xfail-strict` com issue de débito rastreado (gate temporal — `qa.md`), **nunca** removidos. Decisão registrada no PR antes de marcar verde. Comportamento end-to-end por estado (A3/A4) é inegociável de qualquer forma (RF-009).
- **M3 (mutation-âncora do ADR-0004 §8):** remover a guarda de no-op (re-setar `published_at` **incondicionalmente** a `now()` na republicação) → A3 vermelho (`published_at_2 == T2 != T1`). Esta é a mutação que o painel exigiu.
- **M4:** ignorar/parar de honrar `Idempotency-Key` no replay (nunca emitir `Idempotent-Replayed`) → A5 vermelho. _(Inerte se a opção A de T-S2-06 for ratificada — ver ⚠ acima.)_
- **Anti-falso-verde do fake (Unit):** o fake do repositório/store **deve retornar o `Post` com `status=published` e `published_at=T1`** quando consultado — um fake que devolve `None` curto-circuita a guarda `if post.status is PUBLISHED:` e deixa M3 inalcançável (`qa.md`: "fake que retorna None curto-circuita o guard").

### CA-F002-03 — publicar inexistente → `404` tipado + nada publicado; sem chave → `400` (Integration HTTP)

- **A6 (404 tipado):** `PUT /v1/posts/{id-inexistente}/publish` (com `Idempotency-Key` válida) → `404`; corpo `application/problem+json` com `type` sufixo `post_not_found`, `status == 404`. Asserir o **code tipado**, não só `404`.
- **A7 (nada publicado — efeito):** após a chamada, a contagem de publicados é **a mesma de antes** (`== N`, valor absoluto) e nenhum post novo foi criado (`repo.count()` inalterado). `qa.md`: status raso não prova que nada foi persistido.
- **A8 (piso P-03 — sem chave → 400):** `PUT /v1/posts/{id}/publish` **sem** header `Idempotency-Key` → `400` `idempotency_key_required` **e nada publicado** (post-alvo segue `draft`). Input com id **existente e válido** (válido-o-suficiente) para que, removida a guarda de chave, o fluxo **alcance** a transição — senão a mutação fica inerte (`qa.md`: guard adjacente mata a mutação).
- **M5:** remover a dependency `require_idempotency_key` da rota de publish → A8 vermelho (publica sem chave / não retorna `400`). Teste HTTP: `test_publish_without_idempotency_key_returns_400` em `tests/integration/test_publish_http.py` (NÃO um teste de domínio/unit — M5 morde no wiring de DI da rota).
- **M6:** mapear transição inválida para `200`/`500` em vez de `404 post_not_found` → A6 vermelho.

### CA-F004-01 — read-by-id de post publicado → `200` (Integration HTTP)

- **A9:** publica um post; `GET /v1/posts/{id}` → `200`; corpo valida o schema `Post` (`005` §3) com `status == "published"` e `published_at` preenchido (valor exato do que foi publicado, não `is not None`).
- **M7:** filtro de visibilidade do read-by-id invertido (só devolve `draft`) → A9 vermelho.

### CA-F004-02 — rascunho **ou** inexistente → `404` indistinguível; não vaza (Integration HTTP) — **gate de vazamento**

- **A10 (rascunho):** cria post (`draft`, **não** publica); `GET /v1/posts/{id}` → `404`; corpo `post_not_found`.
- **A11 (inexistente):** `GET /v1/posts/{id-inexistente}` → `404`; corpo `post_not_found`.
- **A12 (indistinguibilidade — a âncora):** as respostas de A10 e A11 são **idênticas** em `status`, `type` e `title` (comparar os 3 campos campo-a-campo). É o teste **negativo** de visibilidade exigido por ADR-0004 §8: rascunho não vaza nem por id (allowlist, não marker — `qa.md`).
- **A13 (não vaza na lista também):** o rascunho de A10 **não** aparece em `GET /v1/posts` (allowlist por valor; nenhum `id` de rascunho na resposta).
- **M8 (mutation-âncora de vazamento):** fazer o read-by-id devolver o rascunho (`200`) **ou** diferenciar rascunho (`403`/`404` com `type` diferente) de inexistente → A12 vermelho. Diferenciar = vazar existência.

### Transversais (condições de aceite ADR-0003 §8)

**Suíte de contrato de porta parametrizada** (`test_post_repository_contract.py`, `params=["in_memory","sqlite"]`):

- **C1 (mesma sequência de ids):** `add` de N posts com ids fixos → `list_published` devolve a **mesma ordem `(published_at DESC, id DESC)`** nos 2 adapters (lista de ids idêntica). Asserir o **absoluto** (`len == N_publicados`) antes do relativo (`qa.md`: lote homogêneo).
- **C2 (mesmo `count()`):** após a mesma sequência de escritas, `repo.count()` idêntico nos 2 adapters.
- **C3 (keyset estrito):** com `published_at` empatado e `id` distinto, a página seguinte **não repete a fronteira** nos 2 adapters.
- **C4 (transição persistida):** publicar um post (via `Post.publish` + `add`/`update`) e reler → `status=published`, `published_at=T1` nos 2 adapters.
- **M9 (mutation-âncora do keyset SQLite — ADR-0003 §8):** `<` → `<=` no `WHERE (published_at, id) < (?, ?)` do adapter SQLite **duplica a fronteira** → C3 vermelho **no parâmetro `sqlite`** (e equivalente no in-memory: `<` → `<=` na comparação de tuplas).

**Durabilidade entre conexões** (`tests/integration/test_sqlite_durability.py`, só `sqlite` — o arquivo-âncora de durabilidade já é entregável de T-S2-04; este DETAIL crava as asserções):

- **C5:** escrever com uma instância de `SqlitePostRepository` apontando para `sqlite_db_path` (arquivo em `tmp_path`); **fechar**; abrir **nova** instância no **mesmo arquivo**; `list_published`/read devolve o que foi escrito. **Nunca `:memory:`** (uma conexão `:memory:` perde tudo ao fechar e mascara a feature — ADR-0003 §8). É a feature-âncora do ADR.
- **M10:** se o adapter não fizer `commit` (ou usar `:memory:` por engano) → C5 vermelho na 2ª conexão.

**Replay idempotente contra o `SqliteIdempotencyStore` real** (`test_idempotency_store_contract.py`):

- **C6:** `put(key, hash, resp)` e depois `get(key)` numa **nova conexão** → devolve `(hash, resp)` com o **formato persistido** exercitado (serialização JSON da coluna), não um dublê em dict. `count` de slots == 1 após replay (`qa.md`: "fake que espelha o contrato mas não o caminho" — exigir store real).
- **C7 (HTTP, wiring de produção — `test_publish_post_sqlite_http.py`):** app montada sobre adapters SQLite via a factory parametrizável de T-S2-04 (`create_app(repo=SqlitePostRepository(conn), idem=SqliteIdempotencyStore(conn))`, `conn` sobre `sqlite_db_path`); publicar; repetir o `PUT` com a **mesma chave** → `200` (+ `Idempotent-Replayed: true` **se** a opção B de T-S2-06 for adotada — ver ⚠ em CA-F002-02), **1** slot de idempotência no DB, `count()` de posts inalterado. Cobre o **wiring de DI de produção** (não os fakes) — sem isso os testes exercitam um wiring que não é o de produção (falso-verde estrutural, ADR-0003 §8 / `qa.md`). _Nota: a contagem de slots/`count()` inalterado é inegociável independentemente do header._
- **M11:** quebrar a unicidade/atomicidade da idempotência no adapter SQLite (replay regrava/recria) → C7 vermelho (2 slots ou `count` duplicado).

## 5. Impacto em testes e quality gates

- **Testes novos:** unit (domínio `Post.publish` + `PublishPost`), integration HTTP (publish, read-by-id, publish-sobre-SQLite), contract parametrizado (repo + idempotency store). Pirâmide respeitada: base unit, meio integration, sem E2E (front ainda fora — `007` §1).
- **Cobertura esperada (P-07 aplicado, sem diluir — detalhado em T-S2-09):**
  - **API pública:** `PUT /v1/posts/{id}/publish` e `GET /v1/posts/{id}` = 100% dos endpoints com teste de contrato (`007` §3).
  - **Domínio crítico** (máquina de estados `Post.publish`): ≥ 90% linha + 100% branch crítico (a guarda de no-op é branch crítico).
  - **Idempotência:** 100% da rota de escrita de publish (estado + chave).
  - **Isolamento/autorização** (read-by-id rascunho×inexistente; rascunho fora da lista): 100% dos cenários, com teste **negativo**.
  - **Falha explícita:** branches `404 post_not_found` e `400 idempotency_key_required` cobertos com erro **tipado** asseverado.
  - **Adapters** (`SqlitePostRepository`/`SqliteIdempotencyStore`): piso **próprio** ≥ 80% + contract tests (P-07 "Integrações/adapters"), **não diluído na média global** (T-S2-09 define como medir por-categoria).
- **Gates afetados:** ratchet backend sobe (T-S2-09); `--cov-branch` permanece; suíte passa sob `pytest-randomly`; **`fail`, não `skip`** se faltar a variante SQLite (não há infra externa → não há justificativa para skip — `007` §2; `qa.md`).
- **Mutation (didático):** M3 (no-op publish) e M9 (`<`→`<=` keyset SQLite) entram no alvo de `mutmut` nightly/sob-demanda junto com o módulo de idempotência já existente.

## 6. Riscos

- **Flaky por relógio real:** `published_at` comparado por valor exige relógio **injetado e congelado** (`frozen_clock`); a republicação **avança** o relógio para `T2` deliberadamente, provando que o no-op ignora o tempo novo. Nunca `datetime.now()` no teste ou no domínio (`qa.md`: `now()` na lógica = teste frágil; ADR-0004 §8: `now` injetado).
- **Falso-verde de wiring (o maior risco da tarefa):** testar publish/replay só contra fakes não cobre o caminho de produção SQLite. Mitigação: C5/C6/C7 exercitam o **store/recurso real** e a **app montada sobre SQLite** (ADR-0003 §8). Um fake que guarda a resposta numa chave conveniente passa verde enquanto o formato persistido nunca roda (`qa.md`: "fake espelha o contrato mas não o caminho").
- **`:memory:` mascarando durabilidade:** uma conexão `:memory:` por engano faz C5 "passar" sem provar persistência entre conexões. Mitigação: `sqlite_db_path` em `tmp_path` obrigatório; revisão barra `:memory:` em testes de durabilidade.
- **Guard adjacente matando a mutação (A8/M5):** se o teste de "sem chave" usar id inexistente, o `404` dispara antes da guarda de idempotência e M5 fica inerte. Mitigação: id **existente e em `draft`** no teste de chave ausente.
- **Fake que retorna `None` curto-circuita M3:** o fake do `PublishPost` precisa devolver o `Post` no estado `published` para a guarda de no-op ser alcançada (`qa.md`).
- **Indistinguibilidade frágil (A12):** comparar `detail` (texto livre) acopla o teste a uma string. Mitigação: comparar apenas `status`/`type`/`title` (campos estáveis por contrato — `005` §4); `detail` não deve permitir inferir existência mas não entra na asserção de igualdade.
- **Contaminação de ambiente entre adapters:** a fixture parametrizada precisa de DB **novo por caso** (`tmp_path` por teste) e in-memory recriado — senão estado vaza entre parâmetros (`qa.md`: estado compartilhado). Não paralelizar os dois adapters sobre o mesmo arquivo (CLAUDE.md).
- **`-k publish` não pega regressão transversal:** F002 reabre `GET /v1/posts` (publicados passam a existir de verdade). Rodar a **suíte completa** sob `pytest-randomly`, não só os testes da feature (`qa.md`).

## 7. Definition of Done (verificável)

- [ ] CA-F002-01/02/03 e CA-F004-01/02 automatizados e **verdes com execução real** (`TestClient`), não só "compila".
- [ ] **CA-F002-02 prova `published_at_2 == published_at_1` (valor exato, relógio congelado, `T2` avançado)** e contagem de publicados estável (A3+A4).
- [ ] **Idempotência por estado** (no-op, A3/A4) coberta — inegociável (RF-009).
- [ ] **2º nível (`Idempotency-Key` → `Idempotent-Replayed: true`, A5)** coberto **ou** divergência com T-S2-06 §4.2 resolvida no review-loop (opção B implementada **ou** A5/M4 em `xfail-strict` com issue de débito — nunca removidos silenciosamente).
- [ ] CA-F002-03: `404 post_not_found` tipado **+ nada publicado** (A6/A7) e `400 idempotency_key_required` sem chave **+ nada publicado** (A8).
- [ ] CA-F004-02: respostas de rascunho e inexistente **idênticas** em `status`/`type`/`title` (A12) e rascunho ausente da lista (A13).
- [ ] **≥1 integração HTTP com a app montada sobre SQLite** (C7) cobrindo o wiring de DI de produção.
- [ ] **Suíte de contrato de porta parametrizada** verde nos 2 adapters (C1–C4) com mesma sequência de ids e mesmo `count()`.
- [ ] **Durabilidade entre conexões** em arquivo (`tmp_path`, nunca `:memory:`) verde (C5).
- [ ] **Replay contra `SqliteIdempotencyStore` real** com `count == 1` (C6/C7).
- [ ] Mutation-âncoras M1–M11 verificadas (reverter o fix → vermelho), com destaque para **M3** (no-op publish) e **M9** (`<`→`<=` keyset SQLite).
- [ ] Suíte completa verde sob `pytest-randomly` (qualquer ordem); zero `skip` na variante SQLite (`fail`, não `skip`).
- [ ] Cobertura ≥ pisos P-07 por categoria, **adapter com piso próprio não diluído** (medição definida em T-S2-09).
- [ ] `mypy --strict` limpo no `src/` tocado.
- [ ] Revisão aprovada (`tl-qa` + `tl-python`) sem ressalvas.
