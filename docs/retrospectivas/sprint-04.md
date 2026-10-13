# Retrospectiva — Sprint 4 (MVP de hardening de segurança)

> Data: 2026-07-15 · Tarefas: T-S4-01..04 + ADR-0007 · Origem: `sprint-flow` (a partir do `hardening-flow`)

## Escopo entregue

A Sprint 4 nasceu da auditoria `hardening-flow` (baseline `docs/quality/hardening-baseline-2026-07.md`, 14 achados) e executou o **MVP de hardening**: fechar os dois pisos que o projeto **contradizia** (secret-scan bloqueante; P-03 idempotência) mais o CVE de framework, via `review-loop` com prova por tarefa.

- **ADR-0007** (design-flow, painel `tl-python`/`tl-qa`/`fullstack-tech-lead`): contrato de concorrência de `IdempotencyStore` — `put -> bool` (claim-first) com cláusula normativa C-1..C-5 e teste de conformação parametrizado. Alternativa read-back-compare (menor blast-radius) registrada e preterida por legibilidade-no-contrato; `post_id`-derivado rejeitado (enumerabilidade).
- **T-S4-02 (SEC-01) — APROVADO (2 ciclos).** Bump Angular 19.2.14→**19.2.25**; CVE-2025-66412 (stored XSS) fechado. Gate `npm audit` **fail-closed** com allowlist por-ID (guard `node` inline, sem nova dep). Regressão zero (114/114 front).
- **T-S4-01 (SEC-02) — APROVADO (2 ciclos).** Job `secret-scan` bloqueante (gitleaks-action pinada por SHA + `GITLEAKS_VERSION 8.18.4`, `fetch-depth:0`, `permissions: contents: read`); guard estático `test_ci_hardening.py` (torna o hardening não-regressivo); harness de canário em tmpdir prova detecção dentro do CI.
- **T-S4-04 (SEC-07) — APROVADO parcial.** `permissions: contents: read`, todas as Actions pinadas por SHA, `pip-audit` fail-closed, `dependabot.yml`. **Pendente-de-tooling:** `requirements.lock --generate-hashes` (sem `pip-compile`/`uv` no ambiente).
- **T-S4-03 (SEC-03) — APROVADO (2 ciclos).** TOCTOU de idempotência fechado (piso **P-03**): `put -> bool`, claim-first, `get()` do SQLite sob `_lock`, lock in-memory. Teste de prova red-green **determinístico** (barreira no ponto TOCTOU) + conformação C-1..C-5 parametrizada. **189 testes, 100% cobertura.**

**Estado final:** backend 189 testes / 100% cobertura / 8 gates por-categoria; frontend 114 testes / ratchet intacto; CI com 3 jobs (backend + frontend + secret-scan) todos hardened; ADRs 0001–0007. **2 dívidas novas descobertas na execução** (SEC-15, SEC-16).

## ✅ O que funcionou (repetir)

- **Rodar o audit de verdade mudou o plano — e isso é a feature, não o bug.** O DETAIL assumia "backend/frontend limpos". `pip-audit`/`npm audit` reais desenterraram um auth-bypass de prod no `starlette` (SEC-15) e advisories residuais do Angular sem fix em 19.x (SEC-16). O gate fez o trabalho: virou dívida rastreada com `review-by`, não bloqueio.
- **Revisão adversarial com execução própria pegou dois falso-verdes que o relato não pegava.** O `tl-qa` **plantou a mutação e rodou** — provou que o teste de prova de concorrência estava verde por sorte de escalonamento (barreira no lugar errado) e que o ADR fazia overclaim de ancoragem. Um review por leitura teria aprovado.
- **design-flow antes de código evitou comprometer a porta.** O painel sintetizou o contrato `put->bool` + teste de conformação (garante P-12 por construção), preterindo conscientemente a opção de menor churn — decisão registrada, não improvisada.
- **Consolidar tarefas do mesmo arquivo numa passada.** T-S4-01+T-S4-04 (mesmo `ci.yml`) rodaram juntas — evitou dois PRs conflitantes no mesmo recurso.

## ⚠️ O que melhorar

- **O orquestrador errou a postura do gate frontend (warning) e o review corrigiu.** Decidi manter o `npm audit` como warning por analogia frouxa; era **fail-open** e incoerente com o `pip-audit` fail-closed do backend. Lição: a decisão consistente já existia (o backend acabara de fazer certo) — replicar o padrão, não inventar um mais fraco. Custo: 1 ciclo extra de review.
- **O teste de prova de concorrência foi entregue com a barreira no ponto errado.** O DETAIL §3.3 prescrevia a barreira no TOCTOU (`BarrierSyncedIdempotencyStore`); a 1ª implementação descartou e pôs no início do worker → falso-verde sob GIL. Seguir o DETAIL teria poupado o ciclo.
- **ADR não pode afirmar ancoragem que a suíte não prova.** O ADR dizia o lock in-memory era "ancorado por mutation-test"; sob GIL a corrida interna ao check-and-set não é interleavada. Corrigido para carve-out honesto (sonda forçada), coerente com o de visibilidade eventual.

## 🧠 Aprendizados técnicos (gotchas)

- **Barreira de corrida no ponto TOCTOU, não no início do worker.** Sob GIL, o vencedor completa `read→write→commit` antes de os outros alcançarem a leitura; perdedores caem no fast-path e o ramo mutado nunca roda → verde apesar do bug. Wrapper cuja `get()==None` dispara a barreira força o interleave. (→ `docs/lessons/qa.md`)
- **Corrida interna a check-and-set sob lock não é ancorável pela suíte threaded (CPython-GIL).** Demonstrar load-bearing por sonda forçada (sleep injetado), documentar como carve-out; não vender "ancorado". (→ `qa.md`)
- **Gate de audit: fail-closed + allowlist por-ID com `review-by`, nunca warning.** `... || true` é fail-open (High nova corrigível passa). A allowlist só dos residuais preserva a âncora do CVE fechado (reverter a dep → fora da lista → vermelho). Stacks simétricas. (→ `docs/lessons/security.md`)
- **`INSERT OR IGNORE` + `rowcount==1` é o árbitro atômico do claim write-once;** expor o veredito via `put->bool` é a fronteira certa da idempotência (não o `add` por PK do post). In-memory precisa de `threading.Lock` explícito (o SQLite ganha de graça do `INSERT OR IGNORE`).
- **Conexão SQLite compartilhada (`check_same_thread=False`): leitura concorrente sem o `_lock` levanta `InterfaceError`.** Fechar o TOCTOU do CREATE fez o footgun latente do SEC-06 aflorar; correção mínima (`IdempotencyStore.get` sob lock), sem acoplar o SEC-06 inteiro.

## 📐 Plano vs. realidade

- **A maior surpresa: rodar os audits reabriu o escopo.** O plano do PO tratava SEC-01/SEC-07 como "fechar o CVE conhecido"; a execução revelou CVEs **novos** (SEC-15 starlette auth-bypass; SEC-16 Angular residual) sem fix na linha atual — viram dívida, com o gate fail-closed guardando o que já fechou. Sintoma clássico de "premissa de spec envelhece entre escrita e execução".
- **Custo de ciclos:** cada tarefa exigiu 2 ciclos de review (nenhum escalonamento para `spec-*`). Os 2ºs ciclos foram de **integridade de gate/prova** (fail-closed, red-green determinístico, coerência de baseline), não de lógica de produção — o mesmo padrão da Sprint 3.
- **Pendências que ficam (não bloqueiam o MVP):** prova-de-wiring do gitleaks (branch efêmera, **pendente-de-push**); `requirements.lock` com hashes (**pendente-de-tooling**); SEC-15/SEC-16 (bumps major, dívida com `review-by: 2026-10-15`).

## 🧯 Dívidas registradas

- **SEC-15 — CVEs de deps do backend** (starlette auth-bypass via `fastapi`; pytest dev-only). Interino: `pip-audit` fail-closed com `--ignore-vuln` cirúrgico (`review-by: 2026-10-15`). Fechar: bump `fastapi`/`starlette`. Ver baseline.
- **SEC-16 — advisories residuais do Angular** (pós-bump, sem fix em 19.x, só major). Interino: `npm audit` fail-closed com allowlist por-ID. Fechar: bump major 19→20+.
- **SEC-07 parcial — `requirements.lock --generate-hashes`** pendente-de-tooling (`pip-compile`/`uv` ausentes); backend segue `pip install -e`.
- **T-S4-01 — prova-de-wiring do gitleaks** pendente-de-push (branch efêmera reprovando merge; o harness já prova a detecção in-CI).
- **Dívida residual do ADR-0007** — janela de falha parcial cross-table (claim→`add` não-atômico sob crash); pertence ao workstream transacional do **SEC-06**, não fechada aqui (§5/§8.6 do ADR).
- **SEC-06 latente** — só `IdempotencyStore.get` passou a serializar sob lock; leituras de `PostRepository` seguem como fronteira documentada (não chamar concorrente com escrita até SEC-06 fechar).

## 🔗 Memórias do agente geradas

- `blog-tutorial-sprint4-hardening` — Sprint 4 executada (SEC-01/02 fechados, SEC-03 via ADR-0007, SEC-07 parcial); gates de audit fail-closed com allowlist; dívidas SEC-15/16 + pendências de push/tooling.

## 🎓 Lições promovidas para `docs/lessons/`

- `qa.md` — barreira de corrida no ponto TOCTOU (não no início do worker); corrida interna a check-and-set sob lock não é ancorável pela suíte threaded (GIL) → carve-out honesto por sonda forçada.
- `security.md` — nova seção "Gates de vulnerabilidade de dependências": rodar o audit de verdade (premissa de spec envelhece); fail-closed + allowlist por-ID com `review-by` (nunca warning); gate vermelho-sem-caminho-para-verde é build quebrado; stacks simétricas; allowlist preserva a âncora do CVE fechado.
