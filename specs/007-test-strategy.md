# 007 — Test Strategy (blog-tutorial)

**Status:** Vigente
**Versão:** 1.0.0
**Data:** 2026-06-24
**Responsável:** QA (Tech Lead)
**Constitution:** v1.0.0
**Relacionado a:** `specs/backlog-blog-tutorial.md` (F001, F003, F007) · `specs/adr/ADR-0001-stack-python-backend-angular-frontend.md` · `specs/adr/ADR-0002-paginacao-keyset-vs-offset.md`

> A especificação é a fonte da verdade (P-02). Esta estratégia define a **pirâmide**, os **quality gates** e o **mapa CA→teste** do blog-exemplo. Os números de P-07 são **pisos**; aqui o QA ajusta para cima. Ver `docs/lessons/qa.md`.
>
> **Escopo da Sprint 1: backend-only (FastAPI).** O frontend Angular entra depois. Por isso o **gate ATIVO nesta sprint é só o do backend Python** (pytest + cobertura). Contract test cross-language e E2E Playwright estão registrados como **estratégia futura** (§6) — mencionados para o exemplo ensinar a costura, **sem** gate ativo agora.
>
> **Princípio-guia: enxuto e didático.** O objetivo é o dev-aprendiz ver os gates funcionando — pirâmide, onde mora o ratchet, teste HTTP real que cobre o wiring de DI, e a regressão nascendo vermelha (red-green) — sem inflar a suíte.

---

## 1. Pirâmide de testes (backend Sprint 1)

A pirâmide é **respeitada de propósito**: muitos unit baratos e determinísticos na base, alguns integration HTTP no meio, e E2E só quando o front existir (topo vazio na Sprint 1).

| Nível | Escopo no blog | Ferramenta | Proporção alvo | Sprint 1 |
|---|---|---|---|---|
| **Unit** | Domínio puro: regra de idempotência (mesma key → mesmo id, sem efeito duplicado), validação de post, filtro publicado×rascunho, codificação/decodificação do cursor keyset | `pytest` (+ `hypothesis` opcional para o cursor) | maioria | **Ativo** |
| **Integration (HTTP real)** | Endpoints `POST /v1/posts` e `GET /v1/posts` batidos via `TestClient` da app montada — cobre roteamento, dependency de `Idempotency-Key`, serialização Pydantic, *Problem Details* (RFC 9457) e o **wiring de DI** | `pytest` + `fastapi.TestClient` + adapter in-memory/SQLite (didático) | alguns | **Ativo** |
| **E2E** | Fluxo do usuário ponta-a-ponta no browser (ex.: criar post → aparecer na listagem) | `Playwright` | poucos (1–2) | **Futuro** — só quando o Angular entrar (§6) |

**Por que o integration HTTP real é inegociável (qa.md "rota nova sem teste HTTP real"):** testar só o handler/serviço por baixo **não** exercita middleware, resolução de `Depends`, auth e serialização. Toda rota nova bate no endpoint de verdade com a app montada — é assim que o teste **cobre o wiring de DI de produção** (ADR-0001 §5; qa.md "execução tem de cobrir o wiring").

**Mock só nas bordas, nunca no miolo.** O adapter de persistência (in-memory/SQLite didático) é a única borda dublada; a regra de idempotência, o filtro de visibilidade e a paginação keyset — a lógica sob teste — **nunca** são mockados.

---

## 2. Quality gates (Sprint 1: só backend Python)

| Gate | Regra | Onde roda |
|---|---|---|
| **Cobertura (ratchet)** | Pisos por categoria (§3); branch coverage onde há decisão; **só sobe** (ver abaixo) | CI (job Python) |
| **Determinismo / flaky** | Zero tolerância; flaky = **P1**. Suíte passa sob `pytest-randomly` (qualquer ordem) e sem rede externa | CI |
| **Skip = falha de integração** | Dependência de integração ausente em CI **falha** (`pytest.fail`), **não** `skip` — skip mascara "integração não rodou" → falso-verde | CI |
| **Lint/format** | `ruff` **pinado** na versão do CI (`.pre-commit-config.yaml`) | pre-commit + CI |
| **Typecheck** | `mypy` no domínio/aplicação | CI |
| **Secret-scan** | Bloqueante, sobre o repo inteiro (P-10) | CI |
| **Mutation (didático)** | `mutmut` sobre o módulo de idempotência e o cursor keyset — mede **força do assert**, não cobertura. Alvo nesta sprint: nightly/sob-demanda, não bloqueante (evita inflar) | nightly/local |

### O que é o gate ratchet (didático — alvo de M4)

> **Ratchet** = catraca. O piso de cobertura **só sobe, nunca desce**. Cada entrega que adiciona testes **eleva** o piso para o novo patamar atingido; uma entrega futura que apague testes e derrube a cobertura abaixo desse piso **reprova o CI**. Rebaixar o piso é uma decisão registrada (ADR), nunca um ajuste silencioso para "fazer o CI passar" (qa.md "ratchet"; P-07).
>
> **Prove que o gate morde:** derrube a cobertura de propósito (apague um assert/teste) → o CI **tem** que ficar vermelho. Um ratchet que não reprova quando a cobertura cai é teatro.

### Ratchet **por stack**, nunca média global (inegociável do ADR-0001 §4.1)

Quando o Angular entrar, haverá **dois ratchets independentes** (pytest `--cov` de um lado, `ng test`/Vitest do outro), barrados **separadamente** no CI com **gate AND** (merge bloqueia se qualquer lado reprovar). **Proibida média global combinada** — ela mascara um lado fraco (back 95% + front 40% ≈ 78% "verde" com metade descoberta). É falso-verde estrutural. Na Sprint 1 só existe o ratchet do backend — mas a regra fica registrada para não ser violada quando o segundo job nascer.

---

## 3. Pisos de cobertura por categoria de risco (P-07 aplicado ao blog)

Pisos **bloqueantes** (floor), não metas. QA ajustou para cima onde o risco didático manda. Branch coverage exigido nas categorias com decisão.

| Categoria de risco (P-07) | Área no blog | Piso (linha) | Branch | Exigência extra |
|---|---|---|---|---|
| **Idempotência** | Regra de `Idempotency-Key` em `POST /v1/posts` (CA-F001-02, CA-F001-04) | **100%** das rotas de escrita | 100% dos branches | Teste do **estado/efeito** (slot de idempotência), não só do status HTTP |
| **Domínio crítico** | Máquina de status (rascunho→publicado), validação de post, codec do cursor keyset | **≥ 90% linha + 100% branches críticos** | crítico = 100% | Asserts fortes sobre valor (não `is not None`) |
| **API pública** | `POST /v1/posts`, `GET /v1/posts` | **100% dos endpoints** com teste de contrato | — | Cada endpoint tem ≥1 teste HTTP real que valida o **schema da resposta** |
| **Isolamento / autorização** | Rascunho **não** aparece ao público (CA-F003-02) | **100% dos cenários** de isolamento | 100% | Teste **negativo**: anônimo não recebe rascunho (allowlist, não marker) |
| **Falha explícita (P-11)** | `422` validação (CA-F001-03), `400` idempotency_key_required (CA-F001-04) | 100% dos branches de erro | 100% | Erro **tipado** (RFC 9457) com o campo/código certo asseverado |

> **Branch sem teste é onde a assimetria nasce** (qa.md): cada branch de erro/edge-case do blog tem ≥1 teste. O caminho-feliz coberto e o branch de erro descoberto é exatamente o gap que a categoria "Falha explícita" fecha.

**Visibilidade publicado×rascunho (CA-F003-02) é tratada como isolamento de autorização (P-04), não como "filtro cosmético"** — por isso entra na linha 100%, com teste negativo explícito.

---

## 4. Mapa CA→teste (F001 e F003)

Regra (P-02 + P-13.2): **todo CA vira ao menos um teste que falharia se o CA fosse violado.** CAs negativos (CA-F001-03, CA-F001-04, CA-F003-02) são cobertos **explicitamente** — são onde o falso-verde costuma se esconder.

### F001 — Criar post com idempotência

| CA | Cenário | Nível | Asserção que **prova** (não só status) | Anti-falso-verde ancorado |
|---|---|---|---|---|
| **CA-F001-01** | Criação bem-sucedida (201) | Integration HTTP | `201` **E** corpo com `id` **E** `status == "rascunho"`; post persistido e legível | Asserta valor do corpo + estado persistido, não só `201` |
| **CA-F001-02** | Retry com mesma key não duplica (P-03) | Integration HTTP + Unit | 2ª chamada com `K1` → `200/201 idempotente` **E** mesmo `id` da 1ª **E** **contagem de posts não muda** (1, não 2) | Asserta o **efeito persistido** (count), não só o status; mutation sobre o módulo de idempotência |
| **CA-F001-03** (negativo) | Payload sem título → 422 (P-11) | Integration HTTP | `422` **E** corpo *Problem Details* com `validation_error` apontando o campo `title` | Asserta o **código tipado e o campo**, não só `422`; input válido o suficiente p/ alcançar o validador certo |
| **CA-F001-04** (negativo) | Sem header de idempotência → 400 (P-03) | Integration HTTP | `400` **E** corpo com `idempotency_key_required` **E** **nenhum post criado** | Asserta status mapeado **+ efeito** (count==0); a guarda de idempotência roda, não é curto-circuitada |

> **CA-F001-04 é o caso onde o status raso engana:** confirmar só `400` não prova que nada foi persistido. O assert crítico é `count == 0` **depois** da chamada — é o efeito de estado que a qa.md exige ("assertar o STATUS não pega bug de ESTADO").

### F003 — Listar posts publicados com paginação (keyset/cursor — ADR-0002)

| CA | Cenário | Nível | Asserção que **prova** | Anti-falso-verde ancorado |
|---|---|---|---|---|
| **CA-F003-01** | Lista paginada (`limit=10` sobre 25 publicados) | Integration HTTP | `200` **E** exatamente **10 itens** **E** presença de `cursor`/`next` | Asserta o **absoluto** (`len == 10`) antes do relativo (qa.md "lote homogêneo") |
| **CA-F003-02** (negativo) | Rascunhos não aparecem ao público (P-04) | Integration HTTP | 3 rascunhos + 2 publicados → resposta contém **exatamente os 2 publicados**; nenhum rascunho vaza | **Allowlist, não marker**: asserta a lista filtrada (200 com 2), não "404 no rascunho"; isolamento de autorização |
| **CA-F003-03** | Página seguinte via cursor é estável | Integration HTTP + Unit | 2ª página via `cursor=C1` retorna os seguintes **sem repetir** os já vistos; ids da pág.1 ∩ pág.2 = ∅ | Unit do codec do cursor cobre a **fronteira** (último item da página); sem dependência de ordem de inserção implícita |

> **CA-F003-02 é o gate de vazamento de dados entre estados.** Confundir "marker" (404 ao pedir um rascunho) com "allowlist" (lista pública já filtrada) mascara vazamento (qa.md "marker vs allowlist"). O teste asserta a **lista filtrada**, provando que o rascunho nunca entrou na resposta.

**Cobertura dos CAs negativos é obrigatória:** CA-F001-03, CA-F001-04 e CA-F003-02 têm teste dedicado acima — nenhum deles é coberto "de raspão" por um caminho-feliz.

---

## 5. Anti-falso-verde — checklist bloqueante (da qa.md)

Aplicado a toda PR da Sprint 1. Um item não-atendido **barra a entrega**.

- [ ] **Rota nova tem teste HTTP real** (`TestClient`), não só unit do handler — cobre middleware, `Depends`, serialização.
- [ ] **Execução cobre o wiring de DI de produção** — a app é montada como em produção; colaboradores não são injetados à mão para "facilitar".
- [ ] **`fail`, não `skip`, quando dependência de integração ausente** — skip alto = integração não rodou = falso-verde de cobertura.
- [ ] **Assert sobre estado/efeito, não só status HTTP** — idempotência prova `count`; rejeição prova "nada persistido".
- [ ] **Regressão nasce vermelha (red-green)** — todo bug corrigido começa por um teste que falha **antes** do fix e passa depois. É a DoD do fix.
- [ ] **Mutation-âncora onde importa** — reverter o fix de idempotência/filtro **tem** que deixar o teste vermelho; a mutação ataca a invariante que o teste **alega** proteger, não uma vizinha.
- [ ] **Negativo com input válido-o-suficiente** — o teste negativo alcança o mecanismo alvo (sem um guard adjacente matar a mutação antes).
- [ ] **Suíte completa antes de declarar pronto** — `-k feature` não pega regressão transversal; roda o espelho de CI inteiro sob `pytest-randomly`.
- [ ] **Allowlist, não marker** em visibilidade pública (CA-F003-02).
- [ ] **Determinismo** — sem `now()`/`random` sem controle; sem `sleep` para sincronizar; passa em qualquer ordem.

---

## 6. Estratégia futura — costura cross-stack (NÃO ativa na Sprint 1)

Registrada para o exemplo **ensinar a costura** do polyglot, sem ativar gate agora. Nasce quando o Angular entrar (Sprint 2+).

- **Contract test derivado de schema único (ADR-0001 §4.2 — inegociável quando o front existir).** Os tipos e mocks do front são gerados/validados a partir do **mesmo** OpenAPI de `005-api-contract.md`. Mutar um campo no back **tem** que deixar o contract test vermelho — senão é teatro. É a trava anti-drift do polyglot. *Na Sprint 1 há um só lado: o contrato vive no OpenAPI gerado pelo FastAPI (`/docs`), e os testes HTTP de §4 já validam a resposta contra esse schema.*
- **Segundo ratchet (front), barrado separadamente.** `ng test`/Vitest com piso próprio; **gate AND** com o ratchet Python; **nunca** média global (§2).
- **E2E Playwright — 1–2 fluxos críticos** (ex.: criar post → aparecer na listagem), não cobertura exaustiva (ADR-0001 §4 "magro de propósito").
- **Idempotência: conflito de payload (`409`).** O template P-07 cita "payload divergente → 409"; os CAs atuais do blog (CA-F001-02) cobrem só o **retry idêntico**. Caso o backlog evolua para idempotência forte (mesma key + payload diferente → `409 conflict`), o cenário e o teste entram aqui — **não inventado agora** para não exceder os CAs aprovados.

---

## 7. Matriz de risco × cobertura (resumo)

| Risco / Invariante | Severidade | Tipo de teste | CA | Status Sprint 1 |
|---|---|---|---|---|
| Efeito duplicado por retry (idempotência) | Alto | Integration HTTP + Unit + mutation | CA-F001-02 | Ativo |
| Escrita sem chave de idempotência aceita | Alto | Integration HTTP (efeito: count==0) | CA-F001-04 | Ativo |
| Vazamento rascunho→público (autorização) | Máximo | Integration HTTP (allowlist) | CA-F003-02 | Ativo |
| Falha silenciosa em payload inválido | Médio | Integration HTTP (Problem Details tipado) | CA-F001-03 | Ativo |
| Paginação instável (repetição/perda de item) | Médio | Integration HTTP + Unit (codec, fronteira) | CA-F003-03 | Ativo |
| Contract drift back↔front | Alto | Contract test (schema único) | — | **Futuro** (§6) |
| Fluxo ponta-a-ponta quebrado | Médio | E2E Playwright | — | **Futuro** (§6) |

---

## 8. DoD desta spec (conforme `specs/README.md` §"Definição de pronto por spec")

1. [x] Versão ≥ 1.0.0 → **1.0.0**.
2. [x] Sem ambiguidades não documentadas — o gap "409 de payload divergente" está explicitado como estratégia futura (§6), não omitido.
3. [x] Toda referência cruzada resolve — backlog (F001/F003), constitution (P-02/04/07/10/11/13), ADR-0001 (§4.1/§4.2/§5), qa.md, README. *Nota:* `ADR-0002` está em redação em paralelo (referência forward declarada).
4. [x] Todo CA é executável — §4 mapeia CA-F001-01..04 e CA-F003-01..03 a testes com asserção que falha se o CA for violado.
5. [ ] Aprovação cruzada (PO + QA responsável + ≥1 par, ex.: `tl-python`) — pendente de assinatura no review-loop.

---

## 9. Histórico de versões

| Versão | Data | Autor | Mudança |
|---|---|---|---|
| 1.0.0 | 2026-06-24 | QA (Tech Lead) | Estratégia inicial do blog-tutorial — Sprint 1 backend-only: pirâmide, ratchet por-stack, pisos P-07, mapa CA→teste (F001/F003), anti-falso-verde, costura cross-stack como futuro. |
