# 002 — Domain Model

**Status:** Rascunho
**Versão:** 0.1.0
**Data:** AAAA-MM-DD
**Responsável:** PO + TL
**Constitution:** v1.0.0

> Preencha e mova para `specs/002-domain-model.md`. Define a **linguagem ubíqua** e as **invariantes** — o vocabulário que código, testes e specs compartilham.

## 1. Linguagem ubíqua (glossário)

| Termo | Definição | Sinônimos a evitar |
|---|---|---|
| | | |

## 2. Entidades e agregados

<Para cada agregado: raiz, entidades/value objects internos, identidade, ciclo de vida. Diagrama se ajudar.>

## 3. Máquina(s) de estados

```
<estado-inicial> ──evento──▶ <estado> ──▶ <terminal>
```

| De | Evento | Para | Guarda / pré-condição |
|---|---|---|---|
| | | | |

## 4. Invariantes (RN-D-NN)

> Regras sempre verdadeiras, independentes de feature. Cada uma vira teste negativo (P-07).

- **RN-D-01:** <…>
- **RN-D-02:** <…>

## 5. Eventos de domínio

| Evento | Quando ocorre | Payload essencial | Consumidores |
|---|---|---|---|
| | | | |

## 6. Identificadores

<Estratégia de IDs (ULID/UUID/sequencial), prefixos, unicidade, particionamento por tenant se aplicável.>
