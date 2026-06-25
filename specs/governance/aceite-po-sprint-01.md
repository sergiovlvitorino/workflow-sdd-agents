# ACEITE-PO — Sprint 1 (Blog Tutorial — esqueleto andante)

**Data:** 2026-06-25
**PO responsável:** `po`
**Escopo avaliado:** Sprint 1 — F007 (specs-exemplo), F001 (criar post idempotente), F003 (listar publicados paginado)
**Veredito:** ⬜ Aceito · ✅ Aceito com ressalvas · ⬜ Rejeitado

---

## 1. O que foi entregue

| Item | RF/Feature | Status | Evidência (PR/teste/demo) |
|---|---|---|---|
| Specs-exemplo 001–007 preenchidas e rastreáveis | F007 | ✅ Entregue | `specs/001`–`007`; RFs com CA rastreável (P-02) |
| ADR de decisão técnica do blog | F007 (CA-F007-02) | ✅ Entregue | `specs/adr/ADR-0002` (paginação keyset) |
| Criar post idempotente (`POST /v1/posts`) | F001 / RF-001..004 | ✅ Entregue (backend) | `backend/src/blog/application/create_post.py`; testes unit + HTTP |
| Listar publicados paginado por cursor (`GET /v1/posts`) | F003 / RF-005..007 | ✅ Entregue (backend) | `backend/src/blog/application/list_published_posts.py`; testes HTTP |
| Esqueleto andante backend FastAPI sobre a stack do ADR-0001 | F007/F001/F003 | ✅ Entregue | 37 testes verdes, 100% line + 100% branch, build PEP 517 OK |

## 2. Critérios de aceitação verificados

| CA | Verificado? | Como |
|---|---|---|
| CA-F001-01 (cria post → 201, status draft) | ✅ | Teste HTTP de integração `test_create_post_http` |
| CA-F001-02 (idempotência: mesma `Idempotency-Key` → mesmo id, sem duplicar) | ✅ | Teste unit do caso de uso + HTTP |
| CA-F001-03 (payload inválido → 422 `validation_error`) | ✅ | Teste HTTP de integração |
| CA-F001-04 (sem `Idempotency-Key` → 400 `idempotency_key_required`) | ✅ | Teste HTTP + âncora de estado (`count==0`, não só status — defeito de falso-verde corrigido na revisão) |
| CA-F003-01 (lista paginada, ≤ limit + next_cursor) | ✅ | Teste HTTP `test_list_posts_http` |
| CA-F003-02 (rascunho não vaza na listagem — P-04 allowlist) | ✅ | Teste negativo de visibilidade |
| CA-F003-03 (página seguinte estável via cursor, sem repetir/omitir) | ✅ | Teste com inserção entre páginas; mutation-âncora `<`→`<=` (ADR-0002) |

> Cobertura inversa: todo CA da Sprint 1 tem teste automatizado verde. Sem CA órfão no escopo entregue.

## 3. DoD (P-13)

- [x] Spec aprovada e versionada (001–007 + ADR-0002)
- [x] CAs automatizados e verdes (37 testes; 100% line + branch)
- [ ] Métricas RED instrumentadas — **diferido para F005 (Sprint 3)**; fora do escopo da Sprint 1 por decisão de plano (API-First antes de observabilidade)
- [ ] Documentação pública publicada — **diferido para F008 (guia da trilha, Sprint 3)**
- [ ] Runbook escrito — N/A nesta sprint (sem operação em produção)
- [ ] Revisão de segurança — N/A (sem segredo/PII; sem auth por decisão do ADR-0004, projeto local)

## 4. Ressalvas e follow-ups

| Ressalva | Severidade | Ação | Prazo/Tarefa |
|---|---|---|---|
| Entrega **backend-only**; frontend Angular não iniciado | Baixa (planejado) | Frontend consome contrato `005` | Sprint 3 (T-S3-01..03) |
| F002 (publicar) e F004 (ler por id) diferidos | Baixa (planejado) | Implementar transição aberta (ADR-0004) | Sprint 2 (T-S2-05..07) |
| Gates nasceram frouxos no scaffold (`fail-under=80` com ~97% real, faltou `--cov-branch`, `pytest-randomly` não pinado) | Média | Subir ratchet ao patamar atingido + pinar toolchain | Sprint 2 (T-S2-09) — corrigido na revisão da S1; vigiar regressão |
| Código duplicado `_to_response_dict` em duas camadas | Baixa | Extrair helper compartilhado (polish) | Backlog de polish (T-S3, opcional) |
| Posts publicados só existem via seed didático (sem transição `draft→published`) | Baixa (conhecida) | Resolvida por F002 | Sprint 2 |

## 5. Decisão e assinatura

**Aceito com ressalvas.** A Sprint 1 entregou o esqueleto andante do backend provando o ciclo SDD ponta-a-ponta sobre a stack do ADR-0001: os 7 CAs de F001/F003 estão automatizados e verdes, com 100% de cobertura line+branch e build PEP 517 válido. O valor pedagógico do núcleo foi atingido — o review-loop pegou dois defeitos reais (build mascarado e falso-verde de estado) que cobertura sozinha escondia, validando o processo.

As ressalvas são todas **planejadas e de baixa severidade**: a natureza backend-only e o diferimento de F002/F004/F005/F008 foram aprovados no plano (API-First antes da UI). A única ressalva de processo a vigiar é o aperto dos gates (ratchet no patamar real + toolchain pinada), endereçada como T-S2-09. Nada bloqueia o fechamento da sprint nem a abertura da Sprint 2.

Assinado: **`po`** — 2026-06-25
