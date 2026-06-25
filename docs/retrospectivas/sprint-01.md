# Retrospectiva — Sprint 1 (Blog Tutorial — esqueleto andante)

> Data: 2026-06-24 · Tarefas: F007 (specs-exemplo), F001 (criar post idempotente), F003 (listar paginado keyset)

Sprint 1 do projeto-exemplo didático. Entregou o **esqueleto andante** do backend (FastAPI) provando que o ciclo SDD roda ponta-a-ponta sobre a stack do ADR-0001. Resultado: **37 testes verdes, 100% line + 100% branch, build PEP 517 OK**, sem escalonamento para especialista.

## ✅ O que funcionou (repetir)

- **O review-loop pagou-se logo no primeiro vertical.** A revisão pegou dois defeitos que "11 testes verdes / 97% cobertura" escondiam: (1) um **build quebrado mascarado** (`build-backend` inexistente, contornado pelo `pythonpath` do pytest) e (2) um **falso-verde de estado** em CA-F001-04 (asserva só status, não `count==0`). Nenhum apareceria em revisão estática — o `tl-qa` provou ambos por execução/mutação.
- **Serializar F001→F003 evitou contaminação.** Um único `dev-python` (via `SendMessage`, contexto preservado) montou F001 e reusou tudo em F003 — sem dois agentes escrevendo no mesmo repo (lição de `process.md`).
- **Detalhar F007 antes abriu o caminho.** Ter `005-api-contract` + `ADR-0002` (keyset) fechados antes do código deu ao dev um alvo único; F001/F003 não codificaram às cegas.
- **Mutation-âncoras como critério de aceite real.** O `tl-qa` não aprovou por leitura: re-rodou e confirmou que cada âncora **morde pelo motivo certo** (incl. a nova de estado e a central `<`→`<=` da paginação).

## ⚠️ O que melhorar

- **Os gates nasceram frouxos no scaffold inicial.** `--cov-fail-under=80` (com 97% real), faltou `--cov-branch`, e `pytest-randomly` instalado na máquina mas não pinado. Três buracos de gate num projeto que *ensina* gates. Da próxima vez, o esqueleto deve nascer com o gate no patamar atingido e a toolchain pinada — não deixar para a revisão pegar.
- **Código duplicado já apareceu** (`_to_response_dict` em duas camadas de caso de uso). Marcado como opcional; vigiar para não virar drift de formato.

## 🧠 Aprendizados técnicos (gotchas)

- **Testes verdes não provam que o pacote builda.** Com `pythonpath=["src"]`, o pytest importa o código sem PEP 517 — um `build-backend` inválido passa despercebido. O gate de build (`pip install -e .` / `python -m build`) roda **separado** dos testes.
- **`--cov-branch` é obrigatório no gate quando P-07 exige 100% de branch.** Cobertura line-only (97.65%) escondeu branches descobertos (95.74% real) justamente nas categorias idempotência/falha-explícita.
- **Ratchet nasce no patamar atingido, não num piso redondo.** `fail-under=80` com cobertura real de ~97% deixa apagar ~9 de 11 testes com o CI verde — ratchet teatral.
- **Ferramenta de gate instalada ≠ pinada.** `pytest-randomly` presente na máquina mas fora das deps = gate de determinismo que não roda no CI limpo.
- **Estabilidade keyset exige `<` estrito + teste com inserção entre páginas.** Ordenação total `(published_at DESC, id DESC)`; trocar `<` por `<=` duplica a fronteira (âncora central do ADR-0002).

## 📐 Plano vs. realidade

- **Escopo respeitado.** F007+F001+F003 entregues como planejado; frontend Angular e F005 (observabilidade) deferidos de propósito (API-First antes da UI), conforme aprovação do plano.
- **Estimativas bateram.** F001 (M) precisou de 2 ciclos de review-loop (build + gates); F003 (S) passou em 1. Nenhuma task estourou o teto de 5 iterações nem exigiu `spec-*`.
- **Custo de gate subestimado no detalhamento.** O DETAIL não fixou explicitamente a config de gate do scaffold (cov-branch, fail-under no patamar, randomly pinado) — virou ressalva de review. Próximo DETAIL de scaffold deve trazer a config de gate como entregável.

## 🔗 Memórias do agente geradas

- `blog-tutorial-sprint1-estado` — Sprint 1 entregue backend-only (FastAPI em `backend/`); frontend Angular + F002/F004/F005/F008 pendentes para a próxima sprint, consumindo o contrato `005`.

## 📌 Pendências para a Sprint 2

- Frontend Angular (consumindo `005-api-contract`) + contract test do schema único (ativa o 2º ratchet e a costura cross-stack do ADR-0001).
- F002 (editar/publicar + autorização P-04), F004 (ler por id), F005 (observabilidade RED), F008 (guia da trilha didática).
- Polish opcional herdado: extrair `_to_response_dict` compartilhado; `response_model=PostResponse` no endpoint; enxugar `except Exception` do cursor codec.
