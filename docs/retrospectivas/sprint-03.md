# Retrospectiva — Sprint 3 (frontend Angular + observabilidade + guia da trilha)

> Data: 2026-06-25 · Tarefas: T-S3-01..07 + backend response_model · Origem: sprint-flow

## Escopo entregue

A trilha fecha: **frontend Angular consumindo o contrato, observabilidade dia-1, e o guia didático**. O blog-tutorial cumpre os meta-marcos M1/M3/M4.

- **Backend S3:** F005 observabilidade (middleware ASGI único — request_id propagado aos handlers, sanitização reject-total, allowlist anti-PII, try/finally que nunca causa 500); F004.5 healthcheck `GET /v1/health`; `version="1.1.0"` alinhada ao contrato. Nova categoria de cobertura `observabilidade` (100%). — APROVADO 1 ciclo.
- **T-S3-01/02:** scaffold Angular 19 standalone signals-first; `BlogApiService` (único ponto HTTP) + interceptor RFC 9457; **codegen de tipos do OpenAPI vivo**; contract test real (Ajv + fixtures do TestClient); gate de drift; job de CI frontend (gate AND). — APROVADO 2 ciclos + pré-requisito de backend.
- **Backend response_model:** declarado em todos os endpoints (reusando `PostResponse`/`PageResponse`, +`HealthResponse`/`ApiError`) para o `/openapi.json` ter schemas reais. — verificado empiricamente.
- **T-S3-03/07:** telas listar (cursor)/ler (404 indistinguível)/criar+publicar (Idempotency-Key estável); 2º ratchet apertado (≤1pp global + piso por-arquivo do store); gate `tsc --noEmit`. — APROVADO 2 ciclos.
- **T-S3-06 (F008):** [`docs/guia-trilha-sdd.md`](../guia-trilha-sdd.md) — guia da espinha dorsal + checklist M4. — APROVADO pelo PO.

**Estado final:** backend 164 testes / 100% cobertura / 8 categorias de gate; frontend 96 testes / cobertura ≥ ratchet apertado + piso por-arquivo; CI com jobs separados (backend AND frontend), gate de drift de contrato + `tsc --noEmit` + 2º ratchet; `ng build` verde.

## ✅ O que funcionou (repetir)

- **Painel de revisão por múltiplos ângulos achou o furo arquitetural.** tl-python + tl-frontend + tl-qa, juntos, expuseram que o gate de contrato era **teatro** (codegen lia um JSON à mão). Um revisor só teria deixado passar.
- **Red-green do revisor como prova, não confiança no relato.** O tl-qa *plantou* o drift no Pydantic e confirmou o `git diff` vermelho — provando que a correção (codegen do app vivo) realmente fechou a cadeia `005↔OpenAPI↔TS`.
- **Fix de raiz > workaround.** Em vez de aceitar o augmented JSON como stopgap, corrigimos a causa (backend sem `response_model`). Barato (modelos já existiam) e eliminou o 2º source-of-truth.
- **Serializar backend→frontend** quando o segundo depende do contrato do primeiro evitou retrabalho.

## ⚠️ O que melhorar

- **Lição reaprendida na marca:** rodei o `tl-qa` (que **muta** para red-green) em paralelo com o `tl-frontend` (read-only) sobre `schemas.py` — o revisor read-only pegou a sonda em-voo e reportou um falso "probe deixado na árvore". É exatamente o anti-pattern já documentado em `process.md` ("um gate que MUTA e um revisor que LÊ o mesmo arquivo não rodam em paralelo"). Passei a **serializar** (read-only primeiro, mutador depois). A lição já existia — o custo foi não tê-la aplicado.
- **Gates ausentes só aparecem quando alguém procura.** O `tsc --noEmit` não existia; o Vitest fica verde sem typechecar, escondendo fixtures infiéis ao contrato. Faltava o gate, não o teste.
- **Toolchain nova traz gates novos.** Entrar com o frontend exigiu instituir 3 gates que o backend não tinha análogo direto: drift de contrato, `tsc --noEmit`, e 2º ratchet (gate AND, sem média global combinada).

## 🧠 Aprendizados técnicos (gotchas)

- **FastAPI sem `response_model` → `/openapi.json` com schemas de resposta VAZIOS** (`{}`). Qualquer tooling de contrato (codegen, client gen) recebe nada. Declare `response_model` (reusando os modelos Pydantic) — é o que materializa o API-First (P-01).
- **Pydantic v2 re-serializa `datetime` como `+00:00`** — se o contrato fixa o formato `Z` e a fonte já emite a string canônica, declare o campo de data como **`str`** no response model (não `datetime`), senão o formato observável muda e quebra o contrato.
- **Codegen e gate de drift DEVEM ler o app vivo, não um snapshot à mão.** Um JSON de contrato mantido manualmente é 2º source-of-truth: o `git diff --exit-code` só pega edição do snapshot, nunca o drift real do backend → gate teatro. Prove que morde plantando um campo no Pydantic → diff vermelho.
- **Vitest/esbuild NÃO typecheca** — a suíte fica verde com erros de tipo (fixture infiel ao tipo gerado). Wire `tsc --noEmit -p tsconfig.spec.json` (e do app) como gate de CI/pre-commit separado.
- **Cobertura de frontend precisa de piso por-arquivo**, não só global — `post-store.ts` (a lógica de negócio) ficava a 78% branch escondido na média. Vitest suporta `coverage.thresholds` com glob por arquivo (espelha o `coverage-gates.sh` por-categoria do backend).
- **Middleware de observabilidade nunca pode causar 500** — envolva a emissão de log/eco em try/except que não re-levanta; o `request_id` chega aos exception handlers via `request.state` (+ ContextVar de fallback), pois o middleware sozinho não os alcança.

## 📐 Plano vs. realidade

- **A maior surpresa foi o backend bloquear o frontend.** O plano tratava T-S3-01 como puramente frontend; na prática, o codegen do ADR-0005 só funciona com o backend declarando schemas — um **enabler de backend não previsto** (response_model) entrou no meio. Sintoma clássico de "refino não confrontou a capacidade real" (`process.md`): o ADR-0005 assumia OpenAPI completo, que o backend não entregava.
- **Custo de ciclos:** T-S3-01/02 e T-S3-03/07 exigiram 2 ciclos cada (os 2º ciclos foram de **integridade de gate** — drift real, tsc, ratchet — não de lógica). Backend obs/health e o guia, 1 ciclo. Nenhum escalonamento para especialista nas duas sprints.
- **Toolchain disponível:** Node 24/npm 11 presentes — o frontend rodou de verdade (não só scaffold).

## 🧯 Dívidas registradas

- **Schemas Ajv no contract.spec.ts ainda à mão** (espelham o OpenAPI em vez de carregá-lo) — fechar o último elo manual carregando de `components.schemas` do `/openapi.json` gerado.
- **`_to_response_dict` / `_log_error` / `_emit` duplicados** entre módulos — extrair serialização/emissão para helpers compartilhados (`application/serialization.py`, `observability.emit_event`). Candidatos a `debt-flow`.
- **Allowlist do evento de log de ERRO sem teste de igualdade exata** (só o de sucesso tem) — fechar a simetria anti-PII.
- **F006 (readiness/dashboard)** fora do MVP — só o healthcheck liveness entrou.

## 🔗 Memórias do agente geradas

- `blog-tutorial-sprint3-estado` — MVP completo (backend + frontend + observabilidade + guia); baseline de gates (backend 99/100 por-categoria; frontend ratchet + tsc + drift) e dívidas abertas.

## 🎓 Lições promovidas para `docs/lessons/`

- `python.md` — `response_model` para OpenAPI completo (API-First); `datetime`→`str` no response model para preservar formato `Z` de contrato.
- `qa.md` — codegen/drift gate do app vivo (não snapshot à mão), provado red-green; `tsc --noEmit` como gate (Vitest não typecheca); piso de cobertura por-arquivo no frontend (anti-diluição, espelha o backend).
- (reforço, já existente) `process.md` — não paralelizar revisor que muta com revisor read-only no mesmo arquivo (reaprendida nesta sprint).
