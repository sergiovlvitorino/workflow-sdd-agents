# Playbooks de lições compartilhadas

Camada de conhecimento de engenharia destilado, **versionada no repositório** (`docs/lessons/`) e consumida pelos agentes (`.claude/agents/*/AGENT.md`) em todo o projeto. Como este é um projeto-base, estes playbooks são o **piso de rigor** com que cada novo projeto nasce — e crescem com as retrospectivas de cada um.

## Regras desta camada

1. **Só princípio generalizável entra.** Fato específico de uma entrega (nome de integração, ID de tarefa, detalhe de uma entidade) fica na memória local do projeto (`~/.claude/projects/<proj>/memory/`), **nunca** aqui. Antes de promover, pergunte: *"isto seria verdade em outra frente da mesma classe?"* Se não, não promova.
2. **Destile, não copie.** Transforme o fato cru no princípio que ele ensina. Ex.: *"o repo X precisou setar app.tenant_id"* → *"todo repositório que abre a própria sessão deve setar o GUC de tenant antes da query RLS"*.
3. **Cada lição é load-bearing.** Se não muda uma decisão de implementação ou revisão, não entra. Playbook é destilado, não despejo — prompt inchado degrada o agente.
4. **Datar e verificar.** Toda lição tem data. Uma lição verdadeira-quando-escrita envelhece: **confronte com o código atual antes de recomendar**. Se um arquivo/flag citado não existe mais, a lição está obsoleta — corrija ou remova.
5. **Sem contradições.** Duas lições conflitantes no mesmo playbook paralisam o agente. Ao promover, deduplique contra o que já existe.

## Como é alimentado

O passo de **retrospectiva** do `sprint-flow` faz a *promoção*: ao fechar uma sprint, além de gravar na memória local, decide explicitamente quais lições são generalizáveis, destila e anexa ao playbook do papel correspondente.

## Arquivos

- [qa.md](qa.md) — testes, quality gates, anti-falso-verde, anti-flaky.
- [python.md](python.md) — backend Python: RLS multi-tenant, idempotência, outbox, webhooks, paginação.
- [sre.md](sre.md) — infra, IaC, observabilidade, scheduler/jobs.
- [security.md](security.md) — autorização multi-tenant, secret-scanning, trust store/PKIX.
- [process.md](process.md) — orquestração, auditoria de specs, higiene de commit, paralelismo de agentes.
