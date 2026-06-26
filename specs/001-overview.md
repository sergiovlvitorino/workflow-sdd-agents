# 001 — Overview (Visão de Produto)

**Status:** Vigente
**Versão:** 1.0.0
**Data:** 2026-06-24
**Responsável:** PO
**Constitution:** v1.0.0
**Origem:** `specs/backlog-blog-tutorial.md` (discovery-flow)

> Este documento responde *por que o produto existe* e *para quem*. Não descreve solução técnica (isso é `006-architecture.md` + ADRs). Enxuto de propósito: o produto é um exemplo de ensino.

## 1. Problema

Um dev que acabou de clonar este projeto-base de **Spec-Driven Development (SDD)** encontra 9 skills, 20+ agentes e 7 templates e **não sabe por onde começar nem como as peças se conectam**. Ler documentação solta não mostra o fluxo em ação. O custo de não resolver: alto *time-to-first-contribution* — o dev clona e trava.

O **Blog Tutorial** é o "hello world" didático que resolve isso. O domínio "posts de blog" foi escolhido por ser universalmente compreendido (zero carga cognitiva de negócio), deixando 100% da atenção no **processo SDD**. O valor não está no blog funcionar — está no caminho percorrido para construí-lo.

## 2. Cliente-alvo (ICP) e personas

| # | Persona | Quem é | Objetivo |
|---|---|---|---|
| **P1 (primária — cliente real)** | Dev-aprendiz | Dev que clonou o base e quer aprender a operá-lo | Percorrer o ciclo SDD completo uma vez, vendo agentes (PO/TL/dev/QA) e quality gates em ação |
| P2 (secundária) | Autor fictício | Personagem do domínio | Criar/editar/listar posts — dá substância ao caminho de escrita |
| P3 (secundária) | Leitor fictício | Personagem do domínio | Ler/listar posts — dá substância ao caminho de leitura/paginação |

> O cliente real é **P1**. P2/P3 existem só para que o domínio exercite os princípios. Toda decisão de escopo é tomada a favor de P1.

## 3. Proposta de valor

Em uma frase: **transforma "clonei e travei" em "completei um ciclo e entendi o fluxo"** — o dev *vê* os princípios da constitution nascerem como artefatos testáveis (um teste de idempotência passando vale mais que ler "P-03"). Diferencial vs. status quo (README extenso, docs soltas): o dev opera os agentes de verdade sobre um domínio trivial, e o repo vira a **referência canônica viva** que a documentação aponta ("siga o blog-tutorial").

## 4. Escopo do MVP

MVP = **Sprint 1** + núcleo Must. O menor conjunto que faz P1 percorrer o ciclo e ver os princípios em ação.

| Inclui (MVP) | Não inclui (fora do MVP) |
|---|---|
| **Sprint 1:** F007 (specs-exemplo), F001 (criar post idempotente), F003 (listar paginado) | F006 healthcheck/dashboard (Could) |
| **Sprint 2 (núcleo):** F002 (editar/publicar com autorização), F004 (ler por id), F008 (guia da trilha) | F009 categorias/tags (Wont v1) |
| Recomendado se couber: F005 (observabilidade mínima) | F010 comentários (Wont v1) |

> Esta spec (`001`) e o conjunto de Sprint 1 (F007) entregam o **esqueleto andante**: specs preenchidas + escrita idempotente + leitura paginada.

## 5. Métricas de sucesso (didáticas)

| Métrica | Baseline | Meta | Como medir |
|---|---|---|---|
| M1 — dev novo completa o ciclo ponta-a-ponta seguindo o exemplo | "clona e trava" | < 1 dia de trabalho guiado | autoavaliação no fim da trilha (F008) |
| M2 — princípios da constitution demonstrados pelo MVP (≥1 artefato/teste visível por princípio) | 0 | ≥ 6 dos 14 | rastreabilidade Story→Princípio (backlog §9); núcleo Must cobre 9 |
| M3 — skills da espinha dorsal percorridas (discovery→design→sprint→review-loop→retrospectiva) | — | 5 de 5 | trilha F008 |
| M4 — dev explica "gate ratchet" e "regressão nasce vermelha" ao final | — | autoavaliação positiva | checklist no fim da trilha (F008) |

## 6. Riscos e premissas

- **Premissa:** o domínio trivial (posts) não rouba atenção do processo. Se o blog crescer (categorias, comentários — F009/F010), o foco em P1 se perde → mantidos como Wont v1 de propósito.
- **Risco:** material didático tende a ser copiado para produção. O adapter in-memory/SQLite **precisa** estar marcado como didático (ADR-0001) para não virar base de produto real.
- **Risco:** repo poliglota (Python + Angular) = duas toolchains; atrito de ambiente pode atrapalhar P1 — mitigado mantendo o MVP magro (ADR-0001).
- **Premissa:** nem todos os 14 princípios cabem num exemplo mínimo, e tudo bem. Fora de escopo de propósito: P-10 (custódia de segredos), P-12 (reversibilidade de integração — não há integração externa). Registrado para não criar expectativa de cobertura total.

## 7. Marcos / roadmap de alto nível

| Onda | Conteúdo | Entrega |
|---|---|---|
| **Sprint 1** | F007 + F001 + F003 | Esqueleto SDD: specs preenchidas + escrita idempotente + leitura paginada |
| **Sprint 2** | F002 + F004 + F008 (+ F005 se couber) | Autorização, leitura unitária, fechamento da trilha didática |
| Backlog | F006, F009, F010 | Registrados, fora do MVP — evitam escopo implícito |
