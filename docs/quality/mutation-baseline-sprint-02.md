# Quality — Baseline de Mutation Testing — Sprint 02

> Registro do piso de mutation por módulo (T-S2-09). O gate é **ratchet**: o score só sobe (P-07). Rebaixar exige ADR.
> Cobertura mede o que foi executado; mutation revela asserts fracos (qa.md).

**Ferramenta:** mutmut (nightly/sob-demanda — não bloqueia CI da sprint; candidato a gate no Sprint 3)
**Última atualização:** 2026-06-25

## Âncoras de mutation cravadas na Sprint 2 (red-green verificado nos testes)

As âncoras abaixo foram verificadas manualmente (red-green por Edit, revertidas após prova):

| ID | Módulo / Local | Mutação | Teste que fica vermelho |
|----|----------------|---------|------------------------|
| M1 | `application/publish_post.py` — `repo.add` | Remover chamada de persistência após publicar | `test_publish_state_persisted_verified_via_get_exact_published_at` (reler via GET → 404) |
| M2 | `domain/post.py` — `Post.publish` | Não setar `published_at` (deixar `None`) | `test_publish_draft_published_at_exact_value_with_frozen_clock` (published_at == None ≠ T_PUB_RFC3339) |
| M3 | `domain/post.py` — guarda de no-op | Remover guarda; re-setar `published_at` incondicionalmente | `test_republish_with_advanced_clock_published_at_stays_at_t1` (published_at_2 == T2 ≠ T_PUB) |
| M9 | `infrastructure/sqlite_repository.py` — keyset | `<` → `<=` no `WHERE (published_at, id) < (?, ?)` | Suíte de contrato parametrizada `test_post_repository_contract.py[sqlite]` — página duplica a fronteira |

## Baseline por módulo (pré-mutmut formal — baseado nas âncoras manuais)

| Módulo | Cobertura linha+branch | Âncoras cravadas | Piso mutation (estimado) | Ação |
|---|---|---|---|---|
| `domain/post.py` | 100% | M2, M3 | ≥ 80% | Candidato a mutmut no Sprint 3 |
| `application/publish_post.py` | 100% | M1 | ≥ 80% | Candidato a mutmut no Sprint 3 |
| `infrastructure/sqlite_repository.py` | 100% | M9 | ≥ 75% | Candidato a mutmut no Sprint 3 (keyset crítico) |
| `interfaces/posts_router.py` | 100% | — | — | Sprint 3 |
| `interfaces/errors.py` | 100% | — | — | Sprint 3 |

## Mutantes sobreviventes aceitos (com justificativa)

Nenhum formalmente avaliado nesta sprint (mutmut nightly ainda não wired no CI).

| Mutante | Local | Por que é aceitável | Revisão |
|---|---|---|---|

## Como rodar

```bash
cd backend
pip install mutmut
# Focar nos módulos críticos (domínio + adapter + use cases de escrita)
mutmut run --paths-to-mutate src/blog/domain/post.py,src/blog/application/publish_post.py,src/blog/infrastructure/sqlite_repository.py
mutmut results
```

## Histórico

| Data | Evento | Detalhe |
|---|---|---|
| 2026-06-25 | Sprint 2 — baseline criado | Âncoras M1/M2/M3/M9 verificadas manualmente (red-green por Edit). mutmut formal programado para Sprint 3. |
