# DETAIL — T-S3-07 — 2º ratchet de cobertura do frontend (gate AND, barrado separado do backend)

**Sprint:** 03
**Tamanho:** M _(estimativa)_
**Papel:** QA (`qa` / `spec-qa`) + TL revisão (`tl-qa` + `tl-frontend`)
**Depende de:** T-S3-01 (scaffold Angular: `frontend/` com runner de teste — Vitest **ou** `ng test`/Karma — e `package.json`), **T-S3-03** (os componentes/serviço já têm **testes que medem** — sem testes não há patamar para fixar; um ratchet sobre suíte vazia é teatro). Backend já tem ratchet global 99 + 6 categorias a 100 (`backend/coverage-gates.sh`, `.github/workflows/ci.yml`).
**Bloqueia:** fechamento da Sprint 3 do front (protege as entregas de UI contra regressão de cobertura).

> Produzido por `tl-qa` no `sprint-flow`; consumido pelo `review-loop`. Ativa o **2º ratchet** previsto em `007-test-strategy.md` §2/§6 e `004-non-functional-requirements.md`, com a regra **inegociável** do ADR-0001 §4.1: dois ratchets independentes (pytest de um lado, runner do front do outro), **gate AND** no CI, **nunca média global combinada**. Ver `docs/lessons/qa.md` ("o gate do scaffold nasce no patamar", "ratchet que morde", "ferramenta instalada ≠ pinada", "lint vs build").

---

## 1. Objetivo

Instituir o **piso de cobertura do frontend** como gate **bloqueante e não-regressivo (ratchet)**, medido no **patamar real** atingido pelos testes de T-S3-03, barrado **separadamente** do backend (gate AND — merge reprova se *qualquer* lado cair), determinístico (zero flaky), e **wired** no `.github/workflows/ci.yml` num job do front a partir da raiz. Inclui **sentinela anti-suíte-vazia/teatro** — um ratchet sobre 0 testes (ou testes que não exercem nada) é falso-verde estrutural.

## 2. CAs / RNs cobertos

- **Não realiza CA de negócio** — protege os CAs da UI (T-S3-03) contra regressão de cobertura (P-07 ratchet; P-13 DoD).
- **ADR-0001 §4.1 (inegociável):** dois ratchets por stack, gate AND, **proibida** média global combinada back+front (mascara lado fraco: back 99% + front 40% ≈ "verde" com metade descoberta).
- **`007` §2/§6:** "Segundo ratchet (front), barrado separadamente. Gate AND com o ratchet Python; nunca média global."
- **`004`:** ativa o 2º ratchet quando o Angular entrar.

## 3. Arquivos a criar/alterar

| Path | Ação | Descrição |
|---|---|---|
| `frontend/package.json` | alterar | Script `test:cov` que roda o runner com cobertura **+ piso bloqueante** (Vitest: `--coverage.thresholds.lines/branches/...`; ou `ng test --code-coverage` + checador). Pinar o provider de cobertura (`@vitest/coverage-v8` ou `karma-coverage`). |
| `frontend/vitest.config.ts` (ou `karma.conf.js`) | alterar | Configurar `coverage` (provider, `include`/`exclude`, `thresholds` = piso medido), `reporter` determinístico, e **`coverage.all: true`** (conta arquivos não-importados como 0% — anti-teatro). Modo CI sem watch. |
| `frontend/scripts/coverage-gate.sh` (se o runner não barrar por threshold nativamente) | criar | Sentinela: falha se total de arquivos/linhas medidos < piso mínimo (anti-suíte-vazia) **e** aplica os thresholds. Juiz do CI. |
| `.github/workflows/ci.yml` | alterar | Adicionar **job `frontend`** (ou steps), a partir da raiz com `working-directory: frontend`: instala deps pinadas → roda `test:cov` (gate de cobertura do front) → roda sob ordem aleatória/seed determinística. **Separado** do job backend (gate AND). |

> **Nomes a confirmar no review-loop** conforme o runner que T-S3-01/03 cravarem. Se for `ng test`/Karma, o piso vai em `karma.conf.js` (`coverageReporter.check`); se Vitest, em `vitest.config.ts` (`test.coverage.thresholds`). O gate só vale apontando para a config real.

## 4. Design da solução

### 4.1 O piso nasce no patamar MEDIDO, nunca num número redondo

`qa.md` "ratchet nasce no patamar atingido, com folga mínima — não num número redondo": fixar o piso num `60`/`80` redondo enquanto o real é ~92 deixa apagar a maioria dos testes com o CI verde — ratchet teatral desde o dia 1.

**Procedimento de fixação (executar no review-loop com T-S3-03 verde, não chutar agora):**
1. Rodar `npm run test:cov` e ler o **TOTAL** de cobertura por métrica (lines, statements, branches, functions).
2. Fixar cada threshold = `floor(real)` com **folga ≤ 1 ponto** por métrica.
3. Exigir **branch coverage** explícito (não só lines): branch é onde a assimetria nasce (`qa.md`; análogo ao `--cov-branch` do backend). Um `*ngIf`/`@if` testado só no caminho verdadeiro deixa o branch falso descoberto.

```ts
// frontend/vitest.config.ts — thresholds = patamar MEDIDO (exemplo de estrutura, números no review-loop)
export default defineConfig({
  test: {
    environment: 'jsdom',
    coverage: {
      provider: 'v8',
      all: true,                       // arquivos não-importados contam como 0% (anti-teatro)
      include: ['src/app/**/*.ts'],
      exclude: ['src/app/api/generated/**', '**/*.spec.ts', 'src/main.ts'],
      reporter: ['text', 'json-summary'], // json-summary alimenta a sentinela
      thresholds: {                    // PISO = floor(real medido em T-S3-03), folga <=1
        lines: 0,        // <- preencher no review-loop com o medido
        statements: 0,   // <-
        branches: 0,     // <- branch obrigatório
        functions: 0,    // <-
      },
    },
  },
});
```

> **Exclusão do arquivo gerado é obrigatória e justificada:** `src/app/api/generated/openapi-types.ts` é artefato derivado (ADR-0005 §8) — cobri-lo é cerimônia. A exclusão é **logada** no config (não silenciosa). Tudo o que **não** for gerado/spec/bootstrap **conta**.

### 4.2 Gate AND, NUNCA média global combinada (ADR-0001 §4.1)

Os dois ratchets são **jobs/steps distintos** no CI. O merge reprova se **qualquer** um falhar (AND). É **proibido** somar coberturas back+front num único número — isso mascara um lado fraco. O job backend (`pytest` + `coverage-gates.sh`) e o job frontend (`test:cov`) **não compartilham** artefato de cobertura nem piso.

```yaml
# .github/workflows/ci.yml — 2º job, independente do backend
  frontend:
    name: Front — testes + cobertura (2º ratchet)
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - run: npm ci                       # deps pinadas (lockfile) — pin bloqueante
      - name: Testes + cobertura (piso = ratchet do front)
        run: npm run test:cov             # barra se < threshold OU suíte vazia
```

> O gate AND é estrutural no GitHub Actions: dois jobs obrigatórios; o merge na `main` exige **ambos** verdes (branch protection). Registrar que **back+front nunca viram um número só**.

### 4.3 Determinismo (flaky = P1)

`007` §2: "Zero tolerância; flaky = P1. Suíte passa em qualquer ordem e sem rede externa." Aplicado ao front:
- **Ordem aleatória:** Vitest embaralha por padrão (`sequence.shuffle`) — manter ligado, com `seed` registrado se precisar reproduzir; é o análogo do `pytest-randomly` (pinado no back). Karma: randomizar a ordem dos specs.
- **Sem `setTimeout`/`sleep` para sincronizar.** Usar `fakeAsync`/`tick` (Angular) ou `vi.useFakeTimers()` — controle de tempo, nunca espera real (`qa.md` anti-flaky).
- **Sem rede externa.** HTTP mockado nas bordas (`HttpTestingController`/MSW); o **service tipado** é a única borda que fala HTTP — mockar aí, nunca a lógica do componente.
- **Sem `now()`/`Math.random()` sem controle** — injetar relógio/seed.
- **Provar determinismo:** rodar a suíte **2×** (ou N× com seeds diferentes) → mesmo resultado. Flaky = quarentena com prazo ou conserto, nunca conviver.

### 4.4 Sentinela anti-suíte-vazia / anti-teatro (o gate tem de morder)

Um ratchet com threshold alto mas **0 testes** ou testes que só montam o componente sem asserir nada é falso-verde estrutural (`qa.md` "sentinela >0 mascara truncamento"; "testes verdes não provam nada se não exercem a invariante"). Mitigações **obrigatórias**:

1. **`coverage.all: true`** — arquivos de `src/app/**` não importados por nenhum teste entram como **0%**, derrubando o TOTAL. Sem isso, "100% de 1 arquivo testado" mascara 10 arquivos intocados.
2. **Sentinela de piso de massa:** falhar se o nº de specs executados, ou o total de statements medidos, ficar abaixo de um mínimo honesto (a suíte de T-S3-03 define o piso). Um `npm run test:cov` que reporta "0 tests" **reprova**, não passa.
3. **Threshold em `branches`, não só `lines`** — força asserir os dois lados de cada `@if`/`@switch`.
4. **Red-green do gate (prova que morde, §4.5).**

### 4.5 Prova de que o gate morde (red-green do ratchet)

Antes de declarar pronto (`007` §2 "prove que o gate morde"; reverter com **Edit** na linha exata, **nunca `git checkout`** — CLAUDE.md):

1. **Derrubar cobertura:** comentar (via Edit) um `expect`/`it` de um spec de T-S3-03 que cobre um branch → `npm run test:cov` **reprova** (abaixo do threshold). Reverter por Edit → verde.
2. **Suíte vazia:** apontar o runner para um glob sem specs (ou esvaziar temporariamente) → a sentinela anti-suíte-vazia **reprova** ("0 tests"/massa abaixo do piso), não passa vacuamente. Reverter.
3. **Branch descoberto:** remover o caso de teste do lado `else`/`@else` de um `@if` → o threshold de **branches** cai → **reprova**. Reverter.
4. **Anti-média-global:** confirmar que reprovar só o front (back verde) **bloqueia o merge** (gate AND), e não é diluído por um TOTAL combinado.

## 5. Impacto em testes e quality gates

- **Novo gate:** 2º ratchet de cobertura do front (lines/statements/branches/functions), piso = patamar medido em T-S3-03, **bloqueante**.
- **Gate AND:** job frontend independente do backend; merge exige ambos. **Proibida** média global combinada (ADR-0001 §4.1).
- **Branch coverage exigido** no front (análogo ao `--cov-branch` do back).
- **Determinismo:** ordem aleatória + tempo controlado + sem rede; flaky = P1.
- **Pin bloqueante:** runner, provider de cobertura e deps no `package-lock.json` (`npm ci`); ferramenta instalada ≠ pinada (`qa.md`).
- **Independente do gate de drift (T-S3-02):** cobertura ≠ contrato; um não mascara o outro (ADR-0005 §8).

## 6. Riscos

- **Piso num número redondo abaixo do real** = ratchet teatral desde o dia 1 (`qa.md`). Mitigação: piso = `floor(real)`, folga ≤ 1, por métrica, fixado **com T-S3-03 verde**.
- **Suíte vazia / teatro de cobertura** — threshold alto sobre 0 teste ou testes sem assert. Mitigação: `coverage.all: true` + sentinela de massa + branches + red-green (§4.4/§4.5).
- **Média global combinada back+front** (proibida) mascara lado fraco. Mitigação: jobs **separados**, gate AND, nunca somar.
- **Flaky (P1)** por `setTimeout`/rede/ordem. Mitigação: fakeAsync/fake timers, HTTP mockado na borda, ordem aleatória provada 2×.
- **Gate não-wired é inerte** (`qa.md`). Threshold no config sem rodar no CI = gate inexistente. Mitigação: job front **rodando** no `.github/workflows/ci.yml` (DoD).
- **Ferramenta instalada ≠ pinada** (`qa.md`). Provider de cobertura ausente do lockfile = gate que não roda no CI limpo. Mitigação: `npm ci` + lockfile commitado.
- **Cobrir o arquivo gerado** infla o número sem valor. Mitigação: `exclude` do `generated/**` logado e justificado (artefato derivado, ADR-0005).
- **Confundir lint/typecheck com cobertura** (`qa.md` "lint vs build"). `eslint`/`tsc --noEmit` são gates distintos; nenhum substitui o ratchet de cobertura. Mitigação: cobertura é gate próprio.
- **Reverter sonda com `git checkout`** apaga trabalho não-commitado adjacente (CLAUDE.md). Mitigação: red-green via **Edit** na linha exata.

## 7. Definition of Done (verificável)

- [ ] Piso de cobertura do front **fixado no patamar medido** (lines/statements/branches/functions = `floor(real)`, folga ≤ 1), commitado no config do runner.
- [ ] **Branch coverage** exigido (não só lines).
- [ ] `coverage.all: true` (ou equivalente) — arquivos não-importados contam como 0% (anti-teatro); `generated/**` excluído **com justificativa logada**.
- [ ] **Sentinela anti-suíte-vazia**: `0 tests` / massa abaixo do piso **reprova** (não passa vacuamente).
- [ ] Job **frontend wired no `.github/workflows/ci.yml`**, a partir da raiz (`working-directory: frontend`), **separado** do backend, visto **rodando**.
- [ ] **Gate AND** confirmado: merge na `main` exige job backend **e** job frontend verdes; **nenhuma** média global combinada back+front.
- [ ] **Determinismo provado**: suíte passa em **ordem aleatória** (shuffle/seed) e rodada 2× dá o mesmo resultado; sem `sleep`/rede externa.
- [ ] Runner + provider de cobertura **pinados** (lockfile + `npm ci`).
- [ ] **Red-green do ratchet provado** (§4.5): derrubar cobertura (via **Edit**) reprova; suíte vazia reprova pela sentinela; branch descoberto reprova; reverter restaura verde. **Nunca `git checkout`**.
- [ ] Nenhum piso **rebaixado** sem ADR; ratchet só sobe (P-07).
- [ ] Revisão aprovada (`tl-qa` + `tl-frontend`) sem ressalvas.
