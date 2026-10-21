# O loop de aprendizado

Como um erro pego em **uma** implementação vira um piso de rigor que **todo** agente passa a seguir.
O ciclo tem quatro estágios (`detectar → capturar → destilar → recarregar`) e três portões anti-falso-positivo embutidos.

```mermaid
flowchart TB
  classDef detect  fill:#eef1fd,stroke:#3b5bdb,stroke-width:2px,color:#171b22
  classDef capture fill:#e6f4f1,stroke:#0c8577,stroke-width:2px,color:#171b22
  classDef distill fill:#efeafc,stroke:#6741d9,stroke-width:2px,color:#171b22
  classDef reload  fill:#fcefe7,stroke:#d9480f,stroke-width:2px,color:#171b22
  classDef gate    fill:#ffffff,stroke:#c7cdd8,color:#4a5262,stroke-dasharray:4 3

  A["<b>1 · DETECTAR</b><br/><i>skill: review-loop</i><br/>dev-* implementa · tl-* + tl-qa revisam<br/>veredito APROVADO / RESSALVAS"]:::detect
  B["<b>2 · CAPTURAR</b><br/><i>sprint-flow §4 · retrospectiva</i><br/>memória local do agente<br/>+ docs/retrospectivas/sprint-NN.md"]:::capture
  C["<b>3 · DESTILAR</b><br/><i>sprint-flow §4.3.1 · promoção</i><br/>docs/lessons/{qa,python,sre,security,process}.md"]:::distill
  D["<b>4 · RECARREGAR</b> ◆ elo frágil<br/>.claude/agents/*/AGENT.md consomem lessons<br/>CLAUDE.md: ler antes de decidir"]:::reload

  G1["<b>Portão 1 — anti-falso-verde</b><br/>teste roda de verdade (infra real)<br/>escala p/ spec-* após 3 falhas"]:::gate
  G2["<b>Portão 2 — anti-perda de contexto</b><br/>dois destinos coerentes<br/>passo não-opcional"]:::gate
  G3["<b>Portão 3 — anti-erro-local</b><br/>só generalizável · datado<br/>deduplicado · sem contradição"]:::gate
  W["<b>⚠ sem gate automático</b><br/>ter a lição escrita não garante aplicá-la<br/>mitigação processual (disciplina de orquestração)"]:::gate

  A --> B --> C --> D
  D -->|"↺ o próximo agente nasce com o piso mais alto"| A

  A -.-> G1
  B -.-> G2
  C -.-> G3
  D -.-> W
```

## Legenda dos estágios

| # | Estágio | Onde | Portão anti-falso-positivo |
|---|---------|------|-----------------------------|
| 1 | **Detectar** — o erro é pego com prova, não com relato | `.claude/skills/review-loop/SKILL.md` | Teste roda de verdade (red-green); escala para `spec-*` com contexto limpo após 3 falhas |
| 2 | **Capturar** — aprendizado persistido em dois lugares coerentes | `sprint-flow` §4 (retrospectiva) | Memória local (sobrevive à sessão) **+** doc versionado (sobrevive ao git); não-opcional |
| 3 | **Destilar** — o generalizável sobe para os playbooks | `sprint-flow` §4.3.1 | Só princípio load-bearing, datado, deduplicado, sem contradizer lição anterior |
| 4 | **Recarregar** — playbooks viram o piso de todo agente | `.claude/agents/*/AGENT.md` + `CLAUDE.md` | ⚠️ **Elo frágil**: sem gate automático — depende de ler `docs/lessons/` antes de decidir |

## O elo frágil (provado pela Sprint 3)

Captura e destilação são **estruturais** (têm gate). A vulnerabilidade real é o **recarregamento**: a lição pode existir e não ser lida no momento da decisão.

> Rodei o `tl-qa` (que muta para red-green) em paralelo com o `tl-frontend` (read-only) sobre o mesmo arquivo — anti-pattern **já documentado** em `process.md`. A lição já existia; o custo foi não tê-la aplicado.
> — [`docs/retrospectivas/sprint-03.md`](retrospectivas/sprint-03.md)

No mesmo episódio o mecanismo também funcionou: a retrospectiva **reforçou** a lição existente em vez de duplicá-la — exatamente a regra de deduplicação do Portão 3.

---

**Fontes:** [`review-loop`](../.claude/skills/review-loop/SKILL.md) · [`sprint-flow`](../.claude/skills/sprint-flow/SKILL.md) · [`docs/lessons/README.md`](lessons/README.md) · [`docs/retrospectivas/sprint-03.md`](retrospectivas/sprint-03.md)
