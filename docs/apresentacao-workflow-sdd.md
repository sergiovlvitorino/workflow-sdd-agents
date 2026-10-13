# Roteiro de Apresentação — `workflow-sdd-agents`

> **Tema:** Um repositório-base de Spec-Driven Development (SDD) operado por um time de agentes de IA.
> **Público-alvo:** desenvolvedores, tech leads e líderes de engenharia interessados em processo assistido por IA com rigor de qualidade.
> **Duração sugerida:** 30–40 min (25 de fala + 10–15 de demo ao vivo).
> **Mensagem central:** *A spec manda.* Todo comportamento nasce como uma decisão registrada e um teste que passa — e o time de agentes existe para fazer isso acontecer com governança, não velocidade cega.

---

## 0. Antes de começar (checklist do apresentador)

- Abrir o repo no editor com estes arquivos à mão: [`README.md`](../README.md), [`CLAUDE.md`](../CLAUDE.md), [`specs/000-constitution.md`](../specs/000-constitution.md), [`specs/backlog-blog-tutorial.md`](../specs/backlog-blog-tutorial.md).
- Terminal com `backend/` pronto para rodar `pytest` e `coverage-gates.sh` (o "gate que morde" ao vivo é o momento mais forte da demo).
- Ter aberto o CI: [`.github/workflows/ci.yml`](../.github/workflows/ci.yml).

---

## 1. Abertura — o problema (2 min)

**Fala:** "Todo mundo já viu IA gerar código rápido. O problema não é gerar — é *governar*. Como garantir que o que a IA produz respeita arquitetura, segurança, cobertura de teste e as decisões que o time já tomou? Este projeto é uma resposta: um repositório onde a IA opera **dentro de um contrato**."

- Gancho: código rápido sem processo vira dívida silenciosa.
- Tese: SDD + time de agentes + quality gates = velocidade **com** rigor.

---

## 2. O que é este repositório (3 min)

**Fala:** "Não é uma aplicação. É um **projeto-base** — um template do qual novos projetos nascem já com rigor técnico de zero: constituição vigente, time de agentes versionado, skills de orquestração e playbooks de lições."

Mostrar o mapa de diretórios:

| Diretório | O que é |
|---|---|
| `specs/` | A fonte da verdade — constituição, ADRs, requisitos, tasks |
| `.claude/skills/` | 9 fluxos de orquestração multi-agente |
| `.claude/agents/` | 19 agentes (PO, Tech Leads, Devs, QA, SRE, especialistas) |
| `docs/lessons/` | Playbooks destilados que os agentes leem antes de decidir |
| `docs/retrospectivas/` | Aprendizado versionado por sprint |
| `backend/` + `frontend/` | Aplicação-exemplo `blog-tutorial` (poliglota **de propósito**) |

**Ponto-chave:** o `blog-tutorial` é pretexto. O cliente real é o **dev-aprendiz** — o blog serve para *ver* cada princípio virar teste.

---

## 3. A Constituição — a lei do projeto (4 min)

**Fala:** "Antes de qualquer código, existe uma constituição. 14 princípios invioláveis. Ela prevalece sobre qualquer outro documento e mudá-la exige revisão de PO+TL+SRE+QA e bump major."

Abrir [`specs/000-constitution.md`](../specs/000-constitution.md) e destacar os que mais aparecem na demo:

- **P-02** — A spec é a fonte da verdade. Divergência código × spec **é bug**.
- **P-07** — Cobertura mínima por categoria de risco, com **gate ratchet** (só sobe, nunca desce sem ADR).
- **P-03** — Idempotência obrigatória em escrita.
- **P-11** — Falha explícita > falha silenciosa.
- **P-13** — Definition of Done é vinculante.
- **P-14** — Toda decisão vira ADR ("arquivar, não remover").

**Transição:** "Se a constituição diz *o que* nunca pode ser violado, como o trabalho realmente flui? Por skills."

---

## 4. As Skills — o ciclo de vida orquestrado (6 min)

**Fala:** "Cada skill é um fluxo que coordena vários agentes. A espinha dorsal segue o ciclo de vida do software."

Desenhar o ciclo (usar como slide-diagrama):

```
ideia crua
   │
   ├─ /discovery-flow  → backlog refinado (épicos, stories, MoSCoW, MVP)
   │
   ├─ /design-flow     → ADR versionado (painel de Tech Leads propõe abordagens)
   │
   ├─ /sprint-flow     → plano por sprint + specs DETAIL (TLs detalham o "como")
   │       │
   │       └─ /review-loop → código + testes (implementa → revisa → corrige)
   │
   └─ retrospectiva    → docs/retrospectivas/ + memória do agente + docs/lessons/
```

Tabela das 9 skills (mostrar rapidamente, aprofundar só as 3 primeiras):

| Skill | Função | Aciona |
|---|---|---|
| **discovery-flow** | demanda crua → backlog | `product-owner`, `po`, `tl-qa` |
| **sprint-flow** | fatia sprints, detalha, executa, retrospectiva | `po` → `tl-*` → review-loop |
| **review-loop** | implementa → revisa → corrige até zero ressalvas | `dev-*`/`qa` → `tl-*`/`tl-qa` → `spec-*` |
| **design-flow** | decisão de arquitetura → ADR | painel de 2–3 `tl-*` |
| **bug-flow** | correção dirigida por teste (regressão nasce vermelha) | `qa` → review-loop |
| **debt-flow** | refactor preservando comportamento | `qa` → `Plan` → review-loop |
| **coverage-flow** | sobe cobertura até o gate, sem tocar produção | `qa-automator` → `tl-qa` |
| **hardening-flow** | revisão de segurança por risco | painel `tl-qa`+`tl-*`+`sre` |
| **hotfix-flow** | caminho rápido para incidente | `sre` → dev → tl → deploy |

**Destaque do review-loop:** escala ao **especialista após 3 falhas** do mesmo agente; teto de 5 iterações; **exige execução real dos testes**, não só compilar.

---

## 5. O Time de Agentes — separação de papéis (4 min)

**Fala:** "O eixo de tudo é a separação de papéis. Ninguém acumula decisão e execução."

```
PO         decide  →  O QUÊ / QUANDO   (product-owner, po)
Tech Lead  decide  →  O COMO           (tl-python, tl-java, tl-go, tl-frontend, tl-qa)
Dev/QA     fazem   →  ACONTECER        (dev-*, qa, qa-automator)  — sempre com revisão
Especialista       →  ESCALADA         (spec-*)  — após 3 ciclos sem sucesso
SRE                →  INFRA/INCIDENTE  (sre)
Retrospectiva      →  APRENDE
```

Dois princípios operacionais que valem ouro (de [`docs/lessons/process.md`](lessons/process.md)):

1. **Não paralelizar** dois agentes que escrevem no mesmo repo+banco — contaminam o ambiente (falhas-fantasma). Serialize ou isole com worktree.
2. **Continuidade de contexto:** reacionar um agente com `SendMessage`, não abrir um novo.

---

## 6. Quality Gates — o coração do rigor (5 min) ⭐

**Fala:** "Aqui está o diferencial. Um teste que passa não prova nada se o gate não *morde*. Este projeto trata gate como parte da lógica."

Conceitos para explicar (todos ilustráveis ao vivo):

- **Gate ratchet:** cobertura só sobe. Backend hoje em `--cov-fail-under=99`, patamar real medido com folga ≤1pp — nunca número redondo.
- **Piso por categoria de risco:** [`backend/coverage-gates.sh`](../backend/coverage-gates.sh) mede independentemente 7 categorias (domínio, idempotência de escrita, isolamento/P-04, adapter-sqlite, api-router, error-handlers/RFC 9457, observabilidade) — **gate AND**, nunca média global (média mascara o lado fraco).
- **Sentinela anti-glob-vazio:** 0 statements **reprova**, não passa vacuamente.
- **Regressão nasce vermelha (red-green):** o bug-flow escreve o teste que falha *antes* do fix — é a DoD.
- **Contract test cross-language:** o frontend Angular gera tipos do OpenAPI do backend; um **gate de drift** (`git diff --exit-code`) quebra o CI se o contrato divergir.

**Momento de demo (opcional, forte):** rodar `coverage-gates.sh`, remover um teste de uma categoria crítica e mostrar o gate reprovando.

---

## 7. A aplicação-exemplo — SDD na prática (4 min)

**Fala:** "Para não ficar abstrato, tudo isso é demonstrado num blog. Domínio banal de propósito — o foco é o processo."

- **Backend** (`backend/`): Python + FastAPI, arquitetura **hexagonal** (`domain/` puro → `application/` → `infrastructure/` adapters → `interfaces/`). Post com máquina de estados `draft→published` idempotente, relógio injetado (nunca `datetime.now()` interno).
- **Frontend** (`frontend/`): Angular 19 standalone, signals-first, Vitest, tipos **auto-gerados** do contrato OpenAPI.
- **Poliglota de propósito** (ADR-0001): duas linguagens para ensinar contract test cross-stack.

Mostrar a rastreabilidade: uma story do backlog → um ADR → uma spec DETAIL → código + teste + entrada na retrospectiva. **Esse é o "fio" que amarra tudo.**

---

## 8. Aprendizado que persiste (3 min)

**Fala:** "O que separa isto de uma automação qualquer: o time *aprende*. Toda sprint fecha com retrospectiva em dois lugares coerentes — memória local do agente e doc versionado. O que é generalizável é destilado e promovido para `docs/lessons/`."

- [`docs/lessons/`](lessons/): playbooks de `process`, `python`, `qa`, `security`, `sre` — lidos pelos agentes **antes de decidir**.
- Regra de promoção: só princípio load-bearing e generalizável entra; destilar, não copiar; **datar e confrontar com o código** (lições envelhecem).

---

## 9. Encerramento — por que isso importa (2 min)

**Fala:** "Não é IA escrevendo código mais rápido. É IA operando dentro de um contrato de engenharia — com a spec mandando, papéis separados, gates que mordem e aprendizado que persiste. Velocidade **com** rigor, auditável de ponta a ponta."

Três frases para fechar:
1. **A spec manda** — comportamento muda na spec primeiro.
2. **O gate morde** — teste verde só vale se o gate reprova quando devia.
3. **O time aprende** — cada sprint deixa o próximo mais forte.

---

## Apêndice A — Roteiro de demo ao vivo (10–15 min)

1. Abrir [`specs/000-constitution.md`](../specs/000-constitution.md) — mostrar P-07 (tabela de cobertura).
2. Abrir [`specs/backlog-blog-tutorial.md`](../specs/backlog-blog-tutorial.md) — mostrar épicos, MoSCoW e o corte de escopo (F009/F010 = Won't v1).
3. Seguir o fio de **uma** story: backlog → `specs/adr/` → `specs/tasks/sprint-02/` (DETAIL) → código no `backend/src/blog/`.
4. Rodar `pytest` no backend (verde) e depois `coverage-gates.sh`.
5. **Clímax:** apagar um teste de categoria crítica → rodar de novo → gate reprova. "Isto é um gate que morde."
6. Mostrar [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) — dois jobs, gate AND, drift de contrato.

## Apêndice B — Perguntas prováveis da plateia

- *"Os agentes podem burlar os gates?"* → Não: os gates rodam no CI, fora do controle do agente; o review-loop exige execução real.
- *"E se dois agentes se atrapalharem?"* → Regra explícita de não-paralelismo em repo+banco compartilhado (isolar com worktree).
- *"Como isso escala para um projeto real?"* → O template é agnóstico; o blog é só a trilha didática. Novos projetos preenchem `specs/_templates/` e herdam skills, agentes e lições.
- *"Quem manda, a IA ou a spec?"* → A spec. Divergência código × spec é bug (P-02).

## Apêndice C — Estrutura enxuta de slides (se precisar de deck)

1. Título + tese
2. O problema (IA rápida ≠ IA governada)
3. O que é o repo (mapa de pastas)
4. A Constituição (P-02, P-07, P-13, P-14)
5. O ciclo de skills (diagrama)
6. Tabela das 9 skills
7. Time de agentes (separação de papéis)
8. Quality gates (o gate que morde) ⭐
9. Aplicação-exemplo (o fio backlog→ADR→DETAIL→código→teste)
10. Aprendizado que persiste
11. Encerramento (3 frases)
12. Demo ao vivo
