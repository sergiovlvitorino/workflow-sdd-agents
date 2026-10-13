# DETAIL — T-S4-04 — SEC-07: least-privilege + supply-chain no CI

**Sprint:** 4 (hardening)
**Tamanho:** M _(estimativa)_
**Papel:** SRE (+ TL revisão `tl-python`/`tl-frontend`/`tl-qa`)
**Depende de:** **T-S4-01** (mesmo `ci.yml` — consolidar pin/permissions do job `secret-scan` na mesma passada)
**Bloqueia:** — (fecha SEC-07, Médio)

> Produzido por SRE no `sprint-flow` (detalhamento técnico); consumido pelo `review-loop`. Descreve a tarefa no **presente** — o status real vive no índice/board (ver `docs/lessons/process.md`).

---

## 1. Objetivo

Fechar os **gaps de supply-chain e privilégio do CI** (achado **SEC-07**, Médio): (a) `GITHUB_TOKEN` sem `permissions` (herda escopo de escrita — blast radius desnecessário); (b) Actions de terceiros por **tag mutável** (`@v4`/`@v5` podem ser re-taggeadas → execução de código não-auditado no runner); (c) **backend sem lockfile/hash-pinning** (transitivas resolvidas livremente a cada CI — assimetria com o frontend, que já tem `package-lock.json` + `npm ci` + guard); (d) ausência de **audit de vulnerabilidades** de dependências no CI (`pip-audit` / `npm audit`).

## 2. CAs / RNs cobertos

- **SEC-07 (baseline hardening, Médio):** `permissions: contents: read`; pinar Actions por SHA; `requirements.lock --generate-hashes` + `--require-hashes`; `pip-audit`/`npm audit`. Prova: "CI verde com deps por hash; audit falha em CVE High".
- **CLAUDE.md — lint/scan pinado, higiene de commit:** ferramentas de CI pinadas exatas; nada de `latest`/tag mutável.
- **Playbook Segurança — supply-chain:** imutabilidade da origem (SHA), audit como gate, supressão cirúrgica justificada (análogo `# nosec`).
- **Playbook SRE — "gate que roda de verdade":** cada step novo comprovado rodando (`gh run list`), não só presente no YAML.

## 3. Arquivos a criar/alterar

| Path | Ação | Descrição |
|---|---|---|
| `.github/workflows/ci.yml` | alterar | (a) `permissions: contents: read` no topo; (b) **todas** as Actions pinadas por SHA + comentário da tag; (c) steps de `pip-audit` (job backend) e `npm audit` (job frontend); (d) trocar `pip install -e ".[dev]"` por instalação **hash-pinned** no job backend. |
| `backend/requirements.lock` | criar | Lockfile com hashes (`pip-compile --generate-hashes` a partir do `pyproject.toml`, runtime + extra `dev`). **Multi-versão Python** (3.10 e 3.12 — a matrix roda os dois). |
| `backend/pyproject.toml` | alterar _(condicional)_ | Se optar por `uv` como resolvedor, registrar; senão, `pyproject` intacto (o lock deriva dele). Nenhuma dep top-level muda. |
| `.github/dependabot.yml` | criar | Atualização automática de `github-actions`, `pip` (backend) e `npm` (frontend) — mantém os SHAs/locks vivos sem re-pin manual (nota do enunciado SEC-07). |

## 4. Design da solução

### 4.1 (a) `permissions` least-privilege — deny-by-default no topo

```yaml
# ci.yml — logo abaixo de `on:`, antes de `jobs:`
permissions:
  contents: read        # piso global: só leitura do repo p/ TODOS os jobs
```

- Sem bloco `permissions`, o `GITHUB_TOKEN` **herda o default do repo/org**, tipicamente `read/write` amplo. Declarar `contents: read` no **topo** rebaixa todos os jobs; **elevar por-job** só onde um passo escreve (hoje **nenhum** job escreve: backend/frontend só testam, secret-scan só lê com comentários desligados — ver T-S4-01). Resultado esperado: **nenhum** job precisa elevar.
- Se um passo futuro precisar escrever (ex.: publicar cobertura, comentar PR), adicionar `permissions:` **no job específico** com o escopo mínimo (`pull-requests: write` etc.) — nunca reabrir no topo.

### 4.2 (b) Pin de Actions por SHA de 40 hex + comentário da tag

Toda Action de terceiro passa de tag mutável para **SHA imutável**, com a tag legível no comentário (Dependabot atualiza o par SHA+comentário):

```yaml
- uses: actions/checkout@<sha-40-hex>       # v4.x
- uses: actions/setup-python@<sha-40-hex>   # v5.x
- uses: actions/setup-node@<sha-40-hex>     # v4.x
- uses: gitleaks/gitleaks-action@<sha-40-hex>  # v2.x  (job de T-S4-01)
```

Inventário atual a pinar (do `ci.yml` vigente): `actions/checkout@v4` (2 ocorrências — jobs backend e frontend), `actions/setup-python@v5` (2 ocorrências), `actions/setup-node@v4` (1), mais `gitleaks/gitleaks-action` (novo, T-S4-01). **NÃO inventar o SHA** — resolver cada um a partir da tag e verificar:

```bash
# resolver o SHA da tag (exemplo; rodar por Action no review-loop)
git ls-remote https://github.com/actions/checkout refs/tags/v4.2.2
# ou: gh api repos/actions/checkout/git/refs/tags/v4.2.2 --jq .object.sha
```

- **Racional:** tag é ponteiro mutável; um mantenedor comprometido (ou re-tag malicioso) injeta código no runner com o `GITHUB_TOKEN` em mãos. SHA congela a árvore exata auditada. É o análogo em CI do "deps top-level pinadas exatas" que o baseline já elogia no backend/frontend.
- **Actions oficiais `actions/*`** também são pinadas — supply-chain não abre exceção por "ser da GitHub" (defesa em profundidade).

### 4.3 (c) Backend hash-pinned — fechar a assimetria com o frontend

Hoje: frontend tem `package-lock.json` + `npm ci` + guard de lockfile; backend faz `pip install -e ".[dev]"` (transitivas livres a cada run → build não-reprodutível e superfície de typosquatting/hijack). Fechar com **lockfile de hashes**:

**Gerar o lock** (resolvedor: `pip-tools` ou `uv` — decidir no review-loop; `uv` é mais rápido, `pip-compile` é o mais difundido):

```bash
# opção pip-tools
cd backend
pip install pip-tools
pip-compile --generate-hashes --extra dev -o requirements.lock pyproject.toml
# opção uv (equivalente)
uv pip compile --generate-hashes --extra dev pyproject.toml -o requirements.lock
```

**Instalar no CI com verificação de hash** (job backend, substitui o `pip install -e ".[dev]"`):

```yaml
- name: Instalar deps (hash-pinned)
  run: |
    pip install --require-hashes -r requirements.lock
    pip install -e . --no-deps        # pacote local editável, sem re-resolver deps
```

- **Gotcha decisivo:** `--require-hashes` é **incompatível com install editável** (`-e`). Padrão correto: instalar **todas as deps** (runtime + dev) a partir do `requirements.lock` com `--require-hashes`, e **depois** o pacote local com `pip install -e . --no-deps` (sem tocar as deps já travadas). Isso mantém o `pytest`/`--cov` do editável funcionando **e** trava as dependências por hash.
- **Matrix 3.10 e 3.12:** o `ci.yml` roda as duas versões. Um lock gerado só em 3.12 pode faltar wheels/markers de 3.10 (ou vice-versa). Duas saídas: (i) um `requirements.lock` único que resolva para ambas (marcadores de ambiente cobrindo 3.10–3.12) — validar rodando `--require-hashes` nas duas na matrix; (ii) locks por versão (`requirements-3.10.lock`/`requirements-3.12.lock`) se a resolução única falhar. **Recomendação:** tentar (i); cair para (ii) só se a matrix acusar hash/marker faltante. Análogo ao aprendizado do playbook SRE sobre `.terraform.lock.hcl` multi-plataforma — o lock tem de cobrir **todos** os alvos que o CI realmente executa.
- **Guard de lockfile (paridade com o frontend):** considerar um step que falhe se o `requirements.lock` estiver **dessincronizado** do `pyproject.toml` (re-compilar e `git diff --exit-code`), espelhando o guard de `package-lock.json` do frontend. Barato e fecha a assimetria por completo. Decidir no review-loop (pode ser step próprio ou parte do audit).

### 4.4 (d) `pip-audit` e `npm audit` como steps — bloqueante vs warning

Steps de audit de vulnerabilidades conhecidas nas deps:

```yaml
# job backend
- name: Audit de deps (pip-audit)
  run: pip install pip-audit && pip-audit --require-hashes -r requirements.lock
# job frontend
- name: Audit de deps (npm audit)
  run: npm audit --audit-level=high
```

**Decisão de severidade do gate (concreta, ancorada no baseline):**

- **`pip-audit` (backend): BLOQUEANTE.** O backend tem poucas deps e nenhum CVE conhecido registrado no baseline. **Não inventar CVE** — se o `pip-audit` acusar um High no review-loop, ele está fazendo o trabalho: corrigir (bump) ou, se um High for **inevitável no momento** (upstream sem fix), suprimir **cirurgicamente** com `--ignore-vuln <GHSA/CVE>` **e justificativa na linha** (analogia direta ao `# nosec` cirúrgico do `docs/lessons/security.md`), nunca desligar o gate.
- **`npm audit --audit-level=high` (frontend): WARNING agora, BLOQUEANTE após SEC-01.** O baseline registra **SEC-01** — Angular 19.2.14 exposto ao **CVE-2025-66412** (stored XSS, High), corrigido em 19.2.17, tratado em **tarefa separada** (SEC-01, não é dependência de T-S4-04). Tornar `npm audit` bloqueante **agora** deixaria o CI **impossível de ficar verde** até o bump do Angular — acoplando indevidamente esta tarefa à SEC-01. Portanto:
  - **agora:** rodar como **warning** (`continue-on-error: true` **ou** `npm audit --audit-level=high || true` com eco visível) — dá visibilidade sem travar;
  - **gatilho de flip para bloqueante:** quando **SEC-01** (bump Angular ≥19.2.17) mergear, remover o `continue-on-error`. Registrar esse flip como item de follow-up no PR de SEC-01 (o `npm audit` gate é, aliás, a **prova** de fechamento de SEC-01 — "gate falha com Angular <19.2.17; verde após bump").

> **Decisão registrada (trade-off):** assimetria proposital `pip-audit` bloqueante × `npm audit` warning-por-ora não é inconsistência — reflete o **estado real** de cada ecossistema (backend limpo hoje; frontend com um High conhecido em tarefa separada). Fixar ambos bloqueantes de imediato quebraria o CI por uma dívida já triada e planejada noutra tarefa.

### 4.5 Dependabot — manter SHAs e locks vivos

```yaml
# .github/dependabot.yml (esqueleto)
version: 2
updates:
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule: { interval: "weekly" }
  - package-ecosystem: "pip"
    directory: "/backend"
    schedule: { interval: "weekly" }
  - package-ecosystem: "npm"
    directory: "/frontend"
    schedule: { interval: "weekly" }
```

- Pin por SHA **sem** Dependabot vira dívida de segurança oposta (deps congeladas envelhecem e acumulam CVE). O Dependabot atualiza o SHA **e** o comentário de tag juntos, e refaz o `requirements.lock`/`package-lock.json` — mantendo o pin **atualizado**, não fóssil. Nota do enunciado SEC-07 endereçada.

## 5. Impacto em testes e quality gates

- **Sem teste de suíte novo** — as invariantes são **gates de CI** (permissions/pin/lock/audit), provados red-green no próprio pipeline (playbook SRE: gate/alarme, não teste unitário).
- **Reprodutibilidade:** o job backend passa a ser determinístico (deps por hash) — fecha a assimetria com o frontend e reduz flaky por resolução de transitiva (flaky = P1).
- **Gates existentes intactos:** cobertura backend (`pytest` + `coverage-gates.sh`) e frontend (`test:cov`) inalterados; a mudança é **como** as deps chegam, não o que roda. Confirmar que a suíte segue verde com o lock (mesma resolução do editável atual — se um hash "puxar" uma transitiva diferente da que roda hoje, investigar antes de mergear).
- **Novo gate `pip-audit`** (bloqueante) entra no AND de merge do job backend.
- **`npm audit`** entra como sinal não-bloqueante (flip pós-SEC-01).

## 6. Riscos

- **`--require-hashes` × editável** → resolvido pelo padrão `--require-hashes -r requirements.lock` **+** `pip install -e . --no-deps` (§4.3). Se alguém "simplificar" para `-e ".[dev]"` de novo, perde-se o hash-pinning — DoD amarra isso.
- **Lock incompleto na matrix 3.10/3.12** → validar `--require-hashes` nas **duas** versões; cair para locks-por-versão se faltar hash/marker (§4.3). Não declarar "ok" sem ver os dois verdes (playbook SRE — "reexecute e veja o resultado real").
- **`npm audit` bloqueante travando o CI por SEC-01** → mitigado por warning-até-flip (§4.4); o gatilho de flip fica documentado no PR de SEC-01.
- **`pip-audit` reprovando por um High inevitável** → supressão **cirúrgica** justificada (`--ignore-vuln`), nunca desligar o gate (security.md).
- **SHA errado/typo no pin** → verificar `git ls-remote`/`gh api` que o SHA resolve para a tag comentada (DoD). Um SHA que não bate a tag é pior que a tag (aponta para árvore não-auditada).
- **Contaminação com T-S4-01** (mesmo `ci.yml`) → **serializar**: T-S4-01 primeiro, T-S4-04 consolidando o pin/permissions do job `secret-scan` na mesma árvore (CLAUDE.md — não paralelizar escrita no mesmo arquivo).
- **Dependabot barulhento** → cadência `weekly` e agrupável; ruído de PR é aceitável ante o risco de pin fóssil.

## 7. Definition of Done (verificável)

- [ ] `permissions: contents: read` no **topo** do `ci.yml`; nenhum job eleva sem passo que escreva (auditar job a job). Verificar: `grep -n "permissions:" .github/workflows/ci.yml`.
- [ ] **Todas** as Actions pinadas por **SHA de 40 hex** + comentário da tag (`checkout`, `setup-python`, `setup-node`, `gitleaks-action`). Verificar ausência de tag mutável: `grep -nE "uses: .*@v[0-9]+($|[^0-9a-f])" .github/workflows/ci.yml` **não** retorna linhas; cada SHA confere com `git ls-remote <repo> refs/tags/<tag>`.
- [ ] `backend/requirements.lock` gerado com `--generate-hashes` (runtime + `dev`), cobrindo **3.10 e 3.12** (ou locks-por-versão se a resolução única falhar).
- [ ] Job backend instala com `pip install --require-hashes -r requirements.lock` **+** `pip install -e . --no-deps` (não mais `-e ".[dev]"`); suíte + `coverage-gates.sh` **verdes** nas duas versões da matrix.
- [ ] _(Recomendado)_ Guard de sincronia `requirements.lock` × `pyproject.toml` (re-compile + `git diff --exit-code`), espelhando o guard do frontend.
- [ ] Step **`pip-audit`** no job backend, **bloqueante**, rodando sobre o lock; supressões (se houver) cirúrgicas e justificadas na linha.
- [ ] Step **`npm audit --audit-level=high`** no job frontend, **warning** agora (`continue-on-error`), com follow-up documentado para flip a bloqueante quando **SEC-01** (Angular ≥19.2.17) mergear.
- [ ] `.github/dependabot.yml` cobrindo `github-actions`, `pip` (/backend) e `npm` (/frontend).
- [ ] Steps novos comprovados rodando na aba Actions/`gh run list` (não só presentes no YAML — playbook SRE).
- [ ] Sem regressão nos gates de cobertura (backend/frontend) nem no drift de contrato do frontend.
- [ ] Consolidado com **T-S4-01** (job `secret-scan` também pinado por SHA + `permissions`); um único `ci.yml` coerente.
- [ ] Revisão aprovada (`tl-python`/`tl-frontend`/`tl-qa`) sem ressalvas.
