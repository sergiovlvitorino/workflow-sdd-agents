# ADR-0003 — Persistência local: SQLite vs in-memory

**Status:** Aceito _(com refinamentos do painel — ver §8)_ · _(Proposto → Aceito → Substituído por ADR-XXXX | Rejeitado)_
**Data:** 2026-06-25
**Autor:** design-flow (orquestrador-sintetizador)
**Revisores requeridos:** Tech Lead Backend + Tech Lead QA
**Constitution:** v1.0.0
**Relacionado a:** ADR-0001 (stack; "adapter in-memory didático, SQLite trocável") · `specs/006-architecture.md` (porta `PostRepository`) · P-12 (reversibilidade)

---

## 1. Contexto

O MVP da Sprint 1 entregou um `InMemoryPostRepository` por trás da porta `PostRepository`. Ele cumpre seu papel didático, mas **perde todos os dados a cada restart do processo**. Num projeto que o aprendiz roda localmente e usa de verdade (criar um post, fechar, reabrir, ver que continua lá), a volatilidade vira atrito pedagógico: o blog "esquece" tudo.

Precisamos decidir **agora** porque a Sprint 2 (F002 publicar, F004 ler por id) só faz sentido se os dados sobrevivem entre execuções, e porque trocar o mecanismo de persistência é precisamente a demonstração que a arquitetura hexagonal (P-12) promete ensinar.

**Restrições em jogo:** escopo pequeno, roda **localmente**, **sem autenticação**, intuito **educacional**. Nada de banco em servidor, nada de infra de nuvem.

**Forças:**
- Durabilidade entre execuções (o blog deve lembrar).
- Clareza pedagógica: provar na prática que a porta `PostRepository` permite swap sem tocar domínio/casos de uso.
- Zero fricção de setup local (sem subir container/serviço).
- Coerência com ADR-0001, que já sinalizou "SQLite trocável".

## 2. Alternativas consideradas

| Alternativa | Prós | Contras |
|---|---|---|
| **A. SQLite via novo adapter** _(escolhida)_ | Durável entre execuções; arquivo único, zero setup (lib na stdlib do Python); exercita P-12 (novo adapter, domínio/casos de uso intactos); ensina mapeamento porta→SQL sem complexidade de servidor | + uma dependência de driver/ORM (ou SQL cru); precisa de migration/criação de schema; testes ganham uma variante de integração |
| **B. Manter só in-memory** | Zero deps adicionais; o mais simples possível | Não persiste — o blog esquece a cada restart; desperdiça a oportunidade didática central (a porta nunca é trocada de verdade) |
| **C. Persistência em arquivo JSON** | Durável e sem driver SQL | Meio-termo pobre: reinventa concorrência/consistência à mão, ensina um anti-padrão; não escala nem para o exemplo |

## 3. Critérios de decisão

| Critério | Peso | Por quê |
|---|---|---|
| Demonstração da reversibilidade (P-12) | **Alto** | É a lição arquitetural central do projeto |
| Durabilidade local entre execuções | **Alto** | Sem ela o blog não é usável de verdade |
| Fricção de setup local | **Alto** | Roda local; não pode exigir infra |
| Simplicidade / aderência ao escopo pequeno | Médio | Educacional, não produção |

## 4. Decisão

**Escolhida: Alternativa A — adapter SQLite local, mantendo o in-memory para os testes.**

Cria-se um `SqlitePostRepository` (e o `IdempotencyStore` correspondente) que implementa as **mesmas portas** já definidas em `application/ports.py`. O `main.py` (factory) passa a injetar o adapter SQLite por padrão para execução local, e o `InMemoryPostRepository` permanece como adapter de teste — a suíte unit/integration continua rodando em memória, rápida e determinística. O arquivo SQLite vive fora do controle de versão (entra no `.gitignore`).

Inegociável:
- O **domínio e os casos de uso não mudam uma linha** — esse é o ponto da decisão. Se a troca exigir tocar `domain/` ou `application/`, a abstração da porta está vazada e deve ser corrigida antes.
- O schema é criado de forma explícita e versionável (script/migration simples), não "mágica" implícita — coerente com falha explícita (P-11).
- Os testes de integração HTTP continuam exercitando o **wiring de DI de produção** (anti-falso-verde): pelo menos um teste roda contra o adapter real (SQLite em arquivo temporário/`:memory:`), não só contra o fake.

## 5. Consequências

- **Positivas:** o blog persiste entre execuções; a arquitetura hexagonal deixa de ser teoria e vira exercício concreto de swap de adapter; setup local continua trivial (SQLite é arquivo).
- **Negativas / custo assumido:** uma dependência/camada SQL a mais e a necessidade de criar o schema; surge a questão de migrations (mantida mínima no escopo didático).
- **Impacto em specs/código:** novo `infrastructure/sqlite_repository.py` (e store de idempotência); `main.py` ajusta a injeção; `006-architecture.md` passa a citar dois adapters por porta; `.gitignore` ignora o arquivo `.db`.
- **Impacto em testes/gates:** in-memory segue como fake rápido nos unit; ao menos um teste de integração roda contra o adapter SQLite real para cobrir o mapeamento porta→SQL; o ratchet de cobertura (≥95% backend) passa a incluir o novo adapter.

## 6. Gatilhos de revisão

Reabrir esta decisão se:
- O projeto deixar de ser local/didático e precisar de banco em servidor (Postgres) ou múltiplas instâncias concorrentes — ver gatilhos do ADR-0001.
- Surgir necessidade de migrations não-triviais/versionadas (o escopo SQLite mínimo deixa de bastar).

## 7. Aprovações

| Papel | Nome/agente | Data | Veredito |
|---|---|---|---|
| Tech Lead Backend | `tl-python` | 2026-06-25 | Aprovado com ressalvas — incorporadas em §8 (atomicidade P-03, concorrência sqlite3, mapeamento) |
| Tech Lead QA | `tl-qa` | 2026-06-25 | Aprovado com ressalvas — incorporadas em §8 (suíte de contrato de porta, durabilidade em arquivo, wiring de produção, piso de cobertura próprio) |

## 8. Refinamentos do painel de validação (2026-06-25)

Condições **vinculantes** para a implementação (sem elas o aceite não se sustenta):

- **Driver:** fixar `sqlite3` da **stdlib** (sem ORM) — remove a ambiguidade "(ou ORM)" e respeita dependências mínimas (ADR-0001).
- **Atomicidade da idempotência (P-03) — bloqueante:** `add(post)` e `put(idempotency)` são portas separadas chamadas em sequência por `create_post.py`. No SQLite, se a 2ª falhar após a 1ª comitar, o replay recria o post → **viola P-03**. Decisão: chave de idempotência com `UNIQUE` + `INSERT OR IGNORE` (put naturalmente idempotente) **ou** os dois adapters compartilham conexão/transação com commit único. A escolha deve ser explícita no código.
- **Concorrência/thread (P-11):** `sqlite3` proíbe compartilhar conexão entre threads por padrão (Uvicorn pode usar threadpool). Adotar conexão-por-request (ou `check_same_thread=False` + lock) e `PRAGMA journal_mode=WAL`. Comportamento explícito — nada de `ProgrammingError` intermitente (flaky = P1).
- **Mapeamento:** gravar `PostStatus.value`; datetimes ISO-8601 **UTC tz-aware** (ler de volta naive quebra o keyset); comparação keyset via row-value `(published_at, id) < (?, ?)` ou desmembrada `a < ? OR (a = ? AND b < ?)`.
- **Testes (condição de aceite):**
  - **Suíte de contrato de porta parametrizada** rodando os mesmos casos contra `InMemoryPostRepository` **e** `SqlitePostRepository` (mesma sequência de ids, mesmo `count()`, mesmo replay).
  - **Durabilidade entre conexões:** escrever com uma instância, abrir **nova** instância no mesmo arquivo (`tmp_path`, **nunca** `:memory:`) e ler de volta — é a feature-âncora do ADR.
  - **≥1 integração HTTP montando a app com o adapter SQLite** (a factory passa a ser parametrizável) — senão os testes exercitam um wiring que não é mais o de produção (falso-verde estrutural).
  - **Replay idempotente contra o `SqliteIdempotencyStore` real** (formato persistido/serialização exercitado), `count()==1`.
  - **Piso de cobertura próprio do adapter** (categoria adapters/idempotência/keyset), **não diluído** na média global do pacote (`--cov-fail-under` hoje é global).
  - **Mutation-âncora:** `<` → `<=` no WHERE do keyset SQLite duplica a fronteira → teste vermelho.
