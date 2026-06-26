# 005 — API Contract

**Status:** Rascunho
**Versão:** 0.1.0
**Data:** AAAA-MM-DD
**Responsável:** PO + TL
**Constitution:** v1.0.0

> Preencha e mova para `specs/005-api-contract.md`. Contrato é entregável **antes** da implementação (P-01). Idempotência obrigatória em escrita (P-03); versionamento por prefixo (P-08).

## 1. Convenções gerais

- **Base URL / versão:** `/v1`
- **Autenticação:** <esquema, scopes>
- **Idempotência:** rotas de escrita exigem header `Idempotency-Key`; replay retorna `Idempotent-Replayed: true`; conflito de payload → `409`.
- **Paginação:** <keyset/cursor — ver `docs/lessons/python.md`>
- **Formato de erro:** corpo tipado `{ "error": "code", "message": "...", "details": [...] }`.

## 2. Endpoints

### `POST /v1/<recurso>`

| | |
|---|---|
| **Descrição** | <…> |
| **Auth/scope** | <…> |
| **Idempotente** | sim (`Idempotency-Key`) |

**Request**
```json
{ }
```

**Respostas**
| Código | Quando | Corpo |
|---|---|---|
| 201 | criado | `{...}` |
| 202 | aceito (assíncrono) | `{ "id": "...", "status": "pending" }` |
| 409 | conflito de idempotência | erro tipado |
| 422 | validação | erro tipado com `details` |

## 3. Eventos / webhooks

| Evento | Trigger | Payload | Entrega |
|---|---|---|---|
| | | | at-least-once, assinado |

## 4. Versionamento e depreciação

<Política de breaking change, janela de coexistência (P-08), aviso de depreciação.>
