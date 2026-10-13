# DETAIL — T-S4-01 — SEC-02: secret-scan (gitleaks) bloqueante no CI

**Sprint:** 4 (hardening)
**Tamanho:** S _(estimativa)_
**Papel:** SRE (+ TL revisão `tl-python`/`tl-qa`)
**Depende de:** — (mas **precede/consolida** com T-S4-04, que toca o mesmo `ci.yml`; ver §6 ordem)
**Bloqueia:** — (fecha o piso "secret-scan bloqueante" do CLAUDE.md)

> Produzido por SRE no `sprint-flow` (detalhamento técnico); consumido pelo `review-loop` (implementação + revisão). Descreve a tarefa no **presente** — o status real vive no índice/board, não aqui (ver `docs/lessons/process.md`).

---

## 1. Objetivo

Tornar o secret-scan um **gate de CI real e bloqueante** (roda em push/PR, varre o histórico, falha o build ao encontrar segredo) — hoje o gitleaks só existe no `.pre-commit-config.yaml` (opt-in por clone, contornável com `git commit --no-verify`), o que **viola o piso não-negociável "Secret-scan bloqueante" do CLAUDE.md** e o achado **SEC-02** (Alto) do baseline de hardening.

## 2. CAs / RNs cobertos

- **SEC-02 (baseline hardening, Alto):** "gitleaks só em pre-commit, ausente no CI" → job `gitleaks` no CI, pinado por SHA, rev **v8.18.4** (mesma do pre-commit), `fetch-depth: 0`. Prova: PR com segredo-canário faz o job falhar; verde ao remover.
- **CLAUDE.md — Quality gates:** "Secret-scan e lint **pinado** são bloqueantes." O gate passa a ser efetivo mesmo quando o dev pula o pre-commit.
- **P-10 (segredos):** detecção de segredo é falha explícita (build vermelho), nunca aviso.
- **Playbook SRE — "gate que roda de verdade":** o workflow vive em `<raiz>/.github/workflows/`, comprovado rodando por `gh run list` (não só "arquivo existe").

## 3. Arquivos a criar/alterar

| Path | Ação | Descrição |
|---|---|---|
| `.github/workflows/ci.yml` | alterar | Novo job `secret-scan` (checkout `fetch-depth: 0` + gitleaks pinado por SHA, rev v8.18.4, bloqueante). **Consolidar na mesma passada de T-S4-04** (pin por SHA + `permissions`). |
| `.gitleaks.toml` | criar _(condicional)_ | **Só se** for preciso allowlist de fixtures/paths (ex.: senha canônica de teste). Se o default do gitleaks já roda limpo no repo, **não criar** (evitar config órfã). Decisão no review-loop após rodar `gitleaks detect` no HEAD. |
| `.github/workflows/tests/` ou branch efêmera | criar _(prova red-green, descartável)_ | Fixture com **segredo-canário sintético** (não-real) para provar o vermelho; **removida antes do merge** (ver §4.4 — nunca entra na main). |

> **Não** commitar `.env`, `.pem`, `.key`, `.db` — já cobertos pelo `.gitignore` (baseline confirma). Este job é a rede que pega o que escapar do `.gitignore` + pre-commit.

## 4. Design da solução

### 4.1 Job dedicado, gate AND com backend/frontend

Novo job `secret-scan` no `ci.yml`, paralelo aos jobs `backend`/`frontend` (todos precisam passar para merge — regra de gate AND já vigente no `ci.yml`). Roda em `push` (branches `**`) e `pull_request` (base `main`), como os demais.

```yaml
# ci.yml — novo job (esqueleto; SHAs resolvidos no review-loop — NÃO inventar)
  secret-scan:
    name: Secret scan (gitleaks — histórico completo)
    runs-on: ubuntu-latest
    permissions:
      contents: read            # least-privilege (alinha com T-S4-04)
    steps:
      - uses: actions/checkout@<sha-40-hex>   # v4.x — pin por SHA (T-S4-04)
        with:
          fetch-depth: 0        # varre TODO o histórico, não só o tip
      - name: gitleaks
        uses: gitleaks/gitleaks-action@<sha-40-hex>   # v2.x — pin por SHA
        env:
          GITLEAKS_VERSION: "8.18.4"                  # PARIDADE com o pre-commit (rev do CLI)
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}   # a action usa p/ comentar no PR
          GITLEAKS_ENABLE_COMMENTS: "false"           # sem comentário no PR → dispensa pull-requests:write (mantém contents:read)
```

### 4.2 Decisão-chave: tag da *action* ≠ versão do *CLI* (paridade de detecção)

O pre-commit pina o **CLI** gitleaks em `rev: v8.18.4`. A `gitleaks-action` tem versionamento **próprio** (tags `v2.x`) e, por dentro, baixa um binário do CLI. Pinar só o SHA da action **não** garante que a detecção use a mesma engine/regras do pre-commit. Por isso:

- Pinar a **action por SHA** (imutabilidade de supply-chain — T-S4-04) **e**
- Fixar `GITLEAKS_VERSION: "8.18.4"` (a action respeita essa env e baixa exatamente esse CLI) → **paridade real** com o pre-commit. Sem isso, um dev passa no pre-commit (v8.18.4) e o CI reprova (ou vice-versa) por divergência de regras — o mesmo atrito de versão que o `.pre-commit-config.yaml` alerta.

**Alternativa considerada (escape hatch — decidir no review-loop se a licença bloquear):** instalar o **CLI diretamente** (baixar o binário `gitleaks_8.18.4_linux_x64` pinado por checksum e rodar `gitleaks detect --source . --redact --exit-code 1`). Vantagens: paridade byte-exata com o pre-commit, **zero dependência da action** (sem licença, sem `GITHUB_TOKEN`, sem `pull-requests` scope). Desvantagem: perde os comentários automáticos no PR (irrelevante aqui — o build vermelho já é o sinal). **Recomendação SRE:** se o repo for de **organização** (ver §4.3), preferir o CLI-direto; se for repo de **conta pessoal**, a action é aceitável. A decisão troca "1 secret de licença" por "1 passo de download+checksum" — levar ao dono (toca custo/licença).

### 4.3 Licença e `GITHUB_TOKEN` (blast radius / custo)

- **Licença:** `gitleaks/gitleaks-action` v2 **exige `GITLEAKS_LICENSE`** quando escaneia repositórios de uma **organização** GitHub; é **gratuita** para repos de **conta de usuário**. Confirmar a titularidade do repo no review-loop:
  - repo pessoal → sem licença, seguir com a action;
  - repo de org → obter licença em gitleaks.io **e** adicionar `GITLEAKS_LICENSE: ${{ secrets.GITLEAKS_LICENSE }}`, **ou** usar o escape hatch CLI-direto (§4.2) e evitar a licença. **Custo:** a licença da action é o único item pago potencial — decisão do dono.
- **`GITHUB_TOKEN`:** a action pede o token só para **comentar no PR**. Com `GITLEAKS_ENABLE_COMMENTS: false` desligamos o comentário e mantemos `permissions: contents: read` (least-privilege, alinhado a T-S4-04) — **não** precisamos elevar para `pull-requests: write`. O gate continua efetivo: achado ⇒ step com exit≠0 ⇒ job vermelho.

### 4.4 Prova red-green **sem** commitar segredo real na main (crítico)

O baseline exige "PR com segredo-canário faz o job falhar; verde ao remover". Fazer isso **sem** poluir o histórico da `main` (o scanner lê o **histórico cumulativo** — `docs/lessons/security.md`):

1. **Segredo-canário SINTÉTICO** — nunca uma credencial real. Usar um padrão que o gitleaks reconhece mas comprovadamente inválido, ex.: uma AWS key de exemplo da própria doc (`AKIAIOSFODNN7EXAMPLE`) ou um token com prefixo detectável marcado como fake. Objetivo: disparar uma **regra** do gitleaks, não vazar nada.
2. **Isolar numa branch efêmera de teste** (`test/gitleaks-canary`, descartável) — **jamais** na `main`:
   - commit do canário → abrir PR/push → **job vermelho** (prova o RED);
   - remover o canário (revert) → re-push → **job verde** (prova o GREEN);
   - **deletar a branch** após a prova. A `main` nunca recebe o canário.
3. Registrar no PR de T-S4-01 o **link do run vermelho** e do **run verde** da branch de teste como evidência (`gh run list`/aba Actions) — o playbook SRE exige provar que o gate roda de verdade, não que o YAML existe.
4. Se o canário sintético **não** disparar nenhuma regra default do gitleaks (falso-negativo), a prova é inconclusiva → ajustar o padrão até obter o vermelho **antes** de declarar o gate válido (senão "passa por acidente").

> **Anti-pattern barrado (security.md):** não versionar segredo real "só para testar"; segredo commitado é vazamento **permanente** no histórico e obrigaria rewrite/flatten. O canário é sintético e vive só na branch efêmera.

## 5. Impacto em testes e quality gates

- **Não** há teste unitário/pytest novo — o "teste" deste gate é o **próprio job de CI** (red-green provado na branch efêmera, §4.4). Alinha com o playbook SRE: certas invariantes viram gate/alarme, não teste de suíte.
- **Gate novo:** `secret-scan` entra no conjunto AND de merge (backend + frontend + secret-scan). Nenhum gate existente é afetado (cobertura backend/frontend intactas).
- **Sem regressão:** o job é aditivo; não altera passos de build/test existentes.
- **Determinismo (flaky = P1):** o job depende de download do CLI (`GITLEAKS_VERSION`) — pinar a versão exata evita "verde num dia, vermelho no outro" por bump silencioso. Sem `latest`/`master`.

## 6. Riscos

- **Divergência CLI×action** (detecção diferente do pre-commit) → mitigada por `GITLEAKS_VERSION: 8.18.4` (§4.2). Se o pre-commit subir a rev, subir a env junto (mesma disciplina do `.pre-commit-config.yaml`).
- **Licença de org bloqueia o job** → mitigada pelo escape hatch CLI-direto (§4.2/§4.3); decidir com o dono (custo).
- **Falso-positivo em fixtures** (ex.: senha canônica de teste `testpassword`) → allowlist cirúrgica no `.gitleaks.toml` **com justificativa** (security.md — "senha de teste canônica"; supressão cirúrgica, nunca global). Só criar o `.gitleaks.toml` se o `gitleaks detect` acusar algo legítimo-de-teste; caso contrário, sem config órfã.
- **`fetch-depth: 0` em repo grande** custa tempo de checkout — irrelevante neste repo (pequeno); necessário para varrer histórico (SEC-02 pede o histórico, não só o tip).
- **Canário vazando para a main** → mitigado por branch efêmera + deleção (§4.4); a `main` nunca recebe o canário.
- **Contaminação com T-S4-04** (mesmo `ci.yml`) → serializar: aplicar T-S4-04 (pin por SHA + `permissions`) e T-S4-01 numa passada coordenada, evitando dois PRs conflitantes no mesmo arquivo (CLAUDE.md — não paralelizar escrita no mesmo recurso). Ordem sugerida: **T-S4-01 primeiro** (fecha o piso Alto), T-S4-04 na sequência consolidando o pin/permissions do job novo junto.

## 7. Definition of Done (verificável)

- [ ] Job `secret-scan` presente em `.github/workflows/ci.yml`, disparando em `push` (`**`) e `pull_request` (`main`).
- [ ] `actions/checkout` do job com **`fetch-depth: 0`** (varre histórico) e **pinado por SHA de 40 hex** com comentário `# v4.x` (consolidado com T-S4-04).
- [ ] `gitleaks-action` **pinada por SHA de 40 hex** (`# v2.x`) **e** `GITLEAKS_VERSION: "8.18.4"` fixado (paridade com o pre-commit). Verificar que o SHA resolve para a tag: `git ls-remote https://github.com/gitleaks/gitleaks-action refs/tags/<tag>` bate com o SHA pinado.
- [ ] `permissions: contents: read` no job **e** `GITLEAKS_ENABLE_COMMENTS: "false"` (least-privilege; sem `pull-requests: write`).
- [ ] Licença resolvida conforme titularidade do repo (§4.3): repo pessoal → sem licença; repo de org → `GITLEAKS_LICENSE` **ou** escape hatch CLI-direto. Decisão registrada no PR.
- [ ] **Prova RED-GREEN** em branch efêmera (`test/gitleaks-canary`, deletada após): run **vermelho** com canário sintético + run **verde** após remoção; links dos dois runs no PR (`gh run list`). A `main` **nunca** recebe o canário.
- [ ] Segredo-canário é **sintético/inválido** (ex.: `AKIA...EXAMPLE`), nunca credencial real (security.md — histórico cumulativo).
- [ ] `.gitleaks.toml` **só** se houver allowlist legítima (fixture/senha canônica), com justificativa na linha; caso contrário, ausente.
- [ ] Job aparece rodando na aba Actions/`gh run list` (gate que roda de verdade — playbook SRE), não apenas presente no YAML.
- [ ] Sem regressão nos jobs `backend`/`frontend`; merge exige os três verdes (gate AND).
- [ ] Revisão aprovada (`tl-python`/`tl-qa`) sem ressalvas.

---

> **Fontes externas consultadas** (validar versão/licença no review-loop, não assumir):
> [gitleaks-action v2.md](https://github.com/gitleaks/gitleaks-action/blob/master/v2.md) ·
> [gitleaks-action README](https://github.com/gitleaks/gitleaks-action) ·
> [Gitleaks Action License — OSPO Guide](https://dsacms.github.io/ospo-guide/resources/gitleaks-action-license/)
