# ADR-0007 — Claim idempotente antes de criar: contrato de concorrência de `IdempotencyStore`

**Status:** Aceito _(com condições vinculantes do painel — ver §8)_ · _(Proposto → Aceito → Substituído por ADR-XXXX | Rejeitado)_
**Data:** 2026-07-15
**Autor:** design-flow (orquestrador-sintetizador; painel `tl-python` + `tl-qa` + `fullstack-tech-lead`)
**Revisores requeridos:** Tech Lead Backend (`tl-python`) + Tech Lead QA (`tl-qa`)
**Constitution:** v1.0.0
**Relacionado a:** ADR-0003 §4.4/§8 (write-once `INSERT OR IGNORE` existente — este ADR **amenda, não substitui**) · SEC-03 em `docs/quality/hardening-baseline-2026-07.md` · `specs/tasks/sprint-04/DETAIL-T-S4-03-toctou-idempotencia-create.md` · P-03 (idempotência), P-06 (contrato extensível), P-11 (falha explícita), P-12 (reversibilidade de integração)

---

## 1. Contexto

`CreatePost.execute` é hoje um check-then-act clássico (TOCTOU): a sequência `idem.get(key) → Post.create(id_gen()) → repo.add(post) → idem.put(key, ...)` não é atômica. Duas (ou N) chamadas concorrentes com a **mesma** `Idempotency-Key` + mesmo payload atravessam `existing is None` juntas, geram ULIDs distintos, e **ambas persistem** — dois posts. O `INSERT OR IGNORE` write-once (ADR-0003 §4.4) só protege o registro **da chave**, que chega **depois** do `add`; e o UPSERT de `add` não deduplica porque os `post.id` são diferentes. Resultado: `count()==2` para uma key. Isso **viola P-03** (efeito colateral duplicado em rota de escrita) — é o único piso da constitution quebrado no baseline de hardening (SEC-03).

**Causa-raiz:** a deduplicação é tentada no lugar errado (no `add`, por PK do post — que não colapsa ULIDs distintos) e tarde demais (o claim da chave chega após o `add`). O árbitro precisa vir **antes** da criação e **decidir quem cria**. A `key` — não o `post.id` — é o identificador natural de idempotência.

**Forças em jogo:**
- **Correção sob concorrência** (fechar o TOCTOU, provado red-green) — inegociável (P-03).
- **Reversibilidade / P-12:** mudar a assinatura de uma **porta** (`IdempotencyStore`) é um evento de contrato de fronteira; qualquer adapter futuro (Redis, Postgres, DynamoDB) fica vinculado.
- **Lição hexagonal (didática):** o projeto ensina que a garantia mora no **contrato** da porta, e trocar de adapter não deve vazar para o domínio.
- **Escopo:** app didático, local, monousuário. A concorrência real é rara no runtime, mas o piso P-03 não se rebaixa por isso.

Precisa decidir **agora** porque o fix do SEC-03 (Sprint 4) não pode ser implementado sem fixar a forma do contrato da porta.

## 2. Alternativas consideradas

| Alternativa | Prós | Contras |
|---|---|---|
| **A. `put(...) -> bool` claim-first** _(escolhida)_ | Atomicidade no **único ponto** que todo backend oferece nativo (compare-and-set: SQLite `INSERT OR IGNORE`/`rowcount`, Redis `SET NX`, Postgres `ON CONFLICT`, DynamoDB `attribute_not_exists`); veredito **legível no tipo** e forçado por `mypy` em todo adapter futuro; mantém 409 explícito sob concorrência (P-11); preserva ULID não-enumerável | Muda assinatura de porta (evento P-12); in-memory ganha `threading.Lock` load-bearing; +3 ramos no use-case (cobertura) |
| **B. Contract-first (cláusula normativa + teste de conformação)** | Não é rival de A/C — é **ortogonal e complementar**: transforma "adapter DEVE ser atômico" (adjetivo) em cláusula testável (`sum(True)==1`) guardada na suíte de contrato parametrizada; impede regressão silenciosa de P-03 na troca de adapter | Sozinha não reordena o use-case; precisa de A (ou C) para o fluxo |
| **C. Read-back-compare (porta INTACTA)** | Menor superfície de reversão (reverter = 1 arquivo; porta nunca vira evento); porta permanece CRUD write-once puro; corretude comprovadamente idêntica a A | Garantia por **convenção** ("comparo ids após reler"), não legível no tipo — não "viaja" para o teste de conformação de um adapter futuro; +1 leitura no caminho vencedor; pede comentário explicativo |
| **D. `post_id` derivado da idem-key** | Mais simples (upsert convergente; sem mudança de porta; in-memory trivial) | **Regressão de segurança:** `post_id` vira função de input controlado pelo cliente → IDs **previsíveis/enumeráveis** (regride piso do baseline); embaça o 409 concorrente; funde identidade com idempotência; perde ordenação temporal do ULID |
| **E. Unit-of-work transacional (add+put numa transação)** | Fecharia o TOCTOU **e** a janela de falha parcial cross-table | Maior blast-radius; transação **sozinha não elege vencedor** (sem write-once, 2 transações leem `None` e seguem); exige emular transação/rollback no in-memory; transação cross-store acopla adapters (fere P-06/P-12). É a resposta certa para a **dívida residual** (§5), não para este fix |
| **F. Lock de aplicação no use-case** | Zero mudança de porta | Enfia `threading` na camada de aplicação (vaza infra p/ domínio — fere a lição hexagonal); inútil multi-processo/multi-instância; exige striped locks ou serializa todo create |

## 3. Critérios de decisão

| Critério | Peso | Por quê |
|---|---|---|
| Correção sob concorrência (fecha P-03, red-green) | **Alto** | É o objetivo; piso inegociável |
| Durabilidade da garantia na troca de adapter (P-12) | **Alto** | Sem isso, P-03 quebra silenciosamente num adapter futuro — o risco real de reversibilidade |
| Aderência à lição hexagonal / garantia legível no contrato | **Alto** | O projeto **ensina** isso; a decisão é material didático |
| Reversibilidade / blast-radius | Médio | Mudar porta é evento P-12, mas o `put` tem **um único chamador** — churn contido |
| Simplicidade (KISS) | Médio | Educacional; não inflar |
| Não regredir propriedades de segurança (ULID não-enumerável) | **Alto** | Piso listado no baseline |

## 4. Decisão

**Escolhida: Alternativa A — `IdempotencyStore.put(key, payload_hash, response_json) -> bool` (claim-first), enxertada com a Alternativa B (cláusula normativa + teste de conformação parametrizado) como parte vinculante.**

`put` deixa de retornar `None` e passa a retornar o **veredito do claim write-once**: `True` sse *esta* chamada foi a que materializou o registro da `key`; `False` se a key já existia. Não é responsabilidade nova — é **parar de descartar** a informação que o `INSERT OR IGNORE` já computa (`rowcount`). O use-case reordena para **claim-antes-de-criar**: monta o candidato, disputa o `put`, e **só o vencedor faz `repo.add`**; o perdedor lê o vencedor e faz replay (mesma payload) ou levanta `IdempotencyConflict` → 409 (payload divergente, P-11).

**Por que A vence pelos critérios (síntese do painel):**
- O argumento **decisivo é o de B**: num projeto que ensina "a garantia mora no contrato", o veredito precisa ser **legível no tipo E testável na fronteira**. O read-back-compare (C) esconde a garantia numa convenção do use-case que **não viaja** para o teste de conformação de um adapter futuro — exatamente a regressão silenciosa que P-12 quer impedir.
- A atomicidade fica no **único ponto** que Redis/Postgres/DynamoDB oferecem como primitiva nativa (compare-and-set). Um contrato que separa "reivindicar" de "gravar" (ex.: método `claim()` + `put()`) **reintroduz o TOCTOU** — luta contra a primitiva nativa.
- Rejeita D (regressão de enumerabilidade de ID), E/F e o `claim()` aditivo (deixaria `put` órfão).

**Inegociável (o que dela é contrato, não detalhe):**
- A garantia de claim atômico write-once é do **contrato da porta** (§8, cláusula C-1..C-5), não de um adapter específico. Cada adapter a implementa com seu mecanismo.
- Nenhum adapter de `IdempotencyStore` entra na suíte sem passar o **teste de conformação parametrizado** (`TestIdempotencyClaimContract`) — o portão executável que torna a cláusula um piso, não prosa.
- `PostRepository.add` **não** muda (segue UPSERT idempotente; apenas deixa de ser, indevidamente, o ponto de dedup de criação).

**Sub-questão de nomenclatura (registrada):** considerou-se renomear `put → claim`/`put_if_absent` para tornar o veredito óbvio no nome. **Rejeitado:** `put` já carrega a semântica write-once desde ADR-0003 §4.4; o `-> bool` só expõe o veredito existente; o churn do rename na suíte de contrato parametrizada e em `test_put_is_write_once_idempotent` não compensa. Mitigação: docstring/Protocol explícito ("retorna `True` sse esta chamada gravou o write-once").

## 5. Consequências

- **Positivas:** fecha o TOCTOU (P-03) nos dois adapters, provado red-green; a garantia de concorrência vira contrato de porta **testável** que sobrevive à troca de adapter (P-12 concreto, não nota no ADR); ensina o padrão industrial "claim antes de agir"; preserva ULID opaco/temporal.
- **Negativas / custo assumido:**
  - **Evento de contrato de porta (P-12):** `put -> bool` propaga ao Protocol + 2 adapters + `mypy --strict` no `src/` inteiro. Blast-radius **contido** (um único chamador de produção: `create_post.py`), mas real. Alternativa de menor superfície de reversão (C, read-back-compare) foi **conscientemente preterida** em favor da legibilidade-no-contrato.
  - **In-memory ganha `threading.Lock`** load-bearing (sem ele o check-and-set não é atômico e o bool mente sob corrida). **Correto por construção; não-ancorável pela suíte threaded sob CPython-GIL** — a corrida mora *dentro* do check-and-set do `put`, e o GIL não a interleava sem I/O; demonstrado load-bearing por sonda de corrida forçada (sleep injetado → sem lock, N/N threads retornam `True`), não pela suíte padrão. Ver §8.5.
  - **Dívida residual conhecida (crash-atomicity cross-table):** entre o claim (`put`) e o `add` do vencedor há uma janela — falha do `add`/processo deixa a chave reivindicada apontando para um post inexistente (replays devolvem resposta consistente para recurso não persistido). **Não é regressão** — inverte a janela pré-existente (hoje: post órfão sem chave) para a direção **auto-consistente sob replay e que não viola P-03**. P-11 é preservado no caminho que importa (falha do `add` **propaga**, não vira 201 mentiroso). Fechamento definitivo exige unit-of-work transacional cross-store, que acopla **SEC-06** e um ADR de transação/outbox próprio (P-06/P-12 impedem transação cross-store no use-case). **Follow-up: SEC-06.** Decisão consciente de escopo, não omissão.
- **Impacto em specs/código:** `application/ports.py` (`put -> bool`); `application/create_post.py` (reordenado); `infrastructure/sqlite_repository.py` (`rowcount==1`); `infrastructure/in_memory.py` (`+Lock`, `-> bool`); `tests/contract/test_post_repository_contract.py` (nova classe `TestIdempotencyClaimContract`); `tests/integration/test_create_post_concurrency.py` (novo, teste de prova). `PostRepository` intacto.
- **Impacto em testes/gates:** teste de prova red-green (use-case, parametrizado, `Barrier`) **+** teste de conformação de porta (parametrizado, guarda todo adapter futuro); cobertura das 5 ramificações do use-case (categoria idempotência = 100% branch, P-07); ratchet global re-fixado ao patamar medido se subir (só sobe — número medido no review-loop, nunca chutado); mutation-âncoras (ordem [proof com barreira no TOCTOU], `rowcount`, valor-do-vencedor, 409 [via suíte]; lock in-memory [via sonda de corrida forçada, fora da suíte — §8.5]).

## 6. Gatilhos de revisão

Reabrir esta decisão se:
- Entrar um adapter de `IdempotencyStore` **eventualmente-consistente** (réplica Redis, DynamoDB) — a cláusula C-4 (visibilidade pós-claim) precisará de teste de consistência específico, hoje satisfeito no in-memory via GIL (obrigação diferida verificável, §8).
- A janela de falha parcial residual (§5) deixar de ser aceitável (ex.: o app sair do escopo local/monousuário) — aí entra o workstream transacional junto de SEC-06.
- Surgir necessidade de idempotência com TTL/expiração (SEC-05) que mude a semântica write-once.

## 7. Aprovações

| Papel | Nome/agente | Data | Veredito |
|---|---|---|---|
| Tech Lead Backend | `tl-python` | 2026-07-15 | Aprovado — defendeu A; contra assumido (janela residual → SEC-06) incorporado em §5 |
| Tech Lead QA | `tl-qa` | 2026-07-15 | Aprovado com condição — cláusula C-1..C-5 + teste de conformação parametrizado como DoD (§8) |
| Tech Lead Full Stack | `fullstack-tech-lead` | 2026-07-15 | Consultivo — read-back-compare (C) registrado como alternativa de menor blast-radius preterida; concordou que `put→bool` vence no didático |

## 8. Condições vinculantes do painel (2026-07-15)

Sem estas, o aceite não se sustenta.

### 8.1 Cláusula normativa de concorrência de `IdempotencyStore.put` (P-03/P-12)

Seja `put(key, payload_hash, response) -> bool` chamado por N chamadores concorrentes. Todo adapter **DEVE** satisfazer, sem depender do GIL nem do escalonador:

- **C-1 (vencedor único):** para N `put` concorrentes com a **mesma** `key`, **exatamente um** retorna `True`; todos os demais retornam `False`. Nem zero, nem dois (`sum(results) == 1`).
- **C-2 (veredito honesto):** `True` ⟺ *este* chamador materializou o registro daquela `key`. Proibido `True` incondicional ou veredito derivado de estado não serializado com a escrita.
- **C-3 (write-once de valor):** após qualquer sequência de `put` concorrentes na mesma `key`, `get(key)` devolve o `(payload_hash, response)` **do chamador que recebeu `True`** — nunca o de um perdedor. Primeiro claim vence e é imutável (ADR-0003 §4.4 permanece).
- **C-4 (visibilidade pós-claim / happens-before):** quando um chamador recebe `False`, um `get(key)` subsequente **DEVE** observar o registro do vencedor (não-`None`) — o perdedor precisa ler o vencedor para replay (o use-case assume `winner is not None`).
- **C-5 (persistência real do claim):** `True` implica registro legível por outra conexão/chamador, não um flag local. `put` que retorna `True` mas não persiste é violação.
- **Primitiva por backend (informativo):** SQLite `INSERT OR IGNORE`+`rowcount`; Redis `SET NX`; Postgres `INSERT ... ON CONFLICT DO NOTHING RETURNING`; DynamoDB `PutItem` com `attribute_not_exists(key)`. Backend sem primitiva condicional **DEVE** prover atomicidade via lock/transação própria (como o `threading.Lock` do in-memory). **A garantia é do contrato, não do backend.**

### 8.2 Teste de conformação de porta (o portão executável — DoD)

Na suíte parametrizada `tests/contract/test_post_repository_contract.py`, classe `TestIdempotencyClaimContract`, rodando contra **todo** adapter (in-memory, SQLite e futuros) por construção da fixture:
- **`test_exactly_one_winner_under_concurrency`** (C-1/C-2): `Barrier(N)` (N≥8, sem `sleep`), `sum(True)==1` **e** `count(False)==N-1`.
- **`test_winner_value_is_the_one_that_won`** (C-2/C-3 **acoplados**): cruza *quem recebeu `True`* com *qual valor `get` devolve* — barra o falso-verde "bool honesto, valor errado".
- **`test_loser_can_read_winner`** (C-4/C-5): após um `False`, `get` vê o vencedor (não `None`) — barra "vence mas não persiste".
- Coletar via `f.result()` (propaga exceção — **não** `errors.append`/`fut.exception()` descartado), asserções só de estado.

### 8.3 Teste de prova do use-case (red-green — DoD)

`tests/integration/test_create_post_concurrency.py`, parametrizado nos 2 adapters, exercita `CreatePost.execute` real: `Barrier(N)`, mesma key+payload → `post_repo.count()==1` **e** `len(set(ids))==1`. **`id_gen` REAL/distinto por chamada** (id constante mascara o bug — falso-verde). Deve **nascer vermelho** hoje (registrar o run vermelho no PR). Conflito concorrente (payload divergente) → exatamente um `IdempotencyConflict` (P-11).

### 8.4 Falsos-verdes a barrar (checklist de revisão)

Adapter que retorna sempre `True` (C-1); bool honesto mas valor do perdedor persistido (C-2/C-3 acoplado); `True` sem persistir (C-4/C-5); paridade in-memory×SQLite que só diverge sob corrida (rodar parametrizado); `N` pequeno / sem `Barrier` (falso-verde do próprio guardião — `N≥8`+`Barrier` obrigatórios); `id_gen` constante no teste de prova; worker que engole exceção.

### 8.5 Obrigação diferida verificável

Duas garantias são **deliberadamente mais fracas** que a cláusula normativa por conta do CPython-GIL — registradas honestamente, não como buraco:

- **C-4 (visibilidade pós-claim):** o teste in-memory a satisfaz via GIL. Um adapter distribuído futuro (Redis réplica/DynamoDB) **DEVE** provar C-4 com teste de consistência específico ao entrar.
- **Atomicidade do check-and-set do `put` in-memory (o `threading.Lock`):** a corrida a proteger vive *dentro* do `if key in store → store[key]=...`; sob CPython-GIL a suíte threaded **não** a interleava de forma confiável (nem com barreira no ponto TOCTOU `get→put`, pois a janela é interna ao `put`). O lock é **correto por construção**; sua natureza load-bearing é demonstrada por **sonda de corrida forçada** (sleep injetado entre check e set → sem lock, N/N threads vencem), documentada, e seria ancorável por mutation-test só num runtime free-threaded (PEP 703) ou adapter distribuído. **Não** afirmar "ancorado pela suíte" (seria falso).

O **invariante de ordenação do use-case** (claim-antes-de-criar) — este sim — **DEVE** nascer vermelho na suíte: o teste de prova (§8.3) usa barreira no ponto TOCTOU (dentro de `get()` quando retorna `None`, forçando as N threads a passarem do `get==None` antes de qualquer `put`), tornando a mutação "`add` incondicional" vermelha de forma confiável nos 2 adapters; os unit determinísticos são a âncora complementar. Ambos gatilhos de revisão (§6).

### 8.6 Escopo — o que este ADR **não** fecha

Fecha o **TOCTOU de concorrência** (P-03). **Não** torna a criação atômica cross-table sob crash (janela residual, §5) — isso é do workstream transacional de **SEC-06**. Não acoplar SEC-06 aqui (classes de falha distintas: escrita-que-quebra-piso vs liveness-de-leitura). Declarar "criação atômica sob crash resolvida" seria falso-verde de escopo.
