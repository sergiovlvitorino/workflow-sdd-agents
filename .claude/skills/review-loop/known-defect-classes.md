# Classes de defeito conhecidas — review-loop

Lista compartilhada entre projetos, alimentada pelas retrospectivas de cada um. Ao acionar o `review-loop`, leia este arquivo e inclua no prompt do dev e do(s) revisor(es) apenas os itens relevantes à stack/arquivos tocados pela tarefa atual — não é preciso colar a lista inteira.

Cada entrada: **classe do defeito** — como detectar/mutar para pegá-lo — projeto(s) de origem.

## Testes que aprovam falso-verde

- **Assert de chamada/ausência fraco** (ex.: só checa que uma função foi chamada, não com quais argumentos, ou só checa ausência de exceção). Mutar: trocar o argumento real por um errado e confirmar que o teste reprova. — flash-cards
- **`.get(chave, "")` / fallback silencioso mascarando erro real.** Mutar: forçar a chave a faltar e confirmar que o teste denuncia, não que ele passa com o fallback. — flash-cards
- **Fixture referenciada por nome literal (string) em vez de por contrato/schema.** Mutar: renomear o campo na fixture e ver se algum teste acusa. — flash-cards
- **Teardown/cleanup sem teste dedicado** (idempotência, dupla chamada, ordem de desinscrição). Mutar: chamar teardown duas vezes ou fora de ordem. — flash-cards

## Padrão que se repete em unidades irmãs

- Ao achar um defeito numa classe/módulo/repositório, **verificar explicitamente as unidades irmãs na mesma revisão** (não esperar outro ciclo). Casos reais: isolamento de usuário protegido num repositório mas não no repositório irmão; guard de log correto num arquivo de teste mas não replicado no equivalente. — flash-cards

## Config/infra re-diagnosticada

- **Divergência entre configuração declarada e comportamento medido** (ex.: `--cov=app` vs `source=[...]`, retenção de logs, CORS origin). Quando a mesma config é "corrigida" pela 2ª vez com diagnósticos diferentes, parar e fazer teste A/B controlado (trocar só a variável, medir, reverter) em vez de mais uma hipótese lida do código. — flash-cards

## Revalidação/cache

- **`.catch`/tratamento de erro faltando em revalidação assíncrona** (cache, retry, refetch). — flash-cards

## Gates recém-criados (sabotar o próprio gate)

- **Parser do gate ≠ parser do consumidor real** (regex lendo arquivo que o `make`/ferramenta lê com outra gramática; campo `todo` ≠ `pending` no reporter). Sabotar com a sintaxe que o consumidor aceita e o teste ignora. — flash-cards
- **Gate de lint por nome (objeto+propriedade) vaza por cadeia/alias** (`it.concurrent.fails`, `suite.only`, `const t = it`). Sabotar com cadeia, alias exportado, alias local e namespace; restringir por propriedade. — flash-cards
- **Regex de gate testada só com o exemplo do bug** (pega `'pkg'`, deixa `@scope/pkg`, `pkg/sub.js`, `from"x"`). Sabotar com a forma canônica real. — flash-cards
- **Mock de ordem/tempo impossível** (callback disparado numa ordem que o produtor real nunca emite). Checar com integração sem mock; linha "inatingível" na cobertura costuma ser o mesmo ramo. — flash-cards
- **Função agregadora (`validate`/`run_all`) sem uma prova por regra**: testar só os `check_*` isolados e o caminho verde deixa a remoção de uma regra do agregador passar. Sabotar tirando cada regra do agregador; exigir um caso por regra que passe pelo ponto de entrada que o consumidor usa. — flash-cards
- **Isenção/permissão por NOME** (tópico, arquivo, rota): renomear outro item para o nome isento escapa da regra. Sabotar renomeando; exigir unicidade do nome e "casa" fixa do item isento. — flash-cards
- **Teste que declara uma invariante mas checa um proxy** (prefixo de 4 letras para "o falso amigo nunca é a tradução"): metade dos casos reais passa. Sabotar com os casos do domínio, não com o exemplo do teste; checar contra o dado declarado (ex.: o valor já registrado em outro campo). — flash-cards
- **Parser tolerante de arquivo editado por humano** (planilha/Markdown de revisão): linha solta, quebra de linha num campo ou bloco extra é ignorada e trunca/perde a edição com exit 0. Sabotar com Enter acidental, bloco colado de outro arquivo e reexportação parcial; exigir fail-closed com o alvo byte-idêntico. — flash-cards
- **`parametrize` derivado da constante sob teste** (lista de casos = a constante que o código usa): remover um item da constante remove o caso junto. Mutar removendo um item da constante; exigir lista literal independente comparada por igualdade. — flash-cards
- **Classificador de formas sobre gramática aberta** (shell de receita, CSS, config): cada ciclo fecha as formas vistas e a próxima escapa. Sabotar com aninhamento, pipe, `;` e bloco condicional; preferir congelar por igualdade. — flash-cards
- **Arquivo sombra com precedência** (`GNUmakefile`/`makefile`, `.coveragerc`/`setup.cfg`, `vitest.config.mts`): troca o gate sem tocar no arquivo vigiado. Sabotar criando cada nome da lista de resolução da ferramenta. — flash-cards

## Testar o testador

- **Helper de teste centralizado (a11y, contrato, fixture) sem autoteste**: apagar a asserção central do helper deixa a suíte verde. Sabotar o próprio helper (remover a asserção, desligar filtros/checkers) e exigir que um autoteste reprove. — flash-cards
- **Guarda de estado novo sem teste** (`if (!session) return` num estado que passou a ser estável e interativo). Sabotar removendo a guarda e disparar todos os atalhos/comandos forjados nesse estado. — flash-cards

---

## Como este arquivo cresce

Ao final de cada sprint/retro, se uma classe de defeito nova (não coberta acima) custou ciclo(s) de review, adicione uma entrada curta aqui com o projeto de origem. Não edite o `SKILL.md` da skill para isso — ele deve permanecer estável.
