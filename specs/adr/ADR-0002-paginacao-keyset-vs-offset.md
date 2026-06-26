# ADR-0002 — Paginação de `GET /v1/posts`: keyset/cursor vs offset

**Status:** Aceito · _(Proposto → Aceito → Substituído por ADR-XXXX | Rejeitado)_
**Data:** 2026-06-24
**Autor:** `tl-python` (sprint-flow, Sprint 1)
**Revisores requeridos:** Tech Lead Backend + Tech Lead QA
**Constitution:** v1.0.0
**Relacionado a:** F003 (listar posts publicados com paginação) · `CA-F003-01`, `CA-F003-03` · `specs/005-api-contract.md` (`GET /v1/posts`) · `CA-F007-02` (este ADR satisfaz a exigência de "pelo menos um ADR documenta uma decisão do blog")

---

## 1. Contexto

`GET /v1/posts` (F003) lista posts publicados de forma paginada. O CA-F003-03 exige que a **página seguinte seja estável**: ao avançar via cursor, o leitor recebe os itens seguintes **sem repetir** os já vistos. Como o blog tem escrita concorrente (autores publicam posts enquanto leitores paginam), a paginação tem de se manter correta mesmo com inserções entre uma página e a próxima.

Precisamos decidir **agora** o mecanismo de paginação porque ele define o **shape do contrato** (`Page<T>` com `next_cursor` vs `total`/`page`/`offset`) em `005-api-contract.md` — a fonte única que o frontend Angular vai consumir depois. Trocar isso após o front ser escrito é quebra de contrato (major bump, P-08). É também uma decisão didática: o exemplo deve ensinar o padrão correto desde o dia 1.

**Forças em jogo:**
- Correção sob escrita concorrente (CA-F003-03).
- Clareza pedagógica (o objetivo do blog é ensinar; ver ADR-0001).
- Coerência com `docs/lessons/python.md` ("paginação por cursor keyset, não offset").
- Extensibilidade do contrato (P-06): poder evoluir o critério de ordenação sem quebrar consumidores.

## 2. Alternativas consideradas

| Alternativa | Prós | Contras |
|---|---|---|
| **A. Keyset/cursor** _(escolhida)_ | Estável sob escrita concorrente — `WHERE (published_at, id) < (:last, :last_id)` não pula nem duplica linhas quando posts são inseridos entre páginas (satisfaz CA-F003-03 por construção); cursor opaco esconde o critério de ordenação (P-06: trocar o critério não muda o shape do contrato); padrão recomendado em `docs/lessons/python.md`; ensina o padrão "certo" como referência canônica | Não permite "pular para a página N" (sem índice numérico); cursor precisa ser codificado/decodificado e validado (input externo → P-11); sem `total` barato (exige `COUNT` separado, omitido no MVP) |
| **B. Offset/limit** | Trivial de implementar e de entender à primeira vista; permite `?page=3`; `total` natural | `OFFSET` **pula ou duplica** linhas sob inserção concorrente (`docs/lessons/python.md`) → **viola CA-F003-03**; degrada em listas grandes (o banco varre e descarta as N primeiras linhas); ensinaria o anti-padrão como exemplo canônico |
| **C. Page-number puro (`?page=N`)** | Familiar para UIs de blog | Mesmos defeitos do offset (é açúcar sintático sobre offset); acopla o contrato a um modelo numérico instável |

## 3. Critérios de decisão

| Critério | Peso | Por quê |
|---|---|---|
| Estabilidade sob escrita concorrente (CA-F003-03) | **Alto** | É um critério de aceite explícito e o ponto da feature |
| Clareza pedagógica / exemplo canônico | **Alto** | O blog existe para ensinar o padrão correto (ADR-0001) |
| Coerência com lições (`python.md`) | **Alto** | O base já destilou esta lição; contrariá-la sem motivo é incoerente |
| Extensibilidade do contrato (P-06) | Médio | Cursor opaco protege consumidores de mudança de ordenação |
| Conveniência de "pular para página N" | **Baixo** | Um blog didático não precisa de navegação por número de página |

## 4. Decisão

**Escolhida: Alternativa A — paginação keyset por cursor opaco.**

A ordenação é determinística por `(published_at DESC, id DESC)` — `id` desempata para garantir ordem total mesmo com `published_at` iguais. O **cursor é opaco**: o servidor codifica o par `(published_at, id)` do último item da página (base64url de um JSON pequeno) e o devolve em `next_cursor`; o cliente o ecoa em `?cursor=`. O cliente trata o cursor como **token cego** — nunca o constrói nem o interpreta. Isso satisfaz CA-F003-03 por construção (a query keyset não pula/duplica sob inserção) e mantém o critério de ordenação invisível ao contrato (P-06).

Inegociável:
- Cursor é **input externo** → decodificá-lo e validá-lo; cursor malformado/corrompido falha explicitamente com `400 invalid_cursor` (P-11), nunca silenciosamente "volta ao começo".
- `next_cursor` é `null` na última página (sem mais itens) — sinal único e inequívoco de fim.
- `limit` tem default e teto (ver `005`), para o cliente não pedir página ilimitada.

## 5. Consequências

- **Positivas:** CA-F003-03 satisfeito por construção; contrato `Page<T>` estável e extensível; o exemplo ensina o padrão recomendado; query keyset performa bem com índice em `(published_at, id)`.
- **Negativas / custo assumido:** sem "pular para página N" e sem `total` barato (ambos fora do escopo didático do MVP — se um dia forem necessários, novo ADR); o cursor exige codec + validação (uma peça a mais, mas é justamente onde P-11 se materializa em sala).
- **Impacto em specs/código:** `005-api-contract.md` define `Page<T>` com `items` + `next_cursor` (sem `total`/`page`); o adapter in-memory didático (ADR-0001) implementa o keyset ordenando a lista e cortando em `(published_at, id)`; `006-architecture.md` referencia este ADR.
- **Impacto em testes/gates:** teste de estabilidade (CA-F003-03) deve **inserir um post publicado entre a 1ª página e a 2ª** e provar que nenhum item se repete nem some — não basta paginar uma lista estática (ver `docs/lessons/qa.md`, "exercite a fronteira"). Teste de cursor inválido → `400` (branch de erro coberto). Mutation-âncora: trocar `<` por `<=` na comparação keyset deve duplicar a linha de fronteira → teste vermelho.

## 6. Gatilhos de revisão

Reabrir esta decisão se:
- O produto passar a exigir navegação por número de página ou contagem total exibida (ex.: UI com "página 3 de 12").
- A ordenação deixar de ter uma chave total estável (ex.: ordenar por campo mutável e não-único sem desempate por id).
- O exemplo deixar de ser didático e ganhar requisito de escala/produção (ver gatilhos de ADR-0001).

## 7. Aprovações

| Papel | Nome/agente | Data | Veredito |
|---|---|---|---|
| Tech Lead Backend | `tl-python` | 2026-06-24 | Aprovado — keyset/cursor opaco, ordenação `(published_at DESC, id DESC)` |
| Tech Lead QA | `tl-qa` | 2026-06-24 | Aprovado — exige teste de estabilidade com inserção concorrente + cursor inválido `400` + mutation-âncora `<`/`<=` |
