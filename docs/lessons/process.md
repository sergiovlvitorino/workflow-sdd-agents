# Playbook Processo — orquestração, auditoria, higiene

> Lições generalizáveis. Confronte com o código atual antes de aplicar (ver [README](README.md)).

## Auditoria de specs/docs (anti-falso-positivo)

- **Documento de tarefa fica no presente mesmo depois de entregue.** Um spec/DETAIL descreve o problema no tempo presente e **não é re-carimbado** quando a tarefa termina — o status real vive no índice (TASKS-INDEX), não no corpo do DETAIL. Antes de declarar um risco *aberto* a partir de um spec, **cruze DETAIL × índice × código atual**. Ler só o DETAIL gera falso-positivo de auditoria ("isto está quebrado" quando já foi corrigido).

## Auditoria como mecanismo (não burocracia)

- **Uma task de "verificar se está feito" é o que acha o gap escondido.** O catálogo de dívida envelhece — uma entrada pode estar STALE (já entregue 2 sprints antes) e mesmo assim a varredura exigida pela task encontra buracos **não-catalogados** (ex.: dois repos sem cobertura mutation-proof, um deles um falso-verde autoconfesso "valida que não lança exceção"). Não trate verificação como cerimônia: é o que converte "achei que estava coberto" em "provei que está, ou achei o buraco". O critério da varredura é estrutural ("o código tem a forma de risco X?"), não "tem o helper Y?".
- **Ao abrir uma sprint de dívida, os TLs auditam o HEAD ANTES de o PO fechar o escopo** — senão dimensionam trabalho que já existe (catálogo stale) ou subdimensionam o resíduo real.

## Refinamento confronta CA × código ANTES de implementar

Origem: 2026-06.

- **No detalhamento (DETAIL), o QA/TL confronta cada critério de aceite contra a capacidade REAL do código — não só contra a intenção.** Um CA pode descrever comportamento que a base atual não consegue produzir (ex.: "limpa o campo de erro" quando o método de update ignora `None`; "responde 409 na corrida" quando ele engole a exceção de condição). CAs assim são **não-implementáveis como escritos** e, se não pegos no refino, viram falso-verde no review (o teste descreve algo que o código nunca faz). O produto desse confronto é uma lista explícita de **enablers técnicos** (mudanças de base pré-requisito) que abrem a sprint, em vez de surpresas no meio dela.
- **Sintoma de que faltou esse confronto:** o roadmap/estimativa diz "trivial, zero reescrita" mas a implementação descobre 2–3 mudanças estruturais inevitáveis. Estimativa de discovery-lite ≠ esforço real; o refino com olhos no código é quem corrige.

## Paralelismo de agentes

- **Não paralelize agentes que escrevem no mesmo repo + banco.** Dois agentes (dev/qa) implementando ao mesmo tempo no mesmo workspace/DB se contaminam → falhas-fantasma em massa que são *artefato* da contaminação, não bugs reais (ex.: "251 failed" causado por seed compartilhado). **Serialize**, ou isole com worktree + schema/DB dedicado por agente. Ao ver falha-fantasma em massa, **suspeite de contaminação de ambiente antes do código** — reproduza limpo e sozinho.
- **Variante no review: um gate que MUTA e um revisor que LÊ o mesmo arquivo não rodam em paralelo.** O gate red-green reintroduz/reverte código no arquivo; um revisor read-only simultâneo vê o arquivo em flux (alternando bug↔fix) e descarta o baseline. Rode o revisor read-only **antes e separado** do gate que aplica mutações; só um agente muta um dado arquivo por vez.

## Higiene de commit (especialmente Windows)

- **`git add` por caminho, nunca `git add -A`/`.`** Pode haver trabalho não-relacionado não-commitado (de outro agente, de outra frente) que contamina o PR. Adicione só os arquivos que você tocou.
- **Formatador só nos arquivos tocados,** não no projeto inteiro — `ruff format <arquivos>` (ou equivalente), não `ruff format .` — senão o diff explode com ruído.
- **CRLF engana o `--check` do formatador no Windows.** Um `format --check` pode acusar diferença que é só fim-de-linha. Normalize EOL (`.gitattributes`) antes de confiar no resultado.
- **Use sempre o formatador/linter PINADO do projeto** (`uv run ruff`, não o binário do PATH). Estilo de format muda entre versões — "formatar" com a versão do sistema e o CI reprovar com a versão pinada é a causa real (mais que CRLF) de quebrar o lint sprint após sprint. O juiz é o comando do CI.
- **`ruff check` ≠ `ruff format` (lint não é o mesmo que format).** `ruff format` só reescreve estilo; **não corrige nem acusa** violações de lint como ordenação de imports (`I001`). Declarar "ruff OK" tendo rodado só `format` deixa o `ruff check` (o gate real do CI) vermelho. Rode `ruff check` (com `--fix` se quiser) nos arquivos tocados antes de declarar verde — o juiz é o comando do CI.
- **Verifique a COMPLETUDE do commit, não só o escopo.** O risco não é só commitar demais — é commitar de **menos**: o núcleo da task fica não-commitado no working tree e o `git status` mostra como se estivesse pronto. Antes do PR rode `git diff main HEAD --stat` (o que o CI vai ver) e confirme que TODOS os arquivos do deliverable estão lá.
- **Reverter uma sonda de teste/mutação com `git checkout`/`git restore` apaga trabalho não-commitado adjacente.** Quando há trabalho legítimo não-commitado na árvore (o caso normal neste fluxo), desfaça a sonda com **Edit** (a linha exata que você mudou), nunca `git checkout` (que não distingue sua sonda do trabalho não-commitado ao lado).

## Promoção de lições (este diretório)

- Ao fechar uma sprint/tarefa com aprendizado, decida explicitamente: **específico do projeto** (vai para a memória local) ou **generalizável** (destila para o playbook de papel em `docs/lessons/`). Ver [README](README.md) para as regras de promoção.
