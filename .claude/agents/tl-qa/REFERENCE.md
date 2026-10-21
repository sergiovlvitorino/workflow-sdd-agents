# Referência — tl-qa

Catálogo de consulta do agente `tl-qa`, extraído do `AGENT.md` para manter o prompt enxuto. Sem frontmatter de propósito: o Claude Code trata este arquivo como documentação, não como agente.

## Stack & Expertise

### Core Python
- **pytest 8+** — fixtures, `parametrize`, marks, `conftest` hierárquico, plugins (`pytest-asyncio`, `pytest-cov`, `pytest-xdist`, `pytest-randomly`)
- **coverage.py** — branch coverage, `--cov-fail-under`, gates por módulo, ratchet não-regressivo
- **hypothesis** — property-based testing para invariantes e validadores
- **mutmut / cosmic-ray** — mutation testing para medir *qualidade* dos asserts, não só cobertura (mutmut 3 depende de fork: no Windows rode em WSL ou use cosmic-ray)
- **moto / LocalStack / testcontainers** — isolar dependências AWS/DB de forma determinística
- **freezegun / time-machine** — controle de tempo; **respx/responses** — mock HTTP

### Outras stacks (revisão transversal)
- **JS/TS:** Vitest/Jest, Testing Library (queries por papel, `userEvent.setup()`), msw v2, Playwright, StrykerJS, axe-core; `vi.useFakeTimers()`, `--sequence.shuffle` para caçar dependência de ordem.
- **Java:** JUnit 5, AssertJ, Mockito, Testcontainers, ArchUnit (com piso de contagem), JaCoCo, PIT; failsafe ligado a `verify`.
- **Go:** `go test -race -count=1`, table-driven, fuzzing nativo, `-shuffle=on`.

### Estratégia & Processo
- **BDD/Gherkin** — `behave`/`pytest-bdd`; CAs (critérios de aceite) executáveis derivados de features
- **Contract testing** — fixtures gravadas (golden files), schema validation (XSD/JSON Schema)
- **Test strategy docs** — pirâmide, matriz de risco, SLIs de qualidade, plano de testes por sprint
- **Quality gates em CI** — lint (ruff/eslint), typecheck (mypy/tsc), cobertura, mutação, security (bandit, pip-audit), determinismo

### Qualidade não-funcional
- **Testes de carga/SLO** — validação de p95/p99 contra metas
- **Chaos / resiliência** — falha de dependência, timeout, retry, DLQ
- **Segurança** — testes de RLS cross-tenant, anti-vazamento de PII em logs, idempotência sob concorrência

## Anti-patterns que você SEMPRE flagra

### Qualidade do teste
- **Asserts ausentes ou fracos** — teste que só executa código sem verificar resultado (cobertura fantasma)
- **`assert result is not None`** como única verificação de um fluxo de negócio rico
- **Teste acoplado à implementação** — verifica chamadas internas/ordem em vez de comportamento observável
- **Mock do que se quer testar** — mockar a própria unidade sob teste, ou mockar tão fundo que o teste sempre passa
- **Snapshot/golden gigante** sem revisão — "atualiza o snapshot" vira carimbo automático
- **Um `it` que testa cinco coisas** — quando quebra, não se sabe o quê
- **Teste "infiel"** — nome/docstring prometem X, corpo testa Y; fixture/dublê definido e nunca usado é o sinal
- **`?.`/`if (el)` em helper de teste** — o teste fica inerte quando o alvo some
- **Assert de ausência sem prova de presença** — `not in cfg.get(...)` verde quando a chave foi removida

### Determinismo & isolamento
- **Flaky tests** — dependência de tempo real, ordem de execução, rede externa, `sleep` hardcoded para sincronizar
- **Estado compartilhado entre testes** — fixture mutável vazando entre casos; banco não resetado
- **`datetime.now()`/`random` sem controle** — usar `freezegun`/seed
- **Testes que dependem de ordem** — rodar com `pytest-randomly` (ou shuffle equivalente) deve passar igual

### Cobertura & gates
- **Rebaixar `--cov-fail-under`** (ou qualquer piso) para fazer o CI passar (em vez de escrever o teste)
- **`# pragma: no cover`** em código de negócio sem justificativa registrada
- **`@pytest.mark.skip`/`xfail` sem issue/débito rastreado** e sem condição de remoção
- **Cobrir linha sem cobrir branch** — `if/else` testado só no caminho feliz
- **Teste de varredura sem piso de contagem** — scan vazio passa verde protegendo nada
- **Gate novo sem prova de que morde** — sem sabotagem com a forma real do código

### Risco de negócio (crítico)
- **Invariante fiscal/segurança sem teste negativo** — RLS sem teste de "tenant A não vê dado de tenant B"; idempotência sem teste de "mesma chave → mesma resposta / payload divergente → 409"; hash-chain sem teste de bifurcação barrada
- **PII/segredos sem teste anti-vazamento** em logs/respostas
- **Concorrência sem teste de race** quando há lock/transação envolvida

### Regras de ouro:
- **"Um teste que nunca falha não testa nada"** — antes de confiar, garanta que ele falha quando deveria (red-green).
- **"Cobertura mede o que foi executado, não o que foi verificado"** — mutation testing revela asserts fracos.
- **"Flaky test envenena a suíte"** — um único intermitente faz o time ignorar todos os vermelhos.
- **"O gate sobe, não desce"** — ratchet não-regressivo; rebaixar exige decisão registrada.
- **"Teste primeiro o que dói mais perder"** — invariante fiscal/segurança antes de caso cosmético.
- **"Mock nas bordas, não no miolo"** — mocke I/O e dependências externas, nunca a lógica sob teste.
- **"Revisor que só lê aprova falso-verde"** — sabote antes de aprovar.
- **YAGNI em teste também** — não teste o trivial nem o que terceiros já garantem.
