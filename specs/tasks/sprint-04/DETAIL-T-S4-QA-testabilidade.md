# DETAIL — T-S4-QA — Anexo de testabilidade da Sprint 4 (hardening)

**Sprint:** 4
**Tamanho:** M _(estimativa; transversal às 4 tarefas)_
**Papel:** QA (tl-qa) — co-detalhamento com `tl-python` (T-S4-03), `tl-frontend` (T-S4-02) e `sre` (T-S4-01/04)
**Depende de:** `docs/quality/hardening-baseline-2026-07.md` (achados SEC-01/02/03/07 — a **fonte**), gate ratchet vigente (T-S2-09 / `coverage-gates.sh`), suíte de idempotência existente (T-S2-05).
**Bloqueia:** o `review-loop` de cada tarefa da Sprint 4 (nenhum gate bloqueante fecha sem o teste-de-prova aqui descrito rodando **verde**, e tendo nascido **vermelho** antes do fix).

> Produzido por `tl-qa` no `sprint-flow` (testabilidade); consumido pelo `review-loop` **junto** com os DETAIL de cada stack. Este anexo NÃO implementa testes — detalha o teste-de-prova (red-green), os CAs em Gherkin, a mutation-âncora e o impacto em quality gates de cada tarefa. O status real vive no board, não aqui.

---

## 0. Princípios transversais (valem para as 4 tarefas)

Aplicados de `CLAUDE.md` (gates não-negociáveis) + `docs/lessons/qa.md` (anti-falso-verde) + `docs/lessons/security.md`:

1. **Regressão nasce vermelha.** Todo gate bloqueante desta sprint precisa de um teste-de-prova que **falhe ANTES** do fix e passe **depois**. Sem o vermelho demonstrado, o gate é teatro (qa.md — "Prove que o gate morde").
2. **O gate morde a FORMA REAL do código.** Para os gates de CI (SEC-02/SEC-07) a varredura textual é a autoritativa: planta-se a violação na forma exata (tag mutável, segredo-canário) e exige-se `exit != 0`; o estado limpo dá `exit 0`. Nunca `assert errors > 0` (assert-de-existência passa com gate teatral).
3. **Execução cobre o wiring de DI de produção.** Rota/gate novo exige teste que exercite a cadeia real (TestClient HTTP real p/ backend; job real no `ci.yml` p/ supply-chain), não um dublê que espelha só o contrato.
4. **Flaky = P1.** Nenhuma asserção depende de relógio de parede, ordem de execução ou rede externa para o seu **conteúdo**. Concorrência se sincroniza por **barreira determinística** (`threading.Barrier`), nunca `sleep`. `pytest-randomly` (já pinado, `3.16.0`) deve passar igual.
5. **Ratchet só sobe.** Rebaixar qualquer piso (cobertura global, por-categoria, thresholds do Vitest, `--audit-level`) exige ADR. Subir junto com a entrega que habilita é parte da DoD.
6. **Não paralelizar escritores no mesmo recurso.** O teste de concorrência SQLite (T-S4-03) abre conexão real; **serializar** com outros testes que escrevem no mesmo processo/DB (não rodar sob `pytest-xdist` no mesmo arquivo de banco) — ver §7.

---

## 1. T-S4-01 — SEC-02: gitleaks como gate de CI (secret-scan bloqueante)

### 1.1 Objetivo de qualidade
Fechar o piso "secret-scan bloqueante" (CLAUDE.md): hoje gitleaks só roda em pre-commit opt-in (`--no-verify` contorna). Provar que o job de CI **barra o merge** de um segredo **sem** commitar segredo real, e que o scan é **determinístico**.

### 1.2 CAs em Gherkin

```gherkin
Funcionalidade: Secret-scan bloqueante no CI (SEC-02)

  Cenário: PR com segredo-canário reprova o job
    Dado um branch efêmero com um arquivo contendo um segredo-canário
      que casa uma regra do gitleaks (formato real, valor sintético)
    Quando o job "gitleaks" roda no CI sobre o histórico do PR (fetch-depth: 0)
    Então o job termina com exit != 0
      E o merge fica bloqueado (job requerido)

  Cenário: repositório limpo aprova o job
    Dado o HEAD sem nenhum segredo-canário
    Quando o job "gitleaks" roda no CI
    Então o job termina com exit 0

  Cenário: o scanner é pinado e determinístico
    Dado o job gitleaks referenciado pela Action pinada por SHA (rev v8.18.4)
    Quando o mesmo commit é escaneado duas vezes
    Então o resultado é idêntico (mesma versão de regras, sem drift de "latest")
```

### 1.3 Teste-de-prova (red-green) — SEM commitar segredo real

- **Prova de que o SCANNER + config mordem (local, determinístico):**
  `scripts/gitleaks-canary-test.sh` (novo). Cria um diretório temporário, escreve um arquivo com um segredo-**canário** (padrão que casa uma regra gitleaks — ex.: chave AWS `AKIA…`-shaped com valor sintético, **fora** de qualquer `.gitleaksignore`), roda `gitleaks detect --no-git --source "$TMP"` e **exige exit != 0**; remove o canário e **exige exit 0**. Não toca no repo versionado (tmpdir), então nenhum segredo entra no histórico (security.md — "scanner lê o histórico cumulativo; segredo commitado é vazamento permanente").
- **Prova de que o JOB está WIRED (one-time, branch efêmero):** abrir um PR de branch descartável com o canário no repo → confirmar que o **job requerido** reprova e bloqueia o merge; deletar o branch sem merge. Documentar o SHA do run como evidência no `review-loop`. Isto cobre o **wiring** (qa.md — "gate não-wired é inerte; só conta rodando no pipeline"), que o harness local não prova.
- **Escopo do scan:** `fetch-depth: 0` no checkout → scan do **histórico** do PR, não só o diff do HEAD (security.md — remover no último commit não basta). Registrar no DETAIL que o gate cobre commits do PR, não só a árvore final.

### 1.4 Mutation-âncora
| Reverter (mutação) | Resultado esperado |
|---|---|
| Remover o job `gitleaks` do `ci.yml` | Teste estático de wiring (§4.3) fica **vermelho** (job ausente) |
| Trocar `AKIA…`-shaped canário por string neutra no harness | `gitleaks-canary-test.sh` passa o passo "com canário" com exit 0 → harness **falha** (perdeu o poder de detecção) |
| Adicionar o canário a `.gitleaksignore` (allowlist indevida) | harness detecta exit 0 no passo canário → **vermelho** (allowlist neutralizou o gate) |
| Pinar a Action por tag mutável (`@v8`) em vez de SHA | Teste de pin-por-SHA (§4, SEC-07) fica **vermelho** |

### 1.5 Impacto em gates
- Novo **job de CI requerido** `gitleaks` (bloqueante de merge). Não altera cobertura de código.
- Determinismo: Action pinada por **SHA** na `rev v8.18.4` (mesma do pre-commit — zero drift de versão; process.md "o juiz é o comando do CI").

---

## 2. T-S4-02 — SEC-01: bump Angular ≥19.2.17 + `npm audit` como gate

### 2.1 Objetivo de qualidade
Fechar o CVE-2025-66412 (stored XSS via bypass de sanitização, CVSS 8.5) subindo Angular de `19.2.14` → `≥19.2.17`, e instituir `npm audit` como gate de CI **sem introduzir flaky** (o DB de advisories muda no tempo).

### 2.2 CAs em Gherkin

```gherkin
Funcionalidade: Gate de dependências do frontend (SEC-01)

  Cenário: audit reprova com CVE High presente
    Dado o frontend fixado em @angular/core 19.2.14 (exposto ao CVE-2025-66412 High)
    Quando "npm audit --audit-level=high" roda no CI
    Então o comando termina com exit != 0

  Cenário: audit aprova após o bump
    Dado o frontend fixado em @angular/core >= 19.2.17
    Quando "npm audit --audit-level=high" roda no CI
    Então o comando termina com exit 0

  Cenário: regressão zero pós-bump (comportamento inalterado)
    Dado o bump aplicado e o package-lock regenerado (npm 10, sem entradas-fantasma)
    Quando rodam tsc --noEmit (app+spec), lint pinado, ng build e test:cov
    Então todos passam
      E a cobertura permanece >= thresholds do 2o ratchet (branches 90 / funcs 96 / lines 97 / stmts 97)
      E o piso por-arquivo de post-store.ts (>= 86 branch) permanece verde
      E o gate de drift de contrato (gen:api + git diff --exit-code) permanece vazio

  Cenário: o gate de audit não fica flaky com novo advisory
    Dado um advisory High novo surgindo no registry para uma dep não tocada
    Quando o gate roda via política de allowlist controlada e time-boxed
    Então advisories JÁ triados/aceitos não derrubam o CI
      E qualquer advisory High NÃO-listado ainda reprova (fail-closed)
```

### 2.3 Teste-de-prova (red-green)
- **CA "audit reprova com CVE High" (nasce vermelho no estado pré-bump):** rodar `npm audit --audit-level=high` no `package.json` atual (Angular 19.2.14) → **exit != 0**. Após `ng update @angular/core@19.2 @angular/cli@19.2` (≥19.2.17) + `npm ci` → **exit 0**. Este é o red-green do fix.
- **Regressão zero:** a suíte existente do frontend é o gate — `npx tsc --noEmit -p tsconfig.app.json` + `-p tsconfig.spec.json`, `npm run lint`, `ng build`, `npm run test:cov` (thresholds do `vitest.config.ts`). Nenhum spec novo de comportamento é necessário: o CVE-2025-66412 exige um sink (`bypassSecurityTrust*`/`innerHTML`) que o app **não** usa (baseline: "escape universal por `{{ }}`; zero innerHTML"). Portanto o valor está no bump + gate de audit, não em novo caso de teste de XSS — **não** escrever E2E de XSS especulativo (YAGNI; o sink inexiste).
- **Guard do lockfile:** o step "lockfile sem entradas-fantasma" já existente (`ci.yml`) deve permanecer verde após regenerar o `package-lock.json` (npm 10) — cobre o risco de o `ng update` reintroduzir entradas sem `version`.

### 2.4 Anti-flaky do gate de audit (decisão de testabilidade)
O `npm audit` consulta o registry → resultado **varia no tempo** (novo advisory reprova um PR que não tocou em deps). Para manter determinismo **sem** virar as costas para CVE novo:

| Critério | Opção A — `npm audit` puro | Opção B — `audit-ci`/`better-npm-audit` com allowlist |
|---|---|---|
| Fail-closed em High novo | Sim | Sim |
| Flaky por advisory novo em dep não-tocada | **Sim** (derruba PR alheio) | Mitigado (allowlist time-boxed) |
| Rastreabilidade de exceção | Nenhuma | Cada entrada = advisory-id + razão + `review-by` |
| Dep nova de teste | 0 | +1 (pinada) |

**Recomendação:** Opção B com allowlist **mínima e time-boxed** (cada entrada com data de expiração e justificativa — qa.md "allowlist grande no dia 1 é smell"). No dia do bump a allowlist nasce **vazia** (o bump resolve o único High). Um advisory High **não-listado** ainda reprova (fail-closed). Alternativa aceita: manter Opção A e mover o audit para um job **agendado** (cron) separado do gate de PR — registrar o trade-off em nota. A escolha final é do `review-loop` (tl-frontend); QA exige apenas que o gate seja **fail-closed** e **rastreável**.

### 2.5 Mutation-âncora
| Reverter (mutação) | Resultado esperado |
|---|---|
| Voltar `@angular/core` para `19.2.14` | `npm audit --audit-level=high` → exit != 0 → gate **vermelho** |
| Baixar `--audit-level` para `critical` | O High CVE-2025-66412 (não-critical) passa → o CA "reprova com High" fica **vermelho** (gate não morde mais High) |
| Esvaziar os thresholds do `vitest.config.ts` | 2º ratchet não morde — barrado pela política de ratchet (ADR exigido) |

### 2.6 Impacto em gates
- **2º ratchet (frontend):** thresholds **inalterados** (branches 90 / funcs 96 / lines 97 / stmts 97; `post-store.ts` ≥86 branch). O bump não deve mexer na cobertura; se `ng build`/tipos mudarem números, re-medir e **subir** (nunca baixar).
- **Novo step de CI** `npm audit`/`audit-ci` no job `frontend` (bloqueante, fail-closed).
- **Gate de drift de contrato** (`gen:api`) intacto — os tipos são gerados do OpenAPI do backend, imunes ao bump do Angular.

---

## 3. T-S4-03 — SEC-03: TOCTOU de idempotência no CREATE (CENTRAL — único piso de constitution quebrado, P-03)

### 3.1 Objetivo de qualidade
`create_post.py:47-64` faz **check-then-act** não atômico: `get(key) → None` (nos dois requests) → cada um cria `Post` com **id distinto** (`_new_ulid`) → `repo.add()` (UPSERT por id → 2 linhas) → `idem.put()` write-once (fixa só a 1ª resposta). Resultado sob concorrência: **2 posts** e respostas com **ids distintos** — viola P-03. O teste-de-prova deve **nascer vermelho hoje** e ficar verde após o fix (claim-da-chave-primeiro **ou** `post_id` derivado da idem-key — decisão do `tl-python`; o teste é **agnóstico ao fix**, ancora só no invariante observável).

### 3.2 CAs em Gherkin

```gherkin
Funcionalidade: Idempotência do CREATE sob concorrência (SEC-03 / P-03)

  Cenário: N requests concorrentes com mesma key + mesmo payload criam UM post
    Dado o adapter SQLite real (conexão compartilhada, lock de escrita)
      E um id_gen que produz ids DISTINTOS por chamada (ULID real)
    Quando N threads chamam POST /v1/posts com a MESMA Idempotency-Key e o MESMO payload
      sincronizadas por uma barreira no ponto vulnerável (todas passam do get() antes de qualquer put())
    Então post_repo.count() == 1
      E todas as N respostas carregam o MESMO id
      E nenhuma resposta é 5xx

  Cenário (preservar): idempotência sequencial não regride
    Dado uma criação já persistida com key K e payload P
    Quando um segundo request usa a mesma key K e payload P
    Então retorna 200 com Idempotent-Replayed: true e o mesmo id (count permanece 1)

  Cenário (preservar): conflito de payload continua 409
    Dado uma criação já persistida com key K e payload P
    Quando um request usa key K e payload P' (divergente)
    Então retorna 409 idempotency_key_conflict
```

### 3.3 Teste-de-prova (red-green) — o mais crítico da sprint

**Arquivo:** `backend/tests/integration/test_toctou_idempotency.py` (novo).
**Formato:** pytest + `concurrent.futures.ThreadPoolExecutor` + `threading.Barrier`, sobre `create_app(repo=SqlitePostRepository(...), idem=SqliteIdempotencyStore(...))` — **recurso real** (qa.md: "concorrência se prova no recurso REAL, não num dublê").

Design da prova:
```text
N = 16  (threads)
handle = make_connection(tmp_path/"toctou.db"); init_schema(handle.conn)
# idem REAL, envolvido por um wrapper que sincroniza no ponto TOCTOU:
#   após get(key) retornar None, TODAS as threads esperam a Barrier(N)
#   antes de qualquer uma prosseguir para add()/put().
#   -> maximiza a corrida DE FORMA DETERMINÍSTICA (sem sleep).
barrier = threading.Barrier(N)
idem = BarrierSyncedIdempotencyStore(SqliteIdempotencyStore(handle...), barrier)
app  = create_app(repo=SqlitePostRepository(handle...), idem=idem)
# id_gen: ULID real (default) -> ids DISTINTOS por chamada (essencial, ver 3.4)
client = TestClient(app, raise_server_exceptions=False)

futures = [pool.submit(client.post, "/v1/posts",
                       json=SAME_PAYLOAD,
                       headers={"Idempotency-Key": SAME_KEY})
           for _ in range(N)]
resps = [f.result() for f in as_completed(futures)]

assert app.state.post_repo.count() == 1        # invariante de ESTADO (P-03)
ids = {r.json()["id"] for r in resps}
assert len(ids) == 1                           # mesmo id em TODAS as respostas
assert all(r.status_code in (200, 201) for r in resps)  # nenhum 5xx
```

**Por que nasce vermelho hoje (determinístico):** a `Barrier(N)` garante que as N threads passam do `get()==None` **antes** de qualquer `put()`; com o bug, cada uma cria um post com ULID distinto → `count()==N` e `len(ids)==N` → **vermelho** de forma reprodutível (não flaky-red). Após o fix (claim atômico ou id derivado da key), só um cria; os demais leem/replayam a resposta canônica → `count()==1`, `len(ids)==1` → **verde**.

### 3.4 ARMADILHA de falso-verde (bloqueante para o revisor) — id_gen DEVE ser distinto por chamada
O `id_gen` do use-case **não pode** ser um `lambda: FIXED_ID`. Se todos os posts nascem com o **mesmo** id, o `repo.add()` (UPSERT por id em `sqlite_repository.py:145`) **colapsa** para 1 linha mesmo com o bug presente → `count()==1` e todos os ids iguais → o teste passa **vacuamente**, mascarando o TOCTOU (qa.md — "guard adjacente mata a mutação"; "a mutação tem de atacar a invariante que o teste ALEGA proteger"). Regra de testabilidade: usar o `_new_ulid` real (ou um contador thread-safe que emite ids **distintos**). Assertar **igualdade entre respostas** e **count absoluto**, nunca o **valor** do id (determinismo).

> **Nota de wiring (para o `tl-python`):** hoje `main.py:74-79` fia `CreatePost(id_gen=_new_ulid)` **hardcoded** — o parâmetro `id_gen` de `create_app` alimenta só a observabilidade (linha 88). Para o teste (e para o fix "id derivado da key") talvez seja preciso injetar `id_gen` também no `CreatePost`. Se o teste usar o default `_new_ulid`, não há bloqueio; se o fix optar por id-derivado-da-key, o wiring muda e o teste continua válido (agnóstico ao fix).

### 3.5 Parametrização sobre ambos os adapters
- **Autoritativo (SQLite, recurso real):** o teste §3.3 roda sobre `SqlitePostRepository`/`SqliteIdempotencyStore` — é a prova que vale (conexão real, lock real, `INSERT OR IGNORE` real).
- **In-memory (didático):** `in_memory.py` também exibe o TOCTOU (o `put` é `if key not in self._store` — check-then-act; `add` é `dict[id]=post`). Se o fix introduzir um **método de porta novo** (ex.: `claim(key)->bool` atômico), o adapter in-memory precisa implementá-lo **com lock** para não mascarar o fix nos testes HTTP que o usam. Recomendação: **contract test** parametrizado `@pytest.mark.parametrize("store_factory", [sqlite_factory, in_memory_factory])` cobrindo a **semântica de claim** (um vencedor, N-1 replays) — porém o **stress de concorrência sob barreira** fica no SQLite (recurso real; o dict in-memory sob GIL dá menos sinal). Se o fix **não** mexe na porta (id-derivado-da-key), o in-memory herda a correção sem novo método e o parametrize vira defensivo.

### 3.6 Preservar o que já existe (não-regressão)
Os testes sequenciais **não podem** quebrar com o fix:
- `backend/tests/unit/test_create_post_usecase.py` — replay, conflito 409, hash determinístico.
- `backend/tests/integration/test_create_post_http.py` — CA-F001-02 (replay 200 + `count()==1`), CA-F001-04 (sem key → 400, `count()==0`), 409 divergente.
- `backend/tests/integration/test_sqlite_concurrency.py` — `test_concurrent_upsert_same_id_no_duplicate` e `test_concurrent_idem_put_write_once` (write-once do adapter). O fix do use-case **não** deve alterar a semântica write-once do adapter; se o fix adicionar `claim` no adapter, este arquivo ganha um caso, não perde.

### 3.7 Mutation-âncora
| Reverter (mutação) | Resultado esperado |
|---|---|
| Restaurar o check-then-act original (`get→add(novo ULID)→put`) em `create_post.py` | `test_toctou_idempotency` → `count()==N`, `len(ids)==N` → **vermelho** |
| Trocar `id_gen` do teste por `lambda: FIXED_ID` | Teste passa **vacuamente** com o bug → é o anti-padrão que o §3.4 proíbe; revisor **reprova** o teste (falso-verde de 2ª ordem) |
| No fix claim-first: remover a checagem de `rowcount`/vencedor (sempre tratar como vencedor) | Todos criam → `count()==N` → **vermelho** |
| No fix id-derivado: voltar id para `_new_ulid` mas manter reorder | ids distintos → UPSERT gera N linhas → **vermelho** |
| Remover a `Barrier` (sync por `sleep`/nada) | Sob o bug, red **intermitente** (às vezes serializa) → flaky = P1; a barreira é o que torna o red **determinístico** |

### 3.8 Impacto em gates
- **Categoria `use-cases-write` (`create_post.py` + `publish_post.py`) — piso 100%** (`coverage-gates.sh:113-116`): o branch novo do fix (claim/vencedor-perdedor) **precisa** de teste que o cubra; 100% morde se algum ramo ficar descoberto. `--cov-branch` já ativo → o ramo "perdedor lê resposta do vencedor" conta.
- **Categoria `adapter-sqlite` — piso 100%** (`coverage-gates.sh:94-97`): se o fix adicionar `claim()`/SQL novo no adapter, mantém 100% (glob `sqlite_*.py`).
- **Global ratchet (99):** re-medir após o fix; se subir, re-fixar `--cov-fail-under` (só sobe — P-07). Sem folga → escrever teste, não baixar piso.
- **`mypy --strict`** no `src/` inteiro (assinatura de porta nova, se houver). **`pytest-randomly`** verde (o teste não depende de ordem).

---

## 4. T-S4-04 — SEC-07: CI least-privilege + supply-chain

### 4.1 Objetivo de qualidade
`GITHUB_TOKEN` sem `permissions` (herda write); Actions por tag mutável (`@v4/@v5`); backend sem lockfile/hash-pinning/`pip-audit`. Provar least-privilege e supply-chain **por checagem estática que morde a forma real do `ci.yml`** + `pip-audit` fail-closed + build por hash.

### 4.2 CAs em Gherkin

```gherkin
Funcionalidade: Least-privilege e supply-chain no CI (SEC-07)

  Cenário: token de menor privilégio
    Dado o workflow ci.yml
    Quando o guard estático inspeciona o bloco permissions
    Então existe "permissions:" com "contents: read" (nível workflow ou job)
      E nenhum job concede write sem justificativa explícita

  Cenário: Actions pinadas por SHA (imutável)
    Dado o workflow ci.yml
    Quando o guard varre cada linha "uses:"
    Então TODA referência casa um SHA de 40 hex
      E NENHUMA usa tag mutável (@v4, @v5, @main, @latest)

  Cenário: pip-audit bloqueia CVE High no backend
    Dado o backend com requirements.lock (--generate-hashes)
    Quando "pip-audit" roda no CI
    Então falha (exit != 0) se houver vulnerabilidade conhecida
      E "pip install --require-hashes" recusa dep cujo hash não bate

  Cenário: build reproduzível por hash
    Dado o requirements.lock com hashes
    Quando o CI instala com --require-hashes
    Então só instala artefatos cujo hash corresponde ao lock (build determinístico)
```

### 4.3 Teste-de-prova (red-green) — guard estático que morde a forma real
**Arquivo:** `backend/tests/ci/test_ci_hardening.py` (novo). Lê o `.github/workflows/ci.yml` como **texto** (regex; sem novas deps — PyYAML não está pinado), ignorando linhas de comentário. Asserções:
- `permissions:` presente com `contents: read` (workflow ou job).
- Toda ocorrência de `uses:` casa `@[0-9a-fA-F]{40}\b` (SHA); **nenhuma** casa `@v\d+` / `@main` / `@latest`. (qa.md — "o gate morde a FORMA REAL"; varredura textual autoritativa, AST só descartaria comentário.)
- Existe step/job com `pip-audit`.
- **Sentinela anti-truncamento:** `assert n_uses >= N_ESPERADO` (nº de `uses:` conhecido no workflow) — evitar "varreu 3 de 31" passar (qa.md — "sentinela >0 mascara truncamento").

**Red-green do guard:** reintroduzir uma tag mutável (`uses: actions/checkout@v4`) **ou** remover o bloco `permissions` no `ci.yml` → o teste **reprova** (`exit != 0`). Estado hardenizado → `exit 0`. Prova plantando a violação na forma real, não sintética.

**pip-audit / hashes (red-green de supply-chain):**
- Gerar `backend/requirements.lock` com `pip-compile --generate-hashes` (ou `uv`/`pip freeze`+hashes). CI: `pip install --require-hashes -r requirements.lock` → recusa dep com hash divergente (prova: adulterar um hash no lock → install **falha**).
- `pip-audit` como step: com uma dep vulnerável conhecida → exit != 0 (fail-closed). Determinismo: o audit lê a base de advisories; para o gate de PR não flapar por advisory novo, mesma política do §2.4 (fail-closed + allowlist time-boxed se necessário) — decisão do `sre`/`tl-python` no `review-loop`.

### 4.4 Mutation-âncora
| Reverter (mutação) | Resultado esperado |
|---|---|
| Remover `permissions: contents: read` do `ci.yml` | `test_ci_hardening` → **vermelho** |
| Trocar um `uses: …@<sha>` por `@v4` | guard de pin-por-SHA → **vermelho** |
| Adulterar um hash em `requirements.lock` | `pip install --require-hashes` → **falha** (build não reproduzível) |
| Remover o step `pip-audit` | asserção de presença do step → **vermelho** |
| Baixar o `assert n_uses >= N` para `> 0` | sentinela vira teatro — revisor reprova (mascara truncamento) |

### 4.5 Impacto em gates
- Novo **guard de CI** (`test_ci_hardening.py`) roda na suíte pytest (sem nova dep). Cobertura: é teste de infra; não conta em categoria de código de produção (não infla nem dilui os pisos por-glob).
- Novo step `pip-audit` + `--require-hashes` no job `backend` (bloqueantes).
- Actions do `ci.yml` **todas** pinadas por SHA (inclui `checkout`, `setup-python`, `setup-node` e a `gitleaks-action` de SEC-02) — dependência cruzada com T-S4-01.

---

## 5. Tabela consolidada de mutation-âncoras (índice para o `review-loop`)

| Tarefa | Fix de produção | Teste-de-prova | Mutação que deixa VERMELHO | Recurso |
|---|---|---|---|---|
| T-S4-01 | job gitleaks no CI (SHA, fetch-depth 0) | `scripts/gitleaks-canary-test.sh` + canário em branch efêmero | canário vira string neutra / allowlist indevida / job removido | scanner real (tmpdir) + job real |
| T-S4-02 | Angular ≥19.2.17 + `npm audit` gate | `npm audit --audit-level=high` red→green + suíte front | voltar 19.2.14 / baixar audit-level p/ critical | registry npm + Vitest |
| **T-S4-03** | claim-atômico **ou** id-derivado-da-key | `test_toctou_idempotency.py` (Barrier(N), count==1, ids únicos) | restaurar check-then-act / `id_gen` fixo / remover Barrier | **SQLite real** + TestClient |
| T-S4-04 | permissions + pin SHA + pip-audit/hashes | `test_ci_hardening.py` + `--require-hashes` | remover permissions / tag mutável / hash adulterado | ci.yml textual + pip |

---

## 6. Impacto consolidado em quality gates

| Gate | Situação | Ação da Sprint 4 |
|---|---|---|
| Global `--cov-fail-under=99` (backend) | mantém | re-medir após T-S4-03; se subir, re-fixar (só sobe) |
| `use-cases-write` 100% (por-categoria) | mantém 100% | branch novo do fix TOCTOU coberto (`--cov-branch`) |
| `adapter-sqlite` 100% | mantém 100% | se `claim()` novo no adapter, cobrir |
| 2º ratchet frontend (Vitest thresholds) | mantém | inalterado pós-bump; se números subirem, subir piso |
| `post-store.ts` piso por-arquivo (≥86 branch) | mantém | inalterado |
| Gate de drift de contrato (`gen:api`) | mantém | imune ao bump Angular |
| **Novo:** job `gitleaks` requerido | criar | bloqueante de merge (SEC-02) |
| **Novo:** step `npm audit`/`audit-ci` | criar | fail-closed (SEC-01) |
| **Novo:** guard `test_ci_hardening.py` | criar | permissions + pin SHA + pip-audit (SEC-07) |
| **Novo:** `pip-audit` + `--require-hashes` | criar | supply-chain backend (SEC-07) |
| `pytest-randomly` (determinismo) | mantém | TOCTOU test não depende de ordem |

Nenhum piso **desce**. Todo gate novo nasce **fail-closed** e com teste-de-prova red-green.

---

## 7. Riscos de flaky / contaminação de ambiente

1. **[CRÍTICO] Concorrência real no SQLite (T-S4-03) — não paralelizar com outros escritores.** O `test_toctou_idempotency` abre conexão real e escreve sob carga. Se rodar sob `pytest-xdist` compartilhando o mesmo arquivo de DB, ou em paralelo com outro teste que escreve no mesmo processo, surgem **falhas-fantasma em massa** (CLAUDE.md — "não paralelize agentes que escrevem no mesmo repo+banco"). Mitigação: banco em `tmp_path` **por-teste** (isolado, como `test_sqlite_concurrency.py` já faz); manter a suíte **sem** `-n` no arquivo de concorrência (ou marcar `serial`). Determinismo do red garantido pela `threading.Barrier`, **nunca** `sleep`.
2. **[CRÍTICO] Falso-verde do `id_gen` fixo (T-S4-03).** Ver §3.4 — id fixo colapsa o UPSERT e mascara o TOCTOU. O revisor **deve** confirmar `id_gen` distinto por chamada, senão o teste passa vacuamente com o bug presente.
3. **Flaky do `npm audit`/`pip-audit` (T-S4-02/04).** Base de advisories muda no tempo → PR alheio pode reprovar. Mitigação: `--audit-level=high`/allowlist time-boxed **fail-closed** (§2.4), ou audit em job agendado separado do gate de PR. Nunca allowlist grande no dia 1.
4. **Segredo-canário vazando no histórico (T-S4-01).** O canário do harness vive em **tmpdir** (nunca versionado); a prova de wiring usa **branch efêmero deletado sem merge** (security.md — segredo commitado é vazamento permanente). Não commitar canário na árvore principal nem em `.gitleaksignore`.
5. **Barrier deadlock (T-S4-03).** `Barrier(N)` com N != nº real de threads que alcançam o ponto → deadlock/timeout. Usar `Barrier(N, timeout=...)` e `N == max_workers`; se o fix curto-circuitar o `get()` (claim-first não chama `get` primeiro), a barreira deve estar num ponto que **todas** as threads alcançam (ex.: no início do `execute`), senão trava. Detalhe de implementação a validar no `review-loop`.
6. **TestClient + threads.** `TestClient` (httpx) sobre `ThreadPoolExecutor` compartilha uma app/conexão; garantir `check_same_thread=False` (já é) e que o lock de escrita do adapter cobre `add`/`put`. Leituras (`get`) sem lock são exatamente o ponto TOCTOU — é o que o teste exercita.

---

## 8. Definition of Done consolidada (verificável)

- [ ] **T-S4-01:** job `gitleaks` (SHA-pinned, `fetch-depth: 0`) requerido; `gitleaks-canary-test.sh` red-green verde; wiring provado em branch efêmero (SHA do run registrado).
- [ ] **T-S4-02:** Angular ≥19.2.17; `npm audit` gate red→green (14→bump); suíte front (tsc app+spec, lint, `ng build`, `test:cov`) verde ≥ thresholds; lockfile-guard verde; política anti-flaky (fail-closed) documentada.
- [ ] **T-S4-03 (central):** `test_toctou_idempotency.py` nasceu **vermelho** (bug presente) e ficou **verde** (pós-fix); `id_gen` distinto por chamada confirmado; `Barrier(N)` (sem `sleep`); `count()==1` + ids únicos + sem 5xx; sequenciais (unit + HTTP + `test_sqlite_concurrency`) **sem regressão**; `use-cases-write`/`adapter-sqlite` mantêm 100%; global re-medido.
- [ ] **T-S4-04:** `test_ci_hardening.py` red-green (permissions + pin SHA + pip-audit) com sentinela `>= N`; `requirements.lock --generate-hashes` + `--require-hashes` provado (hash adulterado → falha); todas as Actions do `ci.yml` por SHA.
- [ ] **Transversal:** nenhum piso rebaixado sem ADR; `pytest-randomly` verde; concorrência SQLite serializada (não paralela com escritores); todo gate novo **fail-closed**.
- [ ] Revisão aprovada (`tl-qa` + `tl-python`/`tl-frontend`/`sre` conforme a tarefa) sem ressalvas.
