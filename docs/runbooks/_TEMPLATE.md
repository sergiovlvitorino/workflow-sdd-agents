# Runbook — <Nome da operação / incidente>

> Entregável de SRE (P-13.5). Procedimento operacional acionável sob pressão. Escreva para alguém às 3h da manhã: passos diretos, comandos copiáveis, sem ambiguidade.

**Serviço:** <…>
**Severidade típica:** <SEV-1..3>
**Dono:** <papel/time>
**Última revisão:** AAAA-MM-DD

---

## 1. Quando este runbook se aplica

<Sintoma observável / alarme que dispara este procedimento.>

## 2. Diagnóstico rápido

| Sinal | Onde ver | Significado |
|---|---|---|
| <alarme/métrica> | <dashboard/log query> | <…> |

```bash
# comandos de diagnóstico (copiáveis)
```

## 3. Mitigação

> Objetivo: reduzir o tempo-até-mitigação. Estabilize primeiro, investigue causa-raiz depois.

1. <passo>
2. <passo>

## 4. Rollback

<Como reverter com segurança. Pré-condições e validação pós-rollback.>

## 5. Verificação de recuperação

- [ ] <métrica voltou ao baseline>
- [ ] <alarme limpo>

## 6. Causa-raiz e follow-up

<Após mitigar: registrar dívida (teste de regressão, ADR, correção definitiva). Encadear `hotfix-flow`/`bug-flow` se aplicável.>
