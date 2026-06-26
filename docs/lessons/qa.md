# Playbook QA — testes, gates e anti-falso-verde

> Lições generalizáveis. Confronte com o código atual antes de aplicar (ver [README](README.md)).

## Anti-falso-verde (a suíte está verde, mas não prova nada)

Origem: 2026-06. Classe de defeito recorrente — teste passa sem exercer a invariante.

- **Teste sob superuser mascara RLS.** Multi-tenant testado com role de superusuário/owner não exercita Row-Level Security — passa mesmo com a policy quebrada. Rode os testes de isolamento **sob a role de aplicação**, e prove com *mutation* (quebre a policy de propósito → o teste tem que falhar).
- **Guarda write-only.** Um controle que só restringe escrita, testado só com leitura, passa sem provar nada. Teste o caminho que o guard realmente protege.
- **Rota nova sem teste HTTP real.** Testar o handler/serviço por baixo não cobre middleware, auth, serialização. Toda rota nova precisa de um teste que bate no endpoint de verdade.
- **Marker vs allowlist.** Filtrar por status com "marcador" (404 no não-encontrado) ≠ filtrar por allowlist (200 com lista filtrada). Asserte o comportamento certo dos dois — confundir mascara vazamento de dados entre estados.
- **PII por valor, não por referência.** Asserte o **valor** redatado/mascarado, não que "um campo existe".
- **ORM drift.** O modelo ORM divergir do schema real do banco passa em teste com SQLite/mock e quebra em produção. Teste contra o engine real quando a invariante é de schema.
- **Asserção sobre o artefato real.** Ex.: validar o PDF/bytes que o endpoint devolve (descomprimir e inspecionar), não um mock do gerador.
- **Assertar o STATUS HTTP / caminho-feliz não pega bug de ESTADO.** Um teste que só confere o código de retorno (`status==422`) é raso — o bug mora no efeito colateral persistido (o slot de idempotência ficou no estado certo? a guarda foi gravada? o contador não duplicou?). Asserte o estado/efeito, não só a resposta. E **todo branch de erro/edge-case precisa de ≥1 teste** — branch sem teste é onde a assimetria nasce (ex.: um caminho faz `rollback` e o gêmeo faz `commit`, descartando a guarda de idempotência da mesma transação). Ao mudar O QUE é cacheado/persistido, teste também quem CONSOME (o caminho de replay/leitura), não só quem escreve.
- **Fake que espelha o CONTRATO mas não o CAMINHO esconde wiring não-testado.** Um dublê que guarda um campo numa chave conveniente satisfaz a abstração, mas se a lógica de produção depende do **formato persistido** (JSONB/coluna/serialização) e só o fake é exercitado, esse caminho nunca roda sob teste — passa verde até um refactor quebrar o formato em produção. Quando a correção depende de como o dado é gravado/lido, exija ≥1 teste sobre o **store/recurso REAL** + mutation-proof que altere a chave/formato → vermelho. (Família "execução tem de cobrir o wiring de produção, não um dublê".)

## Execução é o gate (revisão estática não basta)

Origem: 2026-06 (lição B1/T-TECH-CHAIN-02).

- **Rodar os testes de verdade é obrigatório antes de declarar verde.** Ler o código e "parecer certo" não conta.
- **A execução tem que cobrir o wiring de DI de produção.** Um teste que injeta os colaboradores à mão não pega o container de produção mal-ligado. Exercite a cadeia real de injeção.
- **Skip alto = integração não rodou.** Uma suíte com muitos `skip` (faltou DB, broker, credencial) está dando falso-verde de cobertura. Confirme que os testes **rodaram**, não só que "passaram".
- **`-k feature` não pega regressão transversal.** Rodar só os testes da feature nova ignora o que ela quebrou em outro lugar. Antes de declarar pronto, rode a suíte completa / o espelho de CI local inteiro.

## Anti-flaky (determinismo)

- **Teste a causa, não o sintoma.** Asserte sobre `call_count` do engine, o pico de concorrência, o heartbeat — não sobre um efeito colateral observável com timing. Sintoma → flaky; causa → determinístico.
- **`now()` dentro do parser/lógica = timestamp falso e teste frágil.** Injete o relógio; congele o tempo no teste.
- **Validação por ligação** (assert que A causou B via vínculo explícito) em vez de "esperar e checar".
- **Flaky test é P1.** Um teste não-determinístico destrói a confiança na suíte inteira. Não convive — conserte ou quarentena com prazo.

## Quality gates

- **Ratchet:** o piso de cobertura só sobe, nunca desce sem ADR. Prove que o gate **morde**: derrube a cobertura de propósito → o gate tem que falhar.
- **Floor vs target:** distinga o piso bloqueante da meta aspiracional.
- **Cobertura útil > cobertura burocrática.** 85% com asserts fortes vale mais que 100% com asserts fracos. Teste comportamento, não implementação.
- **Regressão nasce vermelha:** todo bug corrigido começa por um teste que falha **antes** do fix e passa depois — é a Definition of Done do fix.
- **Dívida com gate temporal:** marque a invariante ainda-não-resolvida com `xfail-strict` (ou equivalente) — vira gate que avisa quando alguém "resolver sem querer" e documenta o débito.

## Mutação-âncora — o teste morde pelo motivo certo?

A prova de que um teste vale é red-green por mutação: **reverter o fix de produção tem que deixá-lo vermelho.** Mas a mutação pode ser morta por acidente — daí vem a maior família de falso-verde:

- **A mutação tem de atacar a invariante que o teste ALEGA proteger, não uma vizinha.** Um CA pode estar verde por comparar contra um placeholder em vez do valor real (passa pelo motivo errado). A mutação adjacente dá falso conforto; só a que ataca a invariante real revela o falso-verde de 2ª ordem.
- **Guard adjacente mata a mutação.** Se o input do teste negativo é malformado, um guard de validação (400) dispara **antes** do mecanismo que você quer provar — remover o gate alvo nunca é alcançado, e o assert crítico (`emit.call_count==0`) fica inerte. Use input **válido o suficiente** para que, removido o gate, o fluxo ALCANCE o mecanismo.
- **Fake que retorna `None` curto-circuita o guard.** `if existing is not None and existing.status in S:` — com o fake devolvendo `None`, mutar `S` não muda nada (âncora inalcançável). O dublê tem de retornar o objeto **visível no estado** que a mutação manipula.
- **Mesma correção em N caminhos → a mutação tem de morder em CADA um** (N testes red-green). Provar num representante e declarar "mutation-proof" deixa os outros N-1 como cobertura-fantasma.
- **Teste "infiel" (nome/docstring prometem X, corpo testa Y) é falso-verde.** Sinal de alerta: *dead code de teste* — uma fixture/dublê definido e nunca instanciado é indício de que o teste foi trocado por um mais fácil. Nome + docstring + corpo têm de casar.
- **Janela/cutoff/período → exercite a FRONTEIRA fora da janela.** Off-by-one só aparece com o relógio FORA do período (run no mês seguinte, evento no dia da virada); todo teste com data fixa dentro do período mascara.
- **Lote homogêneo → asserte o ABSOLUTO antes do relativo.** "Sem gap na numeração" sobre `n_authorized` (sem `assert n_authorized == 200`) é vacuamente verdadeiro mesmo se a corrupção derrubou 199 itens. Fixe o resultado absoluto esperado antes das invariantes relativas.
- **Concorrência se prova no recurso REAL, não num dublê.** Um `asyncio.Lock` num fake prova a lógica do caller, não que o `UPDATE … WHERE … RETURNING` serializa sob 2 conexões. Use 2 conexões reais sob role app + barreira determinística (`asyncio.Event`, nunca `sleep`), com mutação no SQL.
- **Mudança de infra-de-teste/tooling NÃO é isenta de mutation-proof.** Teste placebo (o corpo do teste chama o mecanismo em vez do handler de produção; spy preenchido sem assert; override do próprio alvo em `dependency_overrides`) fica verde quando você reverte a mudança de produção. Exercite o caminho de produção real.
- **Patchar uma dependência de framework de DI com `side_effect`/`MagicMock` corrompe a assinatura e mata a âncora (2026-06, FastAPI).** `patch("mod.get_dep", side_effect=Boom)` vira um `MagicMock` de assinatura `(*args, **kwargs)`; frameworks que introspectam a assinatura da dependência (FastAPI resolvendo `Depends`) passam a tratar `args`/`kwargs` como parâmetros obrigatórios → respondem **422/400 ANTES de invocar a dep** → o `side_effect` nunca dispara e a âncora "I/O não-mockado explode" fica vacuamente verde no mutante. Para provar "a dep NÃO foi chamada", use `dependency_overrides[get_dep] = _spy` com um spy de **assinatura real** (`def _spy(): ...` fechando sobre um flag) + `assert not spy_called`, independente de status HTTP; e fortaleça `assert status != 500` para o status MAPEADO esperado (prova que a request alcançou o handler). Vale para qualquer fixture que mocke bordas de I/O de um guard de rota (`dependencies=[Depends(...)]`): mocke TODAS as bordas, e aceite o fix de isolamento só rodando o arquivo ISOLADO com a dependência real PARADA.

## Como construir um gate de CI que morde

- **Nunca `assert errors > 0` como prova de gate** — é assert-de-existência, passa com gate teatral. Prove com harness red-green: planta a violação **na forma textual real** do código e exige `exit != 0`; o estado limpo dá `exit 0`.
- **Gate não-wired é inerte.** Só conta quando aparece RODANDO no pipeline (CI local + CI remoto). "Instruir" o wiring em vez de aplicar = gate que não existe.
- **Mire o BUG, não o PADRÃO.** Um gate que flagra todo uso de uma construção legítima (e exige allowlist enorme) é 97% cerimônia. **Allowlist grande no dia 1 é smell** — estreite até ela ser mínima e honesta. Escape inline exige RAZÃO escrita, não supressão pelada.
- **O gate tem de morder a FORMA REAL do código.** Se a primitiva vive como SQL em string (`text("...set_config...")`), um scanner AST de `ast.Call` é inerte — a varredura textual é a autoritativa; AST/tokenize só descartam falso-positivo em docstring/comentário, e **col-aware** (truncar na coluna do token de comentário). Prove "que morde" reintroduzindo a forma real, não uma sintética que não ocorre.
- **Sentinela `>0` mascara truncamento.** "Varreu N rotas > 0" passa varrendo 3 de 31. Use piso proporcional (≥N de M), e toda exclusão justificada **e cruzada** com outra prova, logada — silêncio lê como "cobriu tudo".
- **Rótulo de CA em Gherkin ≠ verdade.** Confira título↔CA contra o spec, não contra o rótulo que o dev escreveu — um cenário rotulado com o CA errado deixa o CA real sem cobertura e o gate "100% CAs" verde.

## O gate do scaffold nasce no patamar, não num piso redondo

Origem: 2026-06 (Sprint 1 blog-tutorial). Um esqueleto inicial com gates frouxos é falso-verde estrutural — a suíte "passa" mas o gate não morde.

- **Testes verdes não provam que o pacote builda.** Com `pythonpath=["src"]` (ou `src`-layout sem instalação), o runner importa o código **sem** PEP 517 — um `build-backend` inválido/inexistente passa despercebido. O gate de build (`pip install -e .` / `python -m build`) é **separado** do gate de teste; rode os dois.
- **`--cov-branch` é obrigatório quando o piso exige branch.** Cobertura line-only mascara branches descobertos exatamente nas categorias que P-07 marca como 100% de branch (idempotência, falha explícita). Line 97% pode esconder branch 95%. Sem `--cov-branch` no gate, o CI **nunca mede** o que a spec exige.
- **Ratchet nasce no patamar ATINGIDO, com folga mínima — não num número redondo.** `--cov-fail-under=80` com cobertura real de ~97% deixa apagar a maioria dos testes com o CI verde. O primeiro PR fixa o piso no nível real (ex.: 95), senão o ratchet "só sobe" é teatro desde o dia 1.
- **Ferramenta de gate instalada na máquina ≠ pinada nas deps.** `pytest-randomly` (ou qualquer plugin que É o gate de determinismo/ordem) presente localmente mas fora do `pyproject` = gate que não roda no CI limpo. O gate só existe se a toolchain que o executa está pinada no projeto (ver `process.md`: o juiz é o comando do CI).

## Gate de contrato cross-stack (codegen de tipos / frontend)

Origem: 2026-06 (Sprint 3 blog-tutorial). Quando o front consome tipos gerados do contrato do back.

- **Codegen e gate de drift DEVEM ler o app vivo, não um snapshot à mão.** Um JSON de contrato mantido manualmente (porque o `/openapi.json` está incompleto) é 2º source-of-truth: o `git diff --exit-code` do tipo gerado só pega edição do snapshot, **nunca o drift real do backend** → gate teatro. A fonte tem de ser o `app.openapi()` vivo (via dump determinístico `sort_keys=True` + LF). Prove que morde plantando um campo no Pydantic do back → o tipo gerado muda → diff vermelho. Se não fica vermelho, a cadeia `spec ↔ OpenAPI ↔ TS` tem um elo à mão no meio.
- **Vitest/esbuild (e a maioria dos runners JS) NÃO typecheca** — a suíte fica **verde com erros de tipo**. Fixture que declara campo inexistente no tipo gerado (ex.: `total` num contrato keyset) ou omite campo obrigatório passa, porque o transpile ignora os tipos. Wire `tsc --noEmit -p tsconfig.spec.json` (e do app) como **gate separado** no CI/pre-commit; prove red-green reintroduzindo a fixture infiel → `tsc` exit≠0. O gate de codegen cobre o arquivo *gerado*, não o *uso* dele nos specs.
- **Contract test tem de validar payload REAL contra o schema, não fixture-à-mão contra si mesma.** Capture a resposta do `TestClient` do back → valide com um validador de schema (Ajv) contra o OpenAPI/contrato. Uma fixture tipada pelo mesmo tipo que ela "testa" é tautológica (passa pelo motivo errado); a docstring que promete "valida o contrato" enquanto faz isso é teste infiel.
- **Cobertura de frontend precisa de piso POR-ARQUIVO, não só global.** A média global esconde a lógica de negócio fraca (ex.: o store a 78% branch escondido em 91% global). Use `coverage.thresholds` do Vitest com glob por arquivo para os módulos de negócio — espelha o gate por-categoria do backend (anti-diluição). Prove que o piso por-arquivo reprova independente do global.

## Armadilhas de medição de teste

- **Métrica Prometheus/global → meça DELTA, não absoluto** (registry global é estado compartilhado → flaky). Capture o valor antes/depois ou patche o counter.
- **Cobertura async (asyncpg/greenlet) exige `concurrency=["greenlet"]`** no coverage — senão subestima e o gate reprova por artefato.
- **`unittest.mock.patch` dentro de `asyncio.gather` envenena globais** (não é concurrency-safe; corrotinas interleaved restauram um Mock como "original"). Aplique patches UMA vez FORA do gather, ou monte o objeto por wiring direto por worker.

## Checklists obrigatórios por tipo de mudança

- **Rota com require_tenant / autorização** → precisa de teste explícito de isolamento cross-tenant.
- **Adapter/port novo** → precisa de fixtures golden gravadas (≥10, capturadas **antes** de qualquer assinatura/efeito não-determinístico).
- **Bug corrigido** → teste de regressão (vermelho→verde).
- **Contrato consumido por use case (campo novo obrigatório)** → varra TODOS os fixtures que mockam os repos envolvidos (um `AsyncMock(spec=Repo)` sem o método novo devolve MagicMock → 500 em runtime) e rode a suíte COMPLETA (BDD/HTTP inclusive) — o `-k <feature>` não pega.
- **Testes de RLS/privilégio** → `pytest.fail` (NÃO `skip`) quando a role app/`DATABASE_URL_APP` está ausente em CI, senão o falso-verde reabre em silêncio.
