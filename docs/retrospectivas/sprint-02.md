# Retrospectiva — Sprint 2 (F002 publicar + F004 ler por id + persistência SQLite)

> Data: 2026-06-25 · Tarefas: T-S2-01..09 (fundação + 6 review-loops) · Origem: sprint-flow

## Escopo entregue

O blog **publica de verdade e persiste estado**. Backend completo de escrita/leitura unitária sobre SQLite.

- **Fundação (P-02 antes do código):** aceite formal da Sprint 1 (`specs/governance/aceite-po-sprint-01.md`); `003 v1.1.0` (F002/F004, transição aberta sem auth); `005 v1.1.0` (PUT publish, GET por id, `post_not_found`); backlog realinhado (CA órfão de ownership reescrito como republicação idempotente).
- **T-S2-04** Adapter SQLite (`SqlitePostRepository`/`SqliteIdempotencyStore`, `get(id)` na porta, factory parametrizável) — 2 ciclos.
- **T-S2-05** `Post.publish(now)` + `PublishPost` (idempotente por estado) — 1 ciclo.
- **T-S2-06** Endpoint `PUT /v1/posts/{id}/publish` (replay opção B + handler `post_not_found` centralizado) — 2 ciclos.
- **T-S2-07** `GET /v1/posts/{id}` (allowlist, 404 indistinguível) — 2 ciclos.
- **T-S2-08** Auditoria + gap-fill da suíte F002/F004 (5 lacunas, +11 testes) — 1 ciclo.
- **T-S2-09** Gate ratchet (global 99 + 6 pisos por-categoria a 100, CI na raiz) — 2 ciclos.

**Estado final:** 125 testes, 100% cobertura real (gate 99 + categorias 100), 0 ResourceWarnings, determinístico sob `pytest-randomly`. Origem dos ADRs: 0003 (SQLite), 0004 (publicar sem auth), 0005, 0006 — todos aceitos antes da execução.

## ✅ O que funcionou (repetir)

- **ADR antes de código (design-flow → sprint-flow).** Os 4 ADRs aceitos e endurecidos por painel deram esquema preciso ao dev (UPSERT, lock compartilhado, replay opção B, allowlist). Decisões contestáveis (publicar sem auth) já resolvidas com assinatura do PO.
- **review-loop pegou bugs reais que cobertura sozinha não pega.** 5 defeitos genuínos achados na revisão (ver abaixo) — todos teriam passado num "está verde, mergeia".
- **Spec antes do código (P-02).** Bumps de `003`/`005` e realinhamento do backlog feitos como tarefas próprias evitaram divergência spec×código no meio da sprint.
- **Serializar a execução** (um dev por vez no mesmo repo) — sem contaminação de ambiente.
- **`tl-qa` executando de verdade + red-green das mutations.** Cada mutation-âncora foi revalidada pelo revisor (não confiou no relatório do implementador) — pegou inclusive um erro de rótulo M5 e a fragilidade do gate sob `set -e`.

## ⚠️ O que melhorar

- **`ruff format` ≠ `ruff check`.** O dev declarou "ruff OK" tendo rodado só `format`; o `check` acusava I001 (T-S2-07). Custou um ciclo. → lição promovida.
- **Gate criado mas inerte.** O workflow CI nasceu em `backend/.github/workflows/` (ignorado pelo GitHub) e a sentinela anti-glob-vazio era código morto sob `set -e`. Gate que não roda/não morde é falso-verde de processo. → lições promovidas.
- **Divergência DETAIL↔código quando a decisão do dev é a certa.** UPSERT (T-S2-04) e replay opção B (T-S2-06) exigiram reconciliar o DETAIL — o orquestrador alinhou a spec ao código aprovado, mas idealmente o DETAIL já anteciparia.

## 🧠 Aprendizados técnicos (gotchas)

- **`add` de adapter SQL deve ser UPSERT, não `INSERT OR IGNORE`, quando a entidade tem transição de estado** — `INSERT OR IGNORE` descarta o update em silêncio (o fake in-memory passa, o SQL real falha → falso-verde de wiring). A idempotência de criação vem do store write-once + retorno antecipado, não do `add`.
- **Adapters que compartilham conexão SQLite devem compartilhar UM lock.** Lock por-adapter não serializa `with conn:` intercalados na mesma conexão → `OperationalError: cannot commit` intermitente. Resolvido com `SqliteHandle(conn, lock)`.
- **IdempotencyStore compartilhado entre rotas precisa de chave namespaced** (`publish:{idem_key}`); a chave crua do cliente colide cross-rota (mesma key em POST e PUT → 409 espúrio). O discriminador de recurso vai no `payload_hash` (`sha256(post_id)`), o namespace vai na store_key.
- **datetime em SQLite:** gravar ISO-8601 UTC tz-aware e forçar tz na leitura; naive na volta quebra a comparação keyset.
- **bash `set -e` aborta na atribuição `out=$(cmd)` quando `cmd` sai ≠0** — a sentinela/captura depois da atribuição vira código morto. Capturar com `out=$(cmd) || rc=$?` (com `rc=0` declarado antes).
- **GitHub Actions só descobre workflows em `<raiz>/.github/workflows/`** — subpasta = inerte. Usar `defaults.run.working-directory` para apontar o subdiretório.
- **Teste de idempotência com relógio de runtime é frágil por design** (poderia passar vacuamente se dois `now()` coincidirem); injetar T1≠T2 (A3 determinístico substituiu).

## 📐 Plano vs. realidade

- **Estimativa honrada.** O fatiamento do PO (S2 = backend+SQLite) se sustentou; nenhuma tarefa estourou. SQLite antecipado para a S2 (colado em F002) provou-se acertado — a transição persiste de verdade.
- **Custo de ciclos:** 4 das 6 tarefas precisaram de 2 ciclos; nenhuma escalou para especialista (`spec-*`). Os 2º ciclos foram majoritariamente de **robustez de gate/concorrência**, não de lógica de negócio — sinal de que a parte funcional está bem dominada e o rigor está nos detalhes de wiring.
- **Gate subiu de verdade:** 95 → 99 global (medido) + 6 categorias de risco a 100 (P-07), com CI agora wired na raiz.

## 🧯 Dívidas registradas (para `debt-flow`/próximas sprints)

- **`_to_response_dict` é função privada compartilhada por 4 casos de uso** (`create_post`, `publish_post`, `get_post`, `list_published_posts`) via import cross-módulo de símbolo `_privado` — acoplamento frágil. Extrair para `application/serialization.py` (público). Candidato a `debt-flow`.
- **Edição de conteúdo (`PUT /v1/posts/{id}` de title/content)** ficou fora do MVP por decisão do PO — registrar se algum dia entrar.
- **Nota didática F008:** callout obrigatório "sem auth é escolha de contexto local, não padrão de produção" (ADR-0004).

## 🔗 Memórias do agente geradas

- `blog-tutorial-sprint2-estado` — estado pós-Sprint 2 (publica+persiste), baseline de gate (99/100) e escopo da Sprint 3.

## 🎓 Lições promovidas para `docs/lessons/`

- `python.md` — adapter SQL `add`=UPSERT vs INSERT OR IGNORE; lock único por conexão compartilhada; datetime tz-aware em SQLite; namespacing de chave de idempotência entre rotas.
- `process.md` — `ruff check` ≠ `ruff format` (o gate é o `check`).
- `sre.md` — workflow GitHub Actions na raiz do repo (subpasta = inerte); `set -e` + `$(...)` mata sentinela/captura de exit.
