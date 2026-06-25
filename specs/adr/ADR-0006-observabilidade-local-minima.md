# ADR-0006 — Observabilidade local mínima: logging estruturado + request_id

**Status:** Aceito _(com refinamentos do painel — ver §8)_ · _(Proposto → Aceito → Substituído por ADR-XXXX | Rejeitado)_
**Data:** 2026-06-25
**Autor:** design-flow (orquestrador-sintetizador)
**Revisores requeridos:** SRE + Tech Lead Backend + Tech Lead QA
**Constitution:** v1.0.0
**Relacionado a:** F005 (observabilidade) · P-05 (observabilidade desde o dia 1) · `specs/006-architecture.md` (middleware ASGI reservado) · `specs/004-non-functional-requirements.md`

---

## 1. Contexto

P-05 da constitution exige **observabilidade desde o dia 1**, e a arquitetura (`006`) já **reservou** o ponto de wiring: um middleware ASGI único. F005 implementa isso na Sprint 2. A pergunta é o **nível** apropriado: o app é **pequeno, roda localmente, sem tráfego real**. Subir métricas RED com Prometheus/OTel seria desproporcional; não ter nada violaria P-05.

Decidir agora calibra F005 antes de implementá-la, e evita que o exemplo ensine ou over-engineering (infra de métricas para um app local) ou negligência (nenhum traço de request).

**Forças:**
- P-05 é um piso da constitution — algo de observabilidade é obrigatório.
- O contexto local/pequeno desfavorece infra de métricas.
- Clareza pedagógica: ensinar o conceito (request_id correlacionável, log estruturado) sem stack de infra.
- `004` já registra que SLOs/RED completos são dívida honesta fora do MVP.

## 2. Alternativas consideradas

| Alternativa | Prós | Contras |
|---|---|---|
| **A. Logging estruturado (JSON) + `request_id` via middleware ASGI** _(escolhida)_ | Satisfaz P-05 no nível certo para local; ensina correlação de logs e o padrão de middleware único; zero infra externa; usa o ponto de wiring já reservado em `006` | Não dá dashboards/alertas (irrelevante sem tráfego real); métricas agregadas ficam para depois |
| **B. Métricas RED + Prometheus/OTel** | Observabilidade "de produção" completa | Desproporcional para app local sem tráfego; sobe stack de infra que contraria o escopo pequeno; ensina complexidade prematura |
| **C. Nada (logs default do Uvicorn)** | Zero esforço | **Viola P-05**; sem `request_id` não há correlação; ensina negligência |

## 3. Critérios de decisão

| Critério | Peso | Por quê |
|---|---|---|
| Conformidade com P-05 (piso da constitution) | **Alto** | Não-negociável; algo tem de existir desde o dia 1 |
| Proporcionalidade ao escopo (local, pequeno) | **Alto** | Não subir infra desnecessária |
| Clareza pedagógica | **Alto** | Ensinar o conceito sem ruído de produção |
| Aproveitar o wiring já reservado (`006`) | Médio | Coerência arquitetural |

## 4. Decisão

**Escolhida: Alternativa A — logging estruturado + `request_id`, via o middleware ASGI único já reservado.**

F005 implementa um **único middleware ASGI** que:
- gera/propaga um `request_id` por requisição (aceitando um header de correlação de entrada, se presente; senão, gerando um);
- emite logs **estruturados** (JSON em stdout) com, no mínimo, `request_id`, método, rota, status e duração — o esqueleto do RED (Rate/Errors/Duration) em forma de log, sem backend de métricas;
- correlaciona o `request_id` em logs de erro (incluindo os Problem Details de P-11).

Inegociável:
- **Um** ponto de wiring (o middleware reservado em `006`), não instrumentação espalhada.
- Logs em **stdout** (12-factor), estruturados, sem segredos (P-10) e sem PII (P-09).
- Saída determinística o suficiente para teste (sem depender de timestamps livres nas asserções de conteúdo).

## 5. Consequências

- **Positivas:** P-05 satisfeito no nível proporcional ao escopo; o exemplo ensina correlação por `request_id` e o padrão de middleware único; nenhuma infra externa para rodar local.
- **Negativas / custo assumido:** sem métricas agregadas/dashboards/alertas (explicitamente fora do MVP, já registrado como dívida em `004`); se um dia houver tráfego real, RED/SLOs entram por novo ADR (com o SRE, conforme `004`).
- **Impacto em specs/código:** F005 materializa o middleware em `interfaces/`; `004`/`006` referenciam este ADR como o nível de observabilidade adotado.
- **Impacto em testes/gates:** teste de que toda resposta carrega/correlaciona `request_id`; teste de que erro tipado (P-11) sai no log estruturado com o `request_id` da requisição; asserções determinísticas (sem depender de duração/relógio).

## 6. Gatilhos de revisão

Reabrir esta decisão se:
- O projeto ganhar tráfego real ou for além de `localhost` (aí RED/SLOs/dashboards passam a valer — ver `004`, definidos pelo SRE).
- Surgir necessidade de tracing distribuído (múltiplos serviços).

## 7. Aprovações

| Papel | Nome/agente | Data | Veredito |
|---|---|---|---|
| SRE | `sre` | 2026-06-25 | Aprovado com ressalvas — sanitização de header, allowlist de campos, formato em §8 |
| Tech Lead Backend | `tl-python` | 2026-06-25 | Aprovado com ressalvas — propagação do request_id aos handlers (§8); middleware único não basta sozinho |
| Tech Lead QA | `tl-qa` | 2026-06-25 | Aprovado com ressalvas — asserções determinísticas e teste de correlação/PII em §8 |

## 8. Refinamentos do painel de validação (2026-06-25)

Condições **vinculantes** para a implementação da F005:

- **Propagação (bloqueante):** o middleware único **não** correlaciona o `request_id` nos Problem Details sozinho — os exception handlers de `interfaces/errors.py` são funções isoladas que hoje não têm o id. Mecanismo: o middleware grava em `request.state.request_id` (os handlers já recebem `Request`); opcionalmente um `contextvars.ContextVar` para logs fora do ciclo da request. O **id_gen é injetável** no `create_app` (DI, como `_new_ulid`/`_utc_now`) — sem isso o teste de correlação não consegue afirmar o valor.
- **Header de entrada:** aceitar **`X-Request-ID`**; é input externo (P-11) → **sanitizar** (charset `[A-Za-z0-9._-]`, ≤128 chars) ou descartar e **gerar** um ULID. Risco principal: log injection (CRLF/lixo quebrando o JSON). **Ecoar** o `request_id` no header da resposta (vira asserção de teste).
- **Corpo do erro:** decisão — `request_id` vai **só no header + log** (não toca o contrato `005`). Alternativa: incluí-lo no corpo via campo `instance` do RFC 9457 → exigiria **minor bump** em `005`. Default adotado: header + log (sem mudança de contrato).
- **Campos do log (JSON Lines em stdout, 1 evento = 1 linha):** `timestamp` (ISO-8601 UTC), `level`, `request_id`, `method`, `route` (**template** `/v1/posts/{id}`, **nunca** a path com valores — cardinalidade/vazamento de id), `status`, `duration_ms` (numérico). Nomes snake_case estáveis.
- **Privacidade (P-09/P-10):** **allowlist** de campos, não blocklist. Nunca logar body, query string crua ou headers arbitrários; `title`/`content` ficam **fora** do log; nunca `Authorization`/cookies (hábito ensinado mesmo sem auth hoje).
- **Robustez:** o middleware envolve `call_next` em `try/finally`; a captura de log/duração **nunca** propaga exceção própria — observabilidade não pode virar causa de `500`.
- **Testes (condição de aceite):**
  - **Dois branches:** request **com** `X-Request-ID` → log usa esse id; request **sem** → log usa id gerado, não-vazio.
  - **Correlação (o teste central):** num caso de **erro** (422/400 já existentes), `log["request_id"] == resp.headers["x-request-id"]`. **Mutation-âncora:** gerar id novo no log em vez de propagar o da request → teste vermelho.
  - **Negativo de PII:** `content` com valor-sentinela → assertar que **não aparece** no log.
  - **Determinismo:** assertar **presença e tipo** de `duration_ms`/`timestamp` (ex.: `>= 0`), **nunca o valor** (flaky = P1).
  - Middleware exercitado via **TestClient HTTP real** (wiring de produção), não isolado à mão.
