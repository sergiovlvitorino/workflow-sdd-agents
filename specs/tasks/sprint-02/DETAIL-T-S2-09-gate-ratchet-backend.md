# DETAIL — T-S2-09 — Gate ratchet backend (subir o piso + pisos por-categoria sem diluir)

**Sprint:** 02
**Tamanho:** M _(estimativa)_
**Papel:** QA (`qa` / `spec-qa`) + TL revisão (`tl-qa` + `tl-python`)
**Depende de:** T-S2-08 (os testes de F002/F004 existem e medem), T-S2-04 (adapter SQLite `sqlite_repository.py` existe e é importável pela cobertura), T-S2-05/06/07 (módulos `publish_post.py`, router publish, `get_post.py` existem — definem os paths dos globs por-categoria)
**Bloqueia:** — (fecha a Sprint 2 do backend; é o gate que protege as entregas T-S2-04..08)

> Produzido por `tl-qa` no sprint-flow; consumido pelo `review-loop`. Eleva o **ratchet** ao patamar realmente atingido e institui **pisos por-categoria que não diluem na média global** (ADR-0003 §8; P-07; `007-test-strategy.md` §2-3; `qa.md` "o gate do scaffold nasce no patamar").

---

## 1. Objetivo

Subir o piso de cobertura backend ao patamar real atingido após F002/F004, garantir `--cov-branch` e `pytest-randomly` pinados, e adicionar **pisos por-categoria** (P-07) — em especial para os módulos novos (adapter SQLite `sqlite_repository.py` de T-S2-04, `PublishPost`/`publish_post.py` de T-S2-05, read-by-id `get_post.py` de T-S2-07) — **sem** deixar a média global esconder um módulo fraco. O gate só vale se **morde**: derrubar a cobertura de um módulo novo tem que reprovar o CI.

## 2. CAs / RNs cobertos

- Não realiza CA de negócio; **protege** todos os CAs de Sprint 1+2 contra regressão de cobertura (P-07 ratchet; P-13 DoD).
- **ADR-0003 §8:** "piso de cobertura próprio do adapter, **não diluído** na média global do pacote".
- **`007-test-strategy.md` §2-3:** ratchet por-stack; pisos por categoria de risco; "prove que o gate morde".

## 3. Arquivos a criar/alterar

| Path | Ação | Descrição |
|---|---|---|
| `backend/pyproject.toml` | alterar | Subir `--cov-fail-under` ao patamar real; manter `--cov-branch`; manter `pytest-randomly` pinado; configurar `[tool.coverage.run]` (`branch=true`, `source`). |
| `backend/coverage-gates.sh` (ou `Makefile` alvo `cov-gates`) | criar | Script que roda os **pisos por-categoria** via `coverage report --include=<glob> --fail-under=<N>` por categoria, **separado** do gate global. É o juiz do CI (`process.md`: o juiz é o comando do CI). |
| `backend/.github/workflows/ci.yml` (ou equivalente já existente) | alterar | Wire do `coverage-gates.sh` no pipeline (gate global **AND** gates por-categoria; merge bloqueia se qualquer um reprovar). |
| `docs/quality/mutation-baseline-sprint-02.md` | criar | Registrar baseline (a partir do `_TEMPLATE`), incluindo as âncoras M3/M9 de T-S2-08. |

## 4. Design da solução — número exato e medição por-categoria

### 4.1 O novo número do gate global

- **Hoje:** `--cov-fail-under=95` (global, line+branch via `--cov-branch`), `pytest-randomly==3.16.0` já pinado, `--cov-branch` já presente. ✔ os três pré-requisitos básicos do `qa.md` "scaffold" já existem — **não regredir**.
- **Regra (`qa.md`: "ratchet nasce no patamar atingido, com folga mínima — não num número redondo"):** medir a cobertura real **depois** de T-S2-08 verde e fixar o piso global em **`floor(real) - 0` a `-1`** (folga máxima de 1 ponto para ruído de medição), **arredondando para baixo**, nunca para um número redondo abaixo do real.
- **Procedimento de fixação (executar no review-loop, não chutar agora):**
  1. Rodar a suíte completa: `pytest` (com `--cov=blog --cov-branch`).
  2. Ler o `TOTAL` do `term-missing` (line+branch combinados).
  3. Novo `--cov-fail-under` = esse `TOTAL` truncado, com no máximo 1 ponto de folga.
- **Alvo esperado:** com os adapters SQLite + os testes de F002/F004, o `TOTAL` deve **subir** de ~95 para **≥ 96–97**. **O número fixado é o medido**, não o estimado aqui. Condição dura: o novo piso **≥ 95** (nunca abaixo do atual — ratchet só sobe; rebaixar exige ADR — P-07).
- **Anti-diluição:** o gate global **sozinho** mascara um adapter fraco (um módulo a 60% somado a um pacote a 98% ainda passa um piso global de 95). Por isso o global é **necessário mas não suficiente** — os pisos por-categoria (§4.2) são o complemento obrigatório.

### 4.2 Pisos por-categoria sem diluir na média global

O `--cov-fail-under` do pytest-cov é **um único número global**. Para não diluir, medir cada categoria com `coverage report --include=<glob> --fail-under=<piso>` em invocações **separadas** sobre o **mesmo** `.coverage` gerado pela suíte (não re-rodar a suíte por categoria). Cada linha reprova **independentemente** (gate AND).

> **Paths dos globs — a confirmar no review-loop.** Os caminhos abaixo refletem os DETAILs canônicos de código (T-S2-04: `infrastructure/sqlite_repository.py`; T-S2-05: `application/publish_post.py`; T-S2-07: `application/get_post.py`; router/erros em `interfaces/`). Se o dev escolher outro nome de módulo, **ajustar o glob** — a sentinela anti-glob-vazio (§6) reprova se o `--include` não casar arquivo, então um path errado falha o gate (não passa vacuamente).

```sh
# backend/coverage-gates.sh — roda DEPOIS de `pytest` ter gerado .coverage
set -euo pipefail

# 1) Gate global (já no pytest addopts, repetido aqui como cinto-e-suspensório)
coverage report --fail-under=<GLOBAL>            # ex.: 96 (medido em §4.1)

# 2) Adapters SQLite (ADR-0003 §8 — piso PRÓPRIO, não diluído). P-07 "Integrações/adapters" >= 80; QA ajusta p/ cima.
#    Path canônico T-S2-04: src/blog/infrastructure/sqlite_repository.py
coverage report --include="src/blog/infrastructure/sqlite_*.py" --fail-under=90

# 3) Domínio crítico — máquina de estados (Post.publish em domain/post.py) + create. P-07 >= 90 linha + 100 branch crítico.
coverage report --include="src/blog/domain/*.py" --fail-under=95

# 4) Idempotência + casos de uso de ESCRITA (rota de escrita = 100%). P-07 idempotência 100%.
#    Path canônico T-S2-05: src/blog/application/publish_post.py
coverage report --include="src/blog/application/create_post.py,src/blog/application/publish_post.py" --fail-under=100

# 5) Isolamento/autorização — read-by-id com allowlist (P-04). P-07 "Isolamento" = 100% dos cenários.
#    Path canônico T-S2-07: src/blog/application/get_post.py (allowlist `status is PUBLISHED`)
coverage report --include="src/blog/application/get_post.py" --fail-under=100

# 6) API pública (router — inclui PUT publish de T-S2-06 e GET /{id} de T-S2-07). P-07 API 100% dos endpoints.
coverage report --include="src/blog/interfaces/posts_router.py" --fail-under=100

# 7) Falha explícita (handlers de erro tipado RFC 9457, inclui post_not_found). P-11.
coverage report --include="src/blog/interfaces/errors.py" --fail-under=100
```

> **Nota:** os globs `--include` devem casar os caminhos **reais** que T-S2-04..07 criarem. Conferir os paths no review-loop — um `--include` que não casa arquivo **passa vacuamente** (`coverage` reporta 100% de 0 linhas). **Mitigação obrigatória (§6):** o script falha se a categoria medir **0 statements** (sentinela anti-glob-vazio), senão é falso-verde estrutural (`qa.md`: "sentinela `>0` mascara truncamento").

### 4.3 Pinagem e determinismo (confirmar, não regredir)

- **`--cov-branch`:** já presente em `addopts`; manter. Adicionar `[tool.coverage.run] branch = true` para que as invocações `coverage report` de §4.2 também enxerguem branch (senão medem line-only e mascaram branch descoberto — `qa.md`: "`--cov-branch` obrigatório quando o piso exige branch").
- **`pytest-randomly==3.16.0`:** já pinado em `dev`; manter. O CI roda a suíte sob ordem aleatória — o gate de determinismo só existe pinado (`qa.md`: "ferramenta instalada ≠ pinada").
- **`source`/`concurrency`:** o blog é **síncrono** (in-memory + `sqlite3` stdlib) — **não** precisa `concurrency=["greenlet"]` (só se um adapter async entrar — `qa.md`). Registrar isso para não adicionar config inerte.

### 4.4 Prova de que o gate morde (red-green do gate)

Antes de declarar pronto, **provar a catraca** (`qa.md`/`007` §2 "prove que o gate morde"; **reverter com Edit na linha exata, nunca `git checkout`** — CLAUDE.md):

1. **Global:** comentar (via Edit) um assert de um teste de F002 que cobre um branch → `coverage report --fail-under=<GLOBAL>` **reprova**. Reverter por Edit.
2. **Adapter:** remover (via Edit) o teste de durabilidade entre conexões → o gate `--include=sqlite_*` cai abaixo de 90 → **reprova**. Reverter.
3. **Idempotência:** remover o teste de replay → categoria idempotência < 100 → **reprova**. Reverter.
4. **Anti-glob-vazio:** apontar um `--include` para um arquivo inexistente → o script **falha pela sentinela de 0 statements**, não passa vacuamente.

## 5. Impacto em testes e quality gates

- **Não cria teste de negócio** — consome os de T-S2-08.
- **Gates afetados:**
  - `--cov-fail-under` global **sobe** ao patamar medido (≥ 95, esperado 96–97) — ratchet.
  - **Novos gates por-categoria** (adapter SQLite, domínio, idempotência/escrita, isolamento read-by-id, API, erros) barrados **separadamente** (gate AND com o global).
  - `--cov-branch` e `pytest-randomly` confirmados pinados.
- **Por-stack (ADR-0001 §4.1):** ainda só o ratchet backend existe (front fora). A regra "**nunca média global combinada** back+front" fica registrada para quando o 2º job nascer — **não** somar stacks.

## 6. Riscos

- **`--include` que não casa arquivo passa vacuamente** (categoria de 0 linhas → 100%). Mitigação: sentinela que reprova se `coverage report` da categoria reportar `0` statements; conferir paths reais criados por T-S2-04..07 antes de fixar os globs.
- **Fixar o piso num número redondo abaixo do real** (ex.: 95 quando o real é 97) = ratchet teatral desde o dia 1 (`qa.md`). Mitigação: piso = `floor(real)` com folga ≤ 1.
- **Gate não-wired é inerte** (`qa.md`): definir os pisos no `pyproject`/script mas não rodá-los no CI = gate que não existe. Mitigação: `coverage-gates.sh` aparece **rodando** no pipeline (DoD).
- **Diluição silenciosa:** confiar só no global esconde adapter fraco. Mitigação: §4.2 obrigatório, não opcional.
- **Reverter sonda com `git checkout`** apaga trabalho não-commitado adjacente (CLAUDE.md). Mitigação: red-green do gate via **Edit** na linha exata, sempre.
- **Rebaixar o piso para "fazer o CI passar"** é proibido sem ADR (P-07). Se algum módulo novo não alcançar o piso da categoria, a resposta é **escrever o teste** (volta a T-S2-08), não baixar o número.

## 7. Definition of Done (verificável)

- [ ] `--cov-fail-under` global **subido ao patamar medido** (≥ 95, número = `floor(TOTAL real)`, folga ≤ 1), commitado em `pyproject.toml`.
- [ ] `--cov-branch` presente em `addopts` **e** `branch=true` em `[tool.coverage.run]`.
- [ ] `pytest-randomly==3.16.0` pinado em `dev` (confirmado, não removido).
- [ ] `coverage-gates.sh` (ou alvo equivalente) com pisos por-categoria: adapter SQLite ≥ 90, domínio ≥ 95 (+100 branch crítico), idempotência/escrita = 100, isolamento read-by-id (`get_post.py`) = 100, API router = 100, erros = 100 — **cada um barrando separadamente**.
- [ ] Sentinela anti-glob-vazio: categoria com 0 statements **reprova** (não passa vacuamente).
- [ ] Gate **wired no CI** e visto **rodando** (global AND por-categoria).
- [ ] **Red-green do gate provado** (§4.4): derrubar cobertura de propósito (via Edit) reprova; reverter restaura verde.
- [ ] Baseline de mutation registrada em `docs/quality/mutation-baseline-sprint-02.md` (inclui M3 no-op publish, M9 `<`→`<=` keyset SQLite).
- [ ] Nenhum piso **rebaixado** sem ADR; ratchet só subiu.
- [ ] Revisão aprovada (`tl-qa` + `tl-python`) sem ressalvas.
