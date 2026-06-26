# CLAUDE.md — convenções do projeto

Guia para o Claude Code (e agentes) operarem neste repositório. Este é um **projeto-base** de Spec-Driven Development; a estrutura abaixo é o contrato de trabalho.

## Fonte da verdade

- A **spec manda**. Antes de mudar comportamento, mude a spec (`specs/`). Divergência código × spec é bug.
- A [`specs/000-constitution.md`](specs/000-constitution.md) prevalece sobre qualquer outro documento. Não enfraqueça um piso sem ADR.

## Mapa do repositório

- `specs/` — SDD (constitution vigente + templates em `_templates/`, `features/`, `adr/`, `tasks/`, `governance/`).
- `.claude/skills/` — fluxos de orquestração. **Prefira acionar a skill** a orquestrar na mão.
- `.claude/agents/` — time de agentes (`subagent_type` = nome da pasta).
- `docs/lessons/` — playbooks destilados. **Leia antes de decidir** e confronte cada lição com o código atual (lições envelhecem).
- `docs/{retrospectivas,runbooks,quality}/` — templates operacionais.

## Como trabalhar

- **Orquestre por skills:** `discovery-flow` → `sprint-flow` → `review-loop`; `design-flow` para ADRs; `bug-flow`/`debt-flow`/`coverage-flow`/`hardening-flow`/`hotfix-flow` para manutenção.
- **Separação de papéis:** PO decide *o quê/quando*, TL decide *como*, `review-loop` faz acontecer (com revisão), retrospectiva aprende. Não pule a aprovação do plano nem os DETAIL antes de executar.
- **Plano antes de código.** Para tarefa não trivial, apresente o plano e obtenha aprovação.

## Quality gates (não-negociáveis)

- Cobertura por categoria de risco (P-07), gate **ratchet** — só sobe, nunca desce sem ADR.
- Regressão **nasce vermelha** (red-green) antes do fix.
- Testes rodam **de verdade** (cobrem o wiring de DI), não só compilam. Rota nova exige teste HTTP real.
- `flaky = P1`. Secret-scan e lint **pinado** são bloqueantes.

## Higiene de commit (ver `docs/lessons/process.md`)

- `git add` **por caminho**, nunca `git add -A`/`.` — pode haver trabalho não-relacionado na árvore.
- Formatador/linter **pinado do projeto**, só nos arquivos tocados (`ruff format <arquivos>`, não `.`).
- Antes do PR: `git diff main HEAD --stat` para confirmar que **todo** o deliverable foi commitado (commitar de menos é o risco silencioso).
- Para reverter uma sonda de teste/mutação, use **Edit** na linha exata — nunca `git checkout` (apaga trabalho não-commitado adjacente).

## Paralelismo de agentes

- **Não paralelize** agentes que escrevem no mesmo repo + banco — contaminam o ambiente (falhas-fantasma em massa). Serialize ou isole com worktree + DB dedicado.
- Ao reacionar um agente já usado no fluxo, prefira `SendMessage` a abrir um novo (continuidade de contexto).

## Aprendizado persiste

- Toda sprint fecha com retrospectiva: memória local do agente **+** `docs/retrospectivas/sprint-NN.md`, coerentes entre si.
- O que for **generalizável** é destilado e promovido para `docs/lessons/<papel>.md` (regras em `docs/lessons/README.md`).
