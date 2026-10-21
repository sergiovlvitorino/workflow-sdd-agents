# DETAIL — T-S4-02 — SEC-01: bump Angular ≥19.2.17 (fecha CVE-2025-66412) + `npm audit` como gate de CI

**Sprint:** 4 (hardening)
**Tamanho:** S _(estimativa — patch bump + 1 step de CI; risco baixo, prova é o que dá trabalho)_
**Papel:** FE (+ TL revisão `tl-frontend` + `tl-qa`; `sre` consultivo — gate de supply-chain no CI, dialoga com SEC-07)
**Depende de:** T-S3-01 (scaffold Angular + `package-lock.json` + guard de lockfile determinístico no `ci.yml`), T-S3-02 (gate de drift de contrato — não pode regredir com o bump)
**Bloqueia:** — (compõe defesa-em-profundidade com SEC-08/CSP; nenhuma tarefa depende desta para começar)

> Produzido por um `tl-*` no `sprint-flow` (detalhamento técnico); consumido pelo `review-loop` (implementação + revisão). Descreve a tarefa no **presente** — o status real vive no índice/board, não aqui (ver `docs/lessons/process.md`).

---

## 1. Objetivo

Fechar **SEC-01** (`docs/quality/hardening-baseline-2026-07.md`, Alto): atualizar toda a linha `@angular/*` + Angular CLI de `19.2.14` para o patch **≥ 19.2.17**, eliminando a exposição ao **CVE-2025-66412** (stored XSS via bypass de sanitização em atributos SVG/MathML — `xlink:href`, `[attributeName]` de `<animate>` — no `@angular/compiler`, dependência de **produção**; CVSS 8.5); e wire de um gate **`npm audit`** no job frontend do CI para que qualquer vuln High na superfície de produção **falhe o build** (P-11, falha explícita) em vez de virar dívida silenciosa. Colateralmente cobre CVE-2025-66035 (fix em 19.2.16, inócuo aqui — sem XSRF token/cookie), que o mesmo bump arrasta.

## 2. CAs / RNs cobertos

Tarefa de hardening: os "CAs" são o achado da baseline + pisos que ela protege.

- **SEC-01 (fonte: `hardening-baseline-2026-07.md:29,51`):** `@angular/*` sai de `19.2.14` (vulnerável) para `≥19.2.17`; `npm audit --audit-level=high` deixa de acusar `GHSA-v4hv-rgfq-gp49` / CVE-2025-66412.
- **P-11 (falha explícita, não aviso):** o gate `npm audit` é **bloqueante** — vuln High na superfície de produção = build vermelho, nunca warning.
- **Piso CLAUDE.md — deps pinadas exatas:** as versões novas entram **pinadas exatas** (sem `^`/`~`), coerentes com o resto do `package.json`.
- **Piso CLAUDE.md — guard de lockfile determinístico:** o `package-lock.json` regenerado mantém o guard verde (toda entrada de `packages` com `version`; regenerado com npm 10).
- **P-07 (ratchet não regride):** cobertura do frontend (`vitest.config.ts`) permanece ≥ pisos atuais; o bump não pode baixar nenhum threshold.

## 3. Arquivos a criar/alterar

| Path | Ação | Descrição |
|---|---|---|
| `frontend/package.json` | alterar | Bump **coordenado** de todo `@angular/*` (deps + devDeps), `@angular/cli`, `@angular-devkit/build-angular`, `@angular/compiler-cli` para `≥19.2.17`, **pin exato**. Ver §4.1. |
| `frontend/package-lock.json` | alterar (regenerar) | Regenerado por `npm install` com **npm 10** após o bump; guard de lockfile deve continuar verde. Único arquivo grande do diff. |
| `.github/workflows/ci.yml` | alterar | Novo step **`npm audit`** no job `frontend`, após `npm ci`, **antes** do gate de drift (fail-fast). Bloqueante. Ver §4.3. |
| `docs/quality/hardening-baseline-2026-07.md` | alterar | Marcar SEC-01 como **fechado** (dívida → resolvida) na seção "Dívidas registradas" e adicionar linha no **Histórico** com data + prova. A baseline é a fonte da verdade do débito; fechar sem atualizá-la deixa o registro incoerente. |
| _(possível)_ `frontend/angular.json`, `frontend/tsconfig*.json` | alterar (só se `ng update` gerar migração) | Patch dentro do mesmo minor (19.2.x) normalmente **não** dispara schematics; se `ng update` tocar algum desses, commitar **por caminho** (higiene CLAUDE.md) e justificar na revisão. Se não tocar, não aparecem no diff. |

> **Não** entram nesta tarefa: `rxjs` (7.8.2), `zone.js` (0.15.0), `tslib` (2.8.1) — ver §4.4 (compatíveis, sem CVE, permanecem pinados como estão). SEC-08/CSP é tarefa separada.

## 4. Design da solução

### 4.1 Mecanismo do bump — `ng update` + re-pin exato (decisão + justificativa)

**Decisão:** usar `ng update` como motor do bump e **normalizar para pin exato** em seguida — **não** editar `package.json` à mão.

```bash
# frontend/ — árvore git LIMPA (ng update exige) e branch da tarefa criada
npx ng update @angular/core@19.2 @angular/cli@19.2
#   → resolve o ÚLTIMO patch da linha 19.2.x (garantidamente ≥19.2.17),
#     atualiza package.json + package-lock.json de forma COORDENADA e
#     roda eventuais migration schematics do próprio Angular.

# Re-pin exato: remover qualquer ^/~ que o ng update tenha introduzido nas
# linhas @angular/* / @angular-devkit/* / @angular/cli, deixando "19.2.NN"
# EXATO — coerente com o piso "deps pinadas exatas" (CLAUDE.md).
#   (edição cirúrgica das linhas versionadas em package.json)

npm install            # reconcilia o lock com os pins exatos (npm 10)
```

**Justificativa (trade-off) — por que `ng update` e não edição manual + `npm install`:**
- O bump é **coordenado**: `@angular/{animations,common,compiler,core,forms,platform-browser,platform-browser-dynamic,router}` (deps) **+** `@angular-devkit/build-angular`, `@angular/cli`, `@angular/compiler-cli` (devDeps) precisam subir **juntos** para a mesma versão. Edição manual é propensa a esquecer o `@angular-devkit/build-angular` (não tem o prefixo `@angular/`) e a produzir um conjunto incompatível.
- `ng update` conhece a **matriz de compatibilidade** e roda migrações se houver — edição manual não. Custo do `ng update` é trivial aqui.
- **Contraponto do projeto:** `ng update` tende a gravar versões com `^` (ex.: `^19.2.17`), o que **viola** o pin exato do projeto. Por isso o passo de **re-pin exato é obrigatório** e explícito no DoD. Não delegar o pin ao CLI.

**Versão-alvo:** o `@19.2` resolve o último patch de 19.2.x. O contrato é **≥19.2.17** (piso do CVE); se o registry servir 19.2.18+, pina-se essa — registrar no PR a versão resolvida. Não hardcodar "19.2.17" se houver patch maior disponível.

### 4.2 Impacto no guard de lockfile determinístico

O `ci.yml` (job frontend) roda um guard antes do `npm ci` que reprova o lock se **qualquer** entrada de `packages` não tiver `version` (entradas-fantasma de deps opcionais que o npm 9 gerava; ver `ci.yml:74-75` e commits `bd31fe3`/`bd8cc93`). O bump precisa:

- Regenerar o lock com **npm 10** (`node >=20`, `npm >=10` — já é o `engines` do projeto e o setup do CI). O `npm install` do §4.1 deve rodar sob npm 10 local para não reintroduzir entradas sem `version`.
- **Verificar localmente** o mesmo one-liner do guard antes de commitar:

```bash
# frontend/ — reproduz o guard do CI localmente (deve imprimir "lockfile OK")
node -e "const l=require('./package-lock.json');const bad=Object.entries(l.packages).filter(([k,v])=>k&&!v.link&&!('version' in v));if(bad.length){console.error('FALHA: entradas sem version');bad.forEach(([k])=>console.error(' -',k));process.exit(1)}console.log('lockfile OK:',Object.keys(l.packages).length,'entradas')"
```

- `lockfileVersion` permanece `3`. `npm ci` deve completar sem erro (o CI já roda `npm ci`, não `npm install` — divergência package.json × lock aborta o CI).

### 4.3 Gate `npm audit` no CI — posição, escopo e bloqueio (decisões)

**Novo step no job `frontend` de `.github/workflows/ci.yml`, logo após `npm ci`:**

```yaml
      - name: npm ci (deps pinadas)
        run: npm ci

      # Gate de supply-chain (SEC-01): vuln HIGH+ na superfície de PRODUÇÃO = build vermelho.
      # Escopo --omit=dev: protege o bundle que chega ao browser (onde vive o XSS do
      # threat model). CVE-2025-66412 está em @angular/compiler (dependency de prod) → morde aqui.
      - name: Gate de vulnerabilidades (npm audit — prod, bloqueante)
        run: npm audit --omit=dev --audit-level=high
```

**Decisão 1 — posição: após `npm ci`, antes do gate de drift.** Fail-fast: é o sinal mais barato do pipeline (sem build/tsc). Precisa do lock resolvido (o `npm ci` já garante isso) e de rede ao registry (o job já tem).

**Decisão 2 — bloqueante (sem `continue-on-error`).** P-11: vuln High é falha explícita, não aviso. `--audit-level=high` faz o `npm audit` sair não-zero **apenas** para High/Critical, ignorando Low/Moderate (evita ruído que forçaria burlar o gate).

**Decisão 3 — escopo `--omit=dev` (produção).** Justificativa/trade-off:
- O threat model (baseline §"Modelo de ameaça") protege **integridade do conteúdo exibido** — XSS no bundle servido. Isso é a superfície de **produção** (`dependencies`). CVE-2025-66412 está em `@angular/compiler`, uma `dependency` → o gate `--omit=dev` **morde** o achado-alvo. Objetivo atingido sem depender de deps de build.
- **Determinismo (flaky = P1):** `npm audit` consulta a advisory DB viva; um audit **full** (incluindo devDeps: vite, esbuild, etc.) fica sujeito a High novas em tooling de build — que **não** chegam ao browser — virando CI vermelho em PRs não-relacionados. Escopar a prod reduz esse acoplamento ao mínimo necessário para o achado.
- **Alternativa registrada (rejeitada como gate bloqueante):** `npm audit --audit-level=high` full (com dev). Rejeitada como *bloqueante* por acoplar o merge a advisories de tooling de build. Pode entrar como step **informativo** (`continue-on-error: true`) numa iteração futura — fora do escopo desta tarefa. A baseline ("Como reverificar") mantém o full audit como reverificação **manual**; não conflita com o gate escopado.

**Nota sobre "vermelho legítimo × flake":** se, no futuro, o gate ficar vermelho por advisory nova **sem fix disponível** numa dep de prod, isso é sinal **real** (não flake) — trata-se via `hardening-flow` com exceção **documentada** (ex.: `--exclude`/allowlist versionada + registro na baseline), nunca `continue-on-error` silencioso. Falha de rede/registry-outage também sai não-zero: raro; retry do job. Documentado em §6.

### 4.4 Compatibilidade de rxjs / zone.js / tslib (não sobem)

`19.2.14 → 19.2.17` é **patch dentro do mesmo minor** — os `peerDependencies` do Angular não mudam entre patches:

- **`rxjs` 7.8.2** — dentro do peer `^6.5.3 || ^7.4.0` do Angular 19.2.x; atual; sem CVE aberto. Permanece pinado `7.8.2`.
- **`zone.js` 0.15.0** — dentro do peer `~0.15.0` do Angular 19.2.x; atual; sem CVE. Permanece `0.15.0`.
- **`tslib` 2.8.1** — compatível; permanece.

A **prova** de que seguem compatíveis é operacional (§5): `npm ci` sem `EBADPEER`, `tsc` verde, `test:cov` verde, `ng build` verde. Se `ng update` propuser tocar `rxjs`/`zone.js`, **recusar** (fora do escopo; sem CVE que justifique) — a menos que seja peer **obrigatório** do patch, o que não é o caso.

## 5. Impacto em testes e quality gates

Esta tarefa **não adiciona testes de aplicação** (é bump + gate de infra). A "prova" é red-green **do gate** + suíte existente verde (zero regressão). Nada de teste novo em `src/`.

### 5.1 Prova red-green do gate (SEC-01 morde)

**VERMELHO (antes do bump, na árvore atual `19.2.14`):**

```bash
cd frontend
npm audit --omit=dev --audit-level=high        # sai NÃO-ZERO
#   → reporta GHSA-v4hv-rgfq-gp49 / CVE-2025-66412 em @angular/compiler
#     "Severity: high", "fix available via `npm audit fix`"
```
- **Prova de que o gate morde no CI:** um commit intermediário que adiciona **só** o step `npm audit` (§4.3) com o lock ainda em `19.2.14` deixa o job `frontend` **vermelho** exatamente nesse step. (Não precisa ir ao remoto: reproduzível local pelo comando acima; se desejar evidência de CI, o primeiro push da branch com o step antes do bump exibe o job vermelho.)

**VERDE (após bump ≥19.2.17):**

```bash
cd frontend
npm audit --omit=dev --audit-level=high        # sai ZERO — nenhuma High em prod
```

### 5.2 Zero regressão — suíte + build (Angular 19.2.x é patch, risco baixo; confirmar)

Rodar, **todos verdes**, após o bump (ordem espelha o job frontend do CI):

```bash
cd frontend
# guard de lockfile (§4.2)
node -e "const l=require('./package-lock.json');const bad=Object.entries(l.packages).filter(([k,v])=>k&&!v.link&&!('version' in v));if(bad.length){process.exit(1)}console.log('lockfile OK')"
npm ci                                          # sem EBADPEER / sem divergência lock
npm run gen:api && node scripts/check-generated-header.mjs \
  && git diff --exit-code -- src/app/api/generated/openapi-types.ts src/app/api/generated/openapi.json   # drift segue verde (T-S3-02)
npx tsc --noEmit -p tsconfig.app.json           # typecheck app
npx tsc --noEmit -p tsconfig.spec.json          # typecheck specs
npm run lint                                     # eslint 9.28.0 pinado
npm run test:cov                                 # 2o ratchet front — thresholds do vitest.config.ts mantidos
npm run build                                    # ng build — confirma que o compiler novo compila o app
```

### 5.3 Gates afetados

- **2o ratchet de cobertura (frontend, `vitest.config.ts`):** deve permanecer ≥ pisos atuais (branches 90 / functions 96 / lines 97 / statements 97; por-arquivo `post-store.ts`). Bump de patch não muda código de app → cobertura idêntica. **Não** baixar nenhum threshold (P-07).
- **Gate de drift de contrato (T-S3-02):** os tipos gerados vêm do OpenAPI do backend (via `openapi-typescript` 7.8.0, que **não** sobe) — bump do Angular não deve alterar `openapi-types.ts`. `git diff --exit-code` deve seguir vazio.
- **Guard de lockfile (novo lock):** verde sob npm 10 (§4.2).
- **Gate `npm audit` (novo):** verde pós-bump; era vermelho pré-bump (§5.1).
- **Backend:** intocado. Gate AND por job (ADR-0001 §4.1) — nada muda no job backend.

## 6. Riscos

- **`ng update` grava `^`/`~` e fura o pin exato** → mitigar com o re-pin obrigatório (§4.1) e conferência no DoD; a revisão bate o `package.json` linha a linha procurando `^`/`~` em `@angular/*`.
- **Lock regenerado com npm errado reintroduz entradas-fantasma** → rodar `npm install`/`npm ci` sob **npm 10** e validar o guard localmente **antes** do commit (§4.2). O CI reprova, mas queremos pegar antes.
- **`npm audit` acopla CI à advisory DB viva (flaky = P1)** → escopo `--omit=dev` minimiza a superfície; vermelho por vuln nova **com fix** = ação real (subir dep); **sem fix** = exceção documentada via `hardening-flow`, nunca silenciar (§4.3). Registry-outage → retry.
- **Migração inesperada do `ng update`** tocando `angular.json`/`tsconfig` → improvável em patch same-minor; se ocorrer, revisar o diff, commitar **por caminho** (nunca `git add -A` — CLAUDE.md) e explicar na revisão.
- **Higiene de commit:** a árvore pode ter trabalho não-relacionado (`docs/` em `git status`). `git add` **explícito** de `frontend/package.json frontend/package-lock.json .github/workflows/ci.yml docs/quality/hardening-baseline-2026-07.md` (+ eventuais arquivos de migração). Antes do PR: `git diff main HEAD --stat` para confirmar que o deliverable inteiro foi commitado.
- **Falso senso de segurança:** o bump fecha o CVE, mas o sink (SVG/MathML) **não** é atingido hoje (só interpolação de texto no app). SEC-08/CSP é a segunda linha e continua dívida aberta — não marcar "XSS resolvido de forma geral", só "SEC-01 fechado".
- **`npm audit fix` acidental:** **não** rodar `npm audit fix` (reescreve o lock além do escopo, pode subir deps não-pinadas). O fix é o bump coordenado do §4.1, ponto.

## 7. Definition of Done (verificável)

- [ ] **Todo `@angular/*` (deps + devDeps) + `@angular/cli` + `@angular-devkit/build-angular` + `@angular/compiler-cli`** em `frontend/package.json` na mesma versão **≥19.2.17**, **pin exato** (sem `^`/`~`); versão resolvida registrada no PR.
- [ ] `rxjs` 7.8.2, `zone.js` 0.15.0, `tslib` 2.8.1 **inalterados**.
- [ ] `frontend/package-lock.json` regenerado sob **npm 10**; guard de lockfile local verde (`node -e "..."` → "lockfile OK"); `lockfileVersion: 3`.
- [ ] **Prova RED:** `cd frontend && npm audit --omit=dev --audit-level=high` na árvore `19.2.14` sai **não-zero** reportando CVE-2025-66412 / `GHSA-v4hv-rgfq-gp49`.
- [ ] **Prova GREEN:** o mesmo comando pós-bump sai **zero**.
- [ ] Novo step **`npm audit --omit=dev --audit-level=high`** em `.github/workflows/ci.yml` (job `frontend`, após `npm ci`, antes do gate de drift), **bloqueante** (sem `continue-on-error`).
- [ ] **Zero regressão** (§5.2, todos verdes): `npm ci`, `gen:api` + drift `git diff --exit-code` vazio, `tsc --noEmit` (app **e** spec), `npm run lint`, `npm run test:cov` (thresholds do `vitest.config.ts` **mantidos**, nenhum baixado — P-07), `npm run build`.
- [ ] `docs/quality/hardening-baseline-2026-07.md`: SEC-01 marcado **fechado** + linha no Histórico com data (2026-07-15) e prova.
- [ ] Commit por caminho (só os arquivos do deliverable); `git diff main HEAD --stat` confere o deliverable completo.
- [ ] Revisão aprovada (`tl-frontend` + `tl-qa`; `sre` de olho no gate de CI) sem ressalvas.
