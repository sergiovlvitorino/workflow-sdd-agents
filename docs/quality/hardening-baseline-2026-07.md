# Quality — Baseline de Hardening / Segurança — 2026-07

> Registro da auditoria de segurança **defensiva** do MVP (`hardening-flow`). Severidade = impacto × exploitabilidade **no contexto deste sistema** (didático, local, sem auth por design — [ADR-0004](../../specs/adr/ADR-0004-publicacao-sem-autenticacao.md)), não CVSS genérico.
> Análogo de segurança do baseline de mutação: fixa o piso conhecido para não regredir e lista o que é dívida aceita.

**Escopo auditado:** app inteiro — backend FastAPI (`backend/src/blog`) + frontend Angular 19 (`frontend/src`) + CI (`.github/workflows`).
**Ferramentas de reverificação:** `pip-audit` (backend, **wired no CI** como gate fail-closed — T-S4-04), `npm audit --omit=dev --audit-level=high` (frontend, **wired no CI** como gate fail-closed com allowlist SEC-16 — T-S4-02).
**Última atualização:** 2026-07-15 _(Sprint 4 de hardening em execução — ver Histórico)_.
**Origem:** `hardening-flow` (Explore → painel tl-python + tl-frontend + tl-qa + sre → triagem); execução via `sprint-flow` (Sprint 4).
**Decisão do dono:** achados registrados como dívida; **Sprint 4** executa o MVP de hardening (SEC-01/02/03/07) — o restante segue dívida.

---

## Modelo de ameaça (calibra a severidade)

- App **didático, local, monousuário**; cliente real é o dev-aprendiz. **Sem auth por design** (ADR-0004) — não é achado, é premissa.
- Superfície de escrita anônima: `POST /v1/posts`, `PUT /v1/posts/{id}/publish` (`content` até 50k).
- Protege-se: integridade do conteúdo exibido (stored XSS = pior vetor), disponibilidade do processo, e os **pisos da constitution** (P-03 idempotência, P-04 rascunho-não-vaza, secret-scan bloqueante).
- Coluna Severidade já reflete o contexto real; `(prod)` indica o delta se exposto publicamente.

**Fundação correta — piso a NÃO regredir:** SQL 100% parametrizado; `X-Request-ID` sanitizado por rejeição total (fecha log-injection/CRLF); allowlist de status no GET (P-04 blindado byte-a-byte por teste); logging com allowlist anti-PII; escape universal por `{{ }}` no frontend (zero `innerHTML`/`bypassSecurityTrust`); nenhum segredo versionado; `.gitignore` cobre `*.db/*.pem/*.key/.env`; ESLint proíbe `innerHTML`/`any`; deps top-level pinadas exatas.

---

## Triagem consolidada (deduplicada entre as 4 lentes)

| ID | Achado | Local | Severidade (real / prod) | Piso |
|----|--------|-------|--------------------------|------|
| SEC-01 | ~~Angular 19.2.14 → CVE-2025-66412 (stored XSS via bypass de sanitização, CVSS 8.5)~~ **FECHADO** (Sprint 4, T-S4-02: bump → 19.2.25) | `frontend/package.json:22-29` | ~~**Alto**~~ | — |
| SEC-02 | gitleaks só em pre-commit, ausente no CI | `.pre-commit-config.yaml:30` vs `ci.yml` | **Alto** | Secret-scan bloqueante (CLAUDE.md) |
| SEC-03 | TOCTOU de idempotência no CREATE → post duplicado sob concorrência | `application/create_post.py:47-64` | **Médio** (Baixo single-user) | **P-03** |
| SEC-04 | Sem body-size-limit → DoS/OOM em POST anônimo | `interfaces/posts_router.py`, `main.py:48-101` | **Médio** (Alto prod) | — |
| SEC-05 | `idempotency_keys` sem TTL/eviction → disk exhaustion | `infrastructure/sqlite_repository.py:63-67,223-230` | **Médio** (Baixo local) | — |
| SEC-06 | I/O SQLite síncrono em handler `async` bloqueia event loop; leituras na conexão compartilhada sem lock (latente) | `posts_router.py`, `sqlite_repository.py:162-194` | **Médio** | — |
| SEC-07 | CI: `GITHUB_TOKEN` sem `permissions`; Actions por tag mutável; backend sem lockfile/pip-audit | `.github/workflows/ci.yml`, `backend/pyproject.toml` | **Médio** | — |
| SEC-08 | Sem Content-Security-Policy no `index.html` | `frontend/src/index.html` | **Médio** | — |
| SEC-09 | `docs`/`openapi`/`redoc` expostos + bind `0.0.0.0` + `reload=True` no entrypoint | `main.py:60,104-109` | **Médio** (prod) / **Baixo** (tutorial) | — |
| SEC-10 | `except (..., Exception)` amplo no decode do cursor mascara bug de programação | `application/cursor.py:47` | **Baixo** (higiene) | Tensão P-11 |
| SEC-11 | Sem handler catch-all → resposta 500 sai sem `X-Request-ID` | `main.py:95-99`, `observability.py:151` | **Baixo** | — |
| SEC-12 | `content` de 50k sem `overflow-wrap` estoura layout horizontal | `features/post-detail/post-detail.ts:55` | **Baixo** (cosmético) | — |
| SEC-13 | Sem `TrustedHostMiddleware` (Host header) | `main.py` | **Baixo** | — |
| SEC-14 | Permissão do arquivo `.db` (umask default, world-readable em host multiusuário) | `sqlite_repository.py:96` | **Baixo** (prod) | — |
| SEC-15 | Deps de backend com CVE (achado por `pip-audit` real, 2026-07-15): `starlette 0.38.6` (transitiva de `fastapi==0.115.0`) com auth-bypass "BadHost" + outras; `pytest 8.3.3` (dev) | `backend/pyproject.toml:10-25` | **Alto** (prod, via starlette) | — |
| SEC-16 | Angular com advisories novas pós-bump (achado por `npm audit` real, T-S4-02): 7 High + 1 moderate em `@angular/*` 19.2.25 **sem fix na linha 19.x** — só em major (20.3.25 / 21.2.17 / 22.0.1). Ex.: GHSA-48r7-hpm6-gfxm, GHSA-39pv-4j6c-2g6v, GHSA-58w9-8g37-x9v5, GHSA-rgjc-h3x7-9mwg | `frontend/package.json:22-29` | **Alto** (prod) | — |

---

## 🧯 Dívidas registradas

Idioma da retro (`docs/retrospectivas/`): título — ação de fechamento + teste de prova + fluxo candidato. Cada correção deve entrar via `hardening-flow`/`review-loop` com o **teste que nasce vermelho antes do fix**.

**Alto**
- **SEC-01 — ✅ FECHADO (Sprint 4, T-S4-02).** Angular 19.2.14 → CVE-2025-66412 (stored XSS via bypass de sanitização; CVSS 8.5). Resolvido pelo bump `@angular/*` 19.2.14→**19.2.25** (CLI 19.2.27), pin exato; `GHSA-v4hv-rgfq-gp49` confirmadamente saiu do `npm audit`. Regressão zero (114/114 testes, tsc/lint/drift/build verdes). Guardado por gate fail-closed (ver SEC-16). Sucessor: **SEC-16** (advisories residuais do Angular, fix só em major).
- **SEC-02 — ✅ FECHADO (Sprint 4, T-S4-01).** gitleaks só em pre-commit → job `secret-scan` bloqueante no CI (gitleaks-action pinada por SHA, `GITLEAKS_VERSION 8.18.4` = paridade pre-commit, `fetch-depth: 0`, `permissions: contents: read`). Harness de canário em tmpdir prova detecção dentro do CI. **Pendente-de-push:** prova-de-wiring (branch efêmera reprovando merge).

**Médio**
- **SEC-03 — TOCTOU de idempotência no CREATE viola P-03** (`create_post.py:47-64`): dois POST concorrentes, mesma key+payload, veem `get(key)=None` e persistem **dois posts** com ids distintos; o `INSERT OR IGNORE` write-once chega depois do `add()`. **Fechar:** claim-da-chave-primeiro (checar `rowcount`) **ou** `post_id` derivado da idem-key (upsert idempotente). **Prova (vermelha hoje):** `ThreadPoolExecutor`, N POSTs mesma key+payload → `post_repo.count()==1` e mesmo id em todas as respostas. Candidato a `bug-flow`.
- **SEC-04 — Sem body-size-limit → DoS/OOM** (`main.py:48-101`): o `max_length=50000` só é checado após o Starlette materializar o corpo inteiro. **Fechar:** middleware ASGI que rejeita por `Content-Length` acima de ~128 KB → 413. **Prova:** POST oversized → 413 antes de materializar. Candidato a `hardening-flow`.
- **SEC-05 — `idempotency_keys` sem TTL → disk exhaustion** (`sqlite_repository.py:63-67`): cada key nova grava linha permanente (`response_json` até 50k). **Fechar:** coluna `created_at` + purga por janela; teto no valor persistido; validar tamanho/charset do header. **Prova:** key além da janela é removida pela purga; header oversized rejeitado. Candidato a `hardening-flow`.
- **SEC-06 — I/O SQLite bloqueia event loop + leituras sem lock** (`sqlite_repository.py:162-194`): chamada síncrona no thread do loop trava tudo (inclui `/v1/health`). **Cuidado:** corrigir o bloqueio com `run_in_threadpool`/handler `def` **sem** proteger as leituras faz surgir race real na `Connection` compartilhada → vira **Alto**. **Fechar os dois juntos.** **Prova:** leituras+escritas paralelas sem `ProgrammingError`; `/v1/health` responde durante leitura pesada. Candidato a `debt-flow`.
- **SEC-07 — Gaps de supply-chain no CI:** `GITHUB_TOKEN` sem `permissions` (herda write); Actions por tag mutável (`@v4/@v5`); backend sem lockfile/hash-pinning. **Fechar:** `permissions: contents: read`; pinar Actions por SHA; `requirements.lock --generate-hashes` + `--require-hashes` + `pip-audit`. **Prova:** CI verde com deps por hash; audit falha em CVE High. Candidato a `hardening-flow`.
- **SEC-08 — Sem CSP** (`index.html`): segunda linha de defesa que conteria XSS futuro (compõe com SEC-01). **Fechar:** CSP restritiva (`default-src 'self'; script-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'`) — meta agora, header HTTP no deploy. **Prova:** teste de presença do header/meta + e2e de bloqueio de script inline. Candidato a `hardening-flow`.
- **SEC-09 — Postura de prod no entrypoint** (`main.py:60,104-109`): `/docs`/`/openapi` abertos, bind `0.0.0.0`, `reload=True` (dev-server). **Fechar:** manter `__main__` dev-only documentado; em prod `docs_url/openapi_url=None` por env, bind `127.0.0.1`, `reload=False`, atrás de proxy com limites. **Prova:** com flag "prod", `/docs`→404.

**Alto (descoberto na execução da Sprint 4)**
- **SEC-16 — Angular com advisories novas pós-bump (npm audit real, T-S4-02).** O bump 19.2.14→19.2.25 **fechou o SEC-01** (CVE-2025-66412), mas `npm audit --omit=dev --audit-level=high` revelou **7 High + 1 moderate** em `@angular/*` publicadas depois do DETAIL, **sem fix na linha 19.x** — só em major (`20.3.25`/`21.2.17`/`22.0.1`). Ex.: GHSA-48r7-hpm6-gfxm, GHSA-39pv-4j6c-2g6v, GHSA-58w9-8g37-x9v5, GHSA-rgjc-h3x7-9mwg. **Interino (Sprint 4):** `npm audit --omit=dev --audit-level=high` é gate **fail-closed** com guard `node` inline (sem nova dep) que faz allowlist cirúrgica **só** desses GHSA (cada um com `review-by: 2026-10-15`) — qualquer High/Critical fora da lista reprova o CI. Simétrico ao `pip-audit`/SEC-15 do backend; reverter o Angular para <19.2.17 traz o CVE-2025-66412 de volta como residual → vermelho (âncora do SEC-01). **Fechar:** bump major do Angular (19→20+), com migração e regressão completa, esvaziando a allowlist. Candidato a `hardening-flow`/`sprint-flow` dedicado. **Prova:** `npm audit --omit=dev --audit-level=high` verde após o major bump.
- **SEC-15 — Deps de backend com CVE (pip-audit real, 2026-07-15).** Rodar `pip-audit` de verdade (T-S4-04) desenterrou CVEs não previstos no baseline original: **`starlette 0.38.6`** (transitiva de `fastapi==0.115.0`) com **auth-bypass "BadHost"** (PYSEC-2026-161, fix ≥1.0.1) + PYSEC-2026-248/249/1941/1943/2280/2281; **`pytest 8.3.3`** dev-only (PYSEC-2026-1845, fix 9.0.3). O fix do starlette **exige bump do `fastapi`** (0.115.0 pina starlette <0.41.0), potencial quebra de compat → tarefa própria. **Interino (Sprint 4):** `pip-audit --ignore-vuln` cirúrgico por advisory com justificativa + prazo de revisão, mantendo o gate bloqueante e verde. **Fechar:** bump `fastapi`/`starlette` (fecha o auth-bypass de prod) + `pytest`≥9.0.3; ao existir `requirements.lock`, `pip-audit -r requirements.lock` remove o ruído de toolchain (advisories do `pip` do runner). Candidato a `hardening-flow`/`debt-flow` dedicado. **Prova:** `pip-audit` verde sem ignores após bump.

**Baixo (higiene)**
- **SEC-10 — `except (..., Exception)` amplo no cursor** (`cursor.py:47`) engoliria bug de programação como 400 (tensão P-11). **Fechar:** estreitar para `(KeyError, ValueError, TypeError, UnicodeDecodeError)` (`binascii.Error ⊂ ValueError`). **Prova:** erro inesperado **não** vira 400 silencioso.
- **SEC-11 — 500 sem `X-Request-ID`** (`main.py:95-99`): sem handler catch-all, exceção inesperada perde correlação (não vaza stack — sem `debug=True`). **Fechar:** handler global `Exception` → Problem Details genérico com `X-Request-ID`.
- **SEC-12 — Layout de 50k** (`post-detail.ts:55`): `overflow-wrap: anywhere; white-space: pre-wrap` no `.post-content` (cosmético).
- **SEC-13 — Sem `TrustedHostMiddleware`:** allowlist de Host em prod (hardening barato; app não gera URLs absolutas).
- **SEC-14 — Permissão do `.db`:** restringir a 0600 arquivo+diretório em prod. `BLOG_DB_PATH` vem só de env (fronteira do operador) — **não** é vetor de path traversal.

---

## Decisões conscientes do ADR-0004 (NÃO são bugs — callout didático)

Registrar no material didático como exemplos de _decisão registrada_ vs. bug — reforça o callout **"em produção, escrita exige autenticação"**:

- **`PUT /publish` é oráculo de existência + transição aberta** que devolve o `content` do rascunho. Consequência explícita da transição aberta (ADR-0004 §4). IDs são ULID (~128 bits), não enumeráveis — exploração prática limitada.
- **Namespace global de `Idempotency-Key`** (sem tenant) permite squatting/replay cross-client. Consequência aceita do "sem auth/monousuário".
- **`content` persistido verbatim** (escape é no render, não no store): backend devolve JSON (escape por construção), frontend auto-escapa. Bom gancho para "por que não sanitizar HTML na persistência".

---

## Ordem de fechamento sugerida (esforço baixo × ganho alto)

1. **SEC-02** (gitleaks no CI) — fecha piso não-negociável, custo baixo.
2. **SEC-01** (bump Angular ≥19.2.17 + `npm audit` gate) — fecha CVE High, `ng update` trivial.
3. **SEC-07** (`permissions: contents: read` + pin SHA + `pip-audit`) — least-privilege de CI.
4. **SEC-04** (body-size-limit) + **SEC-08** (CSP) — hardening de borda barato.
5. **SEC-03** (TOCTOU P-03, com teste red-green) — único piso de constitution quebrado.
6. **SEC-06** (threadpool + lock nas leituras, **em conjunto**), **SEC-05** (TTL), **SEC-09** (postura prod) — maior; tratar quando fizer sentido no escopo didático.
7. Higiene: **SEC-10/11/12/13/14**.

---

## Como reverificar

```bash
# Backend — vulnerabilidades de dependências
cd backend && pip install pip-audit && pip-audit

# Frontend — vulnerabilidades de dependências (falha em High)
cd frontend && npm audit --audit-level=high

# Secret-scan do histórico (o mesmo hook do pre-commit, manual)
gitleaks detect --source . --redact
```

## Histórico

| Data | Evento | Detalhe |
|---|---|---|
| 2026-07-15 | `hardening-flow` — baseline criado | 14 achados triados (0 Crítico, 2 Alto, 7 Médio, 5 Baixo). Registrados como **dívida** por decisão do dono; nenhum fix aplicado. Fundação defensiva verificada como piso a não regredir. |
| 2026-07-15 | `sprint-flow` Sprint 4 — MVP de hardening | ADR-0007 (contrato de concorrência `IdempotencyStore`) aceito. **SEC-02 FECHADO** (gitleaks bloqueante no CI + guard estático `test_ci_hardening.py` + harness canário). **SEC-01 FECHADO** (bump Angular 19.2.14→19.2.25; CVE-2025-66412 saiu do `npm audit`; regressão zero). **SEC-07** parcial (least-privilege + pin SHA + `pip-audit`/`npm audit` fail-closed + dependabot; `requirements.lock` pendente-de-tooling). **SEC-03** (TOCTOU) em execução. **Novas dívidas descobertas na execução:** SEC-15 (CVEs backend: starlette/pytest) e SEC-16 (advisories residuais Angular, fix só em major). |
