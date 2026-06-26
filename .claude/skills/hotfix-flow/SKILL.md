---
name: hotfix-flow
description: Caminho rápido para incidente em produção. O SRE diagnostica a causa-raiz (logs, métricas, alarmes) e propõe o fix mínimo; um desenvolvedor aplica, um tech lead revisa em 1 ciclo enxuto e o deploy é disparado. Corta deliberadamente a cerimônia de sprint para minimizar o tempo-até-mitigação, registrando a dívida (teste/retro) para depois. Use quando o usuário relatar incidente/outage em produção, pedir um "hotfix urgente", ou disser /hotfix-flow <incidente>.
---

# hotfix-flow

Estratégia de **resposta rápida a incidente**: otimiza tempo-até-mitigação, não completude. É o oposto do `sprint-flow` — corta cerimônia de propósito e paga a dívida depois.

## Quando usar

Quando há algo **quebrado em produção** (outage, erro em massa, dado corrompido, regressão crítica liberada) e o objetivo é mitigar **agora**. Vem como argumento (`/hotfix-flow <incidente>`) ou da conversa.

> **Se não é urgente nem em produção, não use isto.** Bug comum → `bug-flow`. O hotfix-flow troca rigor por velocidade conscientemente; só vale quando o custo de esperar é alto.

## Princípios

- **Mitigar primeiro, perfeição depois.** Um fix mínimo e reversível que estanca o sangramento vence uma solução elegante que demora.
- **Diagnóstico orientado a evidência.** O `sre` decide a causa por logs/métricas/alarmes, não por palpite. Sem causa identificada, considere mitigação operacional (rollback, feature flag, throttle) antes do código.
- **Dívida explícita.** Todo atalho tomado (teste faltando, retro não feita, cobertura adiada) é **registrado** ao final para virar tarefa de follow-up — nunca esquecido.
- **Você é o orquestrador.** Diagnóstico → `sre`; fix → 1 `dev`/`spec`; revisão → 1 `tl`; deploy → skill `deploy` (ou procedimento do projeto).

## Mapeamento

| Passo | Agente |
|-------|--------|
| Diagnóstico / causa-raiz / opção de mitigação | `sre` |
| Aplicar o fix mínimo | `dev-*` da stack (ou `spec-*` se crítico/complexo) |
| Revisão enxuta (1 ciclo) | `tl-*` da stack |
| Validar invariante crítica (se houver risco) | `tl-qa` |
| Deploy | skill `deploy` ou procedimento do repo |

## Procedimento

### 0. Triagem (rápida)
1. Capture: o que quebrou, desde quando, impacto (quem/quanto), e se há mitigação operacional imediata (rollback/flag). Severidade define o quão enxuto será o ciclo.
2. Crie um TODO curto: diagnóstico → mitigação → fix → revisão → deploy → registrar dívida.

### 1. Diagnóstico (agente `sre`)
Acione o `sre` para: ler logs/métricas/alarmes, isolar a **causa-raiz** (ou a hipótese mais provável) e recomendar o **caminho mais rápido e seguro** — que pode ser:
- **Mitigação operacional** (rollback do último deploy, desligar feature flag, throttle/circuit-breaker) — frequentemente o passo certo **antes** de qualquer código; ou
- **Fix de código mínimo** quando a causa é clara e pequena.

Se a mitigação operacional já estanca o incidente, faça-a primeiro e trate o fix definitivo com menos pressa (possivelmente via `bug-flow` depois).

### 2. Fix mínimo (agente `dev-*` ou `spec-*`)
Acione **um** implementador da stack com instrução de **mudança cirúrgica e reversível** que resolve a causa identificada pelo `sre`. Para incidentes críticos ou de causa sutil, vá direto ao `spec-*` (pula a curva do dev). Peça: o diff mínimo, o porquê resolve, e o risco residual.

### 3. Revisão enxuta (agente `tl-*`)
**Um** ciclo de revisão com o `tl-*` da stack, focado em: o fix resolve a causa? introduz risco novo? é reversível? Acione o `tl-qa` **apenas** se o fix tocar uma invariante crítica (dados, segurança, dinheiro). Não rode o loop completo de 5 iterações — aqui o teto é praticamente 1–2.

### 4. Deploy
Dispare a skill `deploy` (ou o procedimento de release do projeto) para o ambiente afetado. Confirme com o `sre` que o incidente **de fato cessou** (métricas/alarmes voltaram ao normal) — mitigação não é o mesmo que confirmação.

### 5. Encerramento + dívida
Resuma o incidente, causa-raiz, o que foi feito (mitigação e/ou fix), confirmação de normalização, e **liste explicitamente a dívida** gerada:
- Teste de regressão ainda não escrito → propor `bug-flow` de follow-up.
- Postmortem/retrospectiva pendente.
- Hardening ou fix definitivo se só houve mitigação.

Ofereça registrar esses follow-ups como tarefas no backlog do projeto.

## Observações
- Prefira **reversibilidade** a engenhosidade: um rollback ou flag bate um fix arriscado sob pressão.
- Nunca declare o incidente resolvido sem o `sre` confirmar pelo sinal real (métrica/alarme), não só pelo deploy ter passado.
- O atalho de cerimônia é **consciente e temporário** — a dívida registrada na etapa 5 não é opcional.
