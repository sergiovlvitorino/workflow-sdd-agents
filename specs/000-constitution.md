# 000 — Constitution (Princípios Invioláveis)

**Status:** Vigente
**Versão:** 1.0.0
**Data:** 2026-06-24
**Fonte da verdade:** este documento prevalece sobre qualquer outro em caso de conflito; alterações exigem revisão de PO + Tech Lead + SRE + QA e bump de versão major.

> Este projeto adota **Spec-Driven Development (SDD)**: a especificação é a fonte da verdade. Código segue spec, não o contrário. Toda divergência entre código e spec é tratada como bug — corrige-se o que estiver errado (pode ser código OU spec, mas o desvio precisa ser explicitado e decidido).
>
> **Constitution genérica.** Estes são os princípios de engenharia que valem para qualquer projeto nascido deste base. Ao iniciar um projeto concreto, **mantenha os princípios** e adicione os específicos do seu domínio (regras regulatórias, invariantes de negócio próprios) como emendas versionadas — nunca enfraqueça um piso aqui sem ADR.

---

## P-01. API-First

Todo recurso de negócio é exposto primeiro como contrato de API pública (REST/JSON e/ou eventos). UI, jobs internos e SDKs consomem esse mesmo contrato. Não existe lógica de negócio acessível apenas via UI.

**Implicação:** a especificação de API (`005-api-contract.md`) é entregável obrigatório antes de qualquer implementação do recurso.

## P-02. Spec é fonte da verdade

- Nenhum código de produção é mergeado sem rastreabilidade a um RF e a pelo menos um critério de aceitação (CA-XXX).
- Mudança de comportamento exige mudança de spec **antes** de mudança de código.
- Specs são versionadas (semver) junto com a API.

## P-03. Idempotência obrigatória em operações de escrita

Toda operação que cria ou altera estado relevante **DEVE** aceitar chave de idempotência fornecida pelo cliente e garantir que requisições repetidas com a mesma chave produzem o mesmo resultado, sem efeito colateral duplicado.

**Justificativa:** efeito colateral duplicado (cobrança em dobro, registro duplicado, evento reemitido) é incidente caro. Idempotência é a primeira linha de defesa contra retries de cliente e de rede.

## P-04. Isolamento de dados por padrão

- Quando o sistema é multi-tenant, todo dado é particionado por `tenant_id` desde o modelo de domínio e não existe consulta sem filtro de tenant; vazamento cross-tenant é incidente de severidade máxima.
- Quando não há multi-tenancy, o princípio vale como **isolamento de autorização**: nenhum dado é retornado sem checagem explícita de quem pode vê-lo. Autorização é decidida no servidor, nunca confiando no cliente.

## P-05. Observabilidade desde o dia 1

- Todo endpoint público emite: log estruturado, métrica RED (Rate, Errors, Duration) e trace distribuído.
- Toda operação sensível de negócio gera evento de auditoria imutável.
- Dashboard de saúde do serviço é entregável de produto, não de ops.

## P-06. Compatibilidade e evolução planejadas

A arquitetura **DEVE** ser projetada para evoluir sem quebra: contratos extensíveis, integrações externas atrás de portas, e padrões/formatos de terceiros tratados como cidadãos substituíveis — nunca acoplados ao núcleo. Mudança previsível de regulação, parceiro ou plataforma não pode exigir reescrita do domínio.

## P-07. Cobertura mínima de testes por categoria de risco

| Categoria | Cobertura mínima de testes |
|---|---|
| Domínio crítico (regras de negócio, máquinas de estado, cálculos) | ≥ 90% linha + 100% branches críticos |
| Integrações externas / adapters | ≥ 80% + contract tests com fixtures gravados |
| API pública | 100% dos endpoints com testes de contrato |
| Isolamento / segurança (multi-tenant, autorização) | 100% dos cenários de isolamento testados |
| Idempotência | 100% das rotas de escrita |

Quem ajusta números é QA (`007-test-strategy.md`); estes são pisos, não tetos. O gate de cobertura é **ratchet**: só sobe, nunca desce sem ADR.

## P-08. Versionamento semântico de API e specs

- API pública versionada via prefixo `/v1`, `/v2`.
- Quebra de contrato exige major bump e janela mínima de coexistência (defina o prazo na spec da API; default sugerido: 90–180 dias).
- Specs seguem semver: major (quebra de contrato ou de princípio), minor (novo RF/feature), patch (clarificação sem mudança de comportamento).

## P-09. Privacidade e proteção de dados por design

- Dado pessoal é classificado e cifrado em repouso.
- Logs **não** contêm dado pessoal não-mascarado nem segredos.
- Direitos do titular (acesso, exclusão, portabilidade) são endpoints, não procedimentos manuais.
- Obrigações legais de retenção, quando existirem, prevalecem sobre solicitação de exclusão — e a base legal é registrada em ADR.

## P-10. Custódia de segredos e material criptográfico

- Segredos, chaves e certificados são armazenados cifrados (KMS/HSM/secret manager), nunca no filesystem da aplicação nem no repositório.
- Chave privada nunca trafega para fora do limite de confiança que a usa.
- Secret-scanning é gate de CI; artefato com segredo nunca é versionado (nem no histórico).

## P-11. Falha explícita > falha silenciosa

Em qualquer ambiguidade (dependência indisponível, payload inesperado, credencial vencida), a plataforma **DEVE** falhar com erro tipado e acionável. Nunca produzir resultado com fallback "best effort" que mascare o problema.

## P-12. Reversibilidade de integração

Cada integração externa é substituível sem mudança no domínio. O domínio não conhece o protocolo concreto (SOAP, XML específico, SDK de fornecedor) nem o nome do parceiro. A implementação concreta dessa regra é responsabilidade de arquitetura (`006-architecture.md`).

## P-13. Definição de pronto (DoD) é vinculante

Uma feature só é considerada entregue quando:

1. Spec aprovada e versionada.
2. Critérios de aceitação (CA-XXX) automatizados e verdes (com execução real, não só "compila").
3. Métricas RED instrumentadas.
4. Documentação pública (referência de API + exemplo) publicada.
5. Runbook operacional (SRE) escrito quando a feature tem operação não-trivial.
6. Revisão de segurança aprovada se a feature toca segredo, dado pessoal ou endpoint público novo.

## P-14. Decisões registradas (ADR-lite)

Toda decisão de produto, arquitetura ou trade-off não óbvio é registrada em texto curto, versionado, próximo da spec que a originou (`specs/adr/`). **Arquivar, não remover** — um ADR superado registra quem o substituiu.

---

## Cláusula de evolução

Esta constitution pode ser emendada. Toda emenda exige:

- Proposta escrita com motivação e impacto.
- Revisão por PO + TL + SRE + QA.
- Bump de versão e changelog explícito.
- Não é retroativa: specs já aprovadas seguem a versão da constitution sob a qual foram aprovadas, salvo migração explícita.
