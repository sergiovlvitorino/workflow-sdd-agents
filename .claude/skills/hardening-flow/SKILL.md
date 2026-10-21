---
name: hardening-flow
description: Faz uma revisão de segurança orientada a risco e corrige os achados por severidade. Reaudita o que já foi decidido (baseline anterior, exceções e riscos aceitos vencidos), roda os scanners de verdade (via skill security-analysis, quando instalada), um painel (tl-qa + tl-* da stack + sre) audita a superfície de ataque, os achados são triados por severidade/exploitabilidade, e cada correção bloqueante é executada via review-loop com teste que prova a vulnerabilidade fechada e, quando o defeito é de classe, um gate anti-regressão. Use quando o usuário pedir "revisão de segurança", "hardening", "corrigir vulnerabilidades", "análise OWASP", ou disser /hardening-flow <escopo>.
---

# hardening-flow

Estratégia de **segurança orientada a risco**: reaudita o que já foi decidido, audita a superfície de ataque com ferramenta e com leitura, prioriza por severidade real e corrige com prova (teste que falha antes do fix). Reutiliza `security-analysis` para a auditoria executada e `review-loop` para as correções.

## Quando usar

Quando o objetivo é reduzir risco de segurança: revisão pré-release, hardening de uma área sensível (auth, multi-tenant, pagamentos, upload, deserialização), resposta a um achado de scanner, auditoria periódica, ou quando um **gatilho de reauditoria** do perfil de ameaça disparou. Vem como argumento (`/hardening-flow <escopo>`) ou da conversa.

## Princípios

- **Risco real, não checklist cego.** Severidade = impacto × exploitabilidade no *contexto deste sistema*. Um teórico sem caminho de exploração não prioriza sobre um explorável.
- **Executar antes de afirmar.** A base de advisories é viva e a premissa "deps limpas" de um spec envelhece: rode os scanners de verdade a cada auditoria. Leitura de código não substitui `pip-audit`/`npm audit`/gitleaks — ela pega outra classe de defeito. **Ferramenta ausente nunca é verde:** registre `não executado: <motivo>`.
- **O já decidido também vence.** Allowlist, `# nosec`, risco aceito e item adiado têm prazo ou gatilho; vencido é achado, não histórico.
- **Provar a falha antes de corrigir.** Cada vulnerabilidade bloqueante ganha um **teste que a demonstra** (negativo de segurança) e que passa só depois do fix — senão a regressão volta. Defeito de **classe** (rota sem autorização, sink de DOM, action sem pin) ganha também um **gate** que pega a próxima instância.
- **Defesa, não ofensa.** O foco é fechar brechas e validar defensivamente. Não produza exploits prontos para uso malicioso; PoC de validação fica no mínimo necessário para provar/testar a correção.
- **Não rebaixar postura.** Suprimir um achado só **por ID, com motivo, `review-by:<data>` e item de dívida**, revisado pelo `tl-qa`/`sre` — nunca global, nunca para "passar o gate". Rebaixar um gate a warning (`|| true`, `::warning::`) é **fail-open**.

## Mapeamento

| Passo | Agente / skill |
|-------|----------------|
| Contexto (perfil, baseline, playbook) e reauditoria do já decidido | orquestrador |
| Mapear superfície de ataque / entrypoints | `Explore` (read-only) |
| Auditoria executada (scanners + OWASP + drift do perfil) | skill `security-analysis`; sem ela, `sre` roda os scanners |
| Auditoria por leitura (painel, em paralelo) | `tl-qa` (invariantes/abuso), `tl-*` da stack (vulns de código), `sre` (config/infra/segredos/deps/CI) |
| Triagem por severidade | orquestrador (consolida e prioriza) |
| Corrigir cada achado bloqueante | skill `review-loop` (com teste de prova e, se de classe, gate) |

## Procedimento

### 0. Escopo, modelo de ameaça e memória
1. Defina o **escopo** (módulo, endpoint, fluxo, ou app inteiro) e o que se está protegendo (dados sensíveis, isolamento entre tenants, dinheiro, custo, disponibilidade). Confirme que é uso **autorizado/defensivo** (revisão do próprio projeto). Se ambíguo, pergunte.
2. Leia o que o projeto já sabe, se existir:
   - **perfil de ameaça** (`docs/security/threat-model.md`, `THREAT_MODEL.md`, `SECURITY.md` ou equivalente): ativos, fronteiras, controles declarados, riscos aceitos, lacunas, comandos de scan, gatilhos;
   - **baseline/relatório anterior** de hardening (ex.: `docs/quality/hardening-baseline-*.md`, `docs/security/`) e as dívidas de segurança registradas no backlog;
   - **playbook de segurança** (`~/.claude/lessons/security.md` e, se houver, `docs/lessons/security.md`): classes de defeito que já escaparam antes. Confronte cada lição com o código atual.
3. **Exclusão de escopo é decisão de risco.** Superfície deixada de fora "por design" (admin, rota interna, job, webhook) é justamente onde escalada se esconde: registre o motivo e quem decidiu, e leve-a ao usuário em vez de excluí-la em silêncio.
4. Crie um TODO: contexto → reauditoria → mapear → auditar (executada + painel) → triar → corrigir (por severidade) → reverificar → atualizar perfil.

### 1. Reauditoria do já decidido
Antes de procurar achados novos, confira os antigos. Cada item abaixo vencido ou quebrado entra na triagem como achado:
- **Exceções com prazo:** IDs em allowlist de audit (`--ignore-vuln`, allowlist do `npm audit`, `.trivyignore`, etc.), `# nosec`/`nosemgrep`/`// eslint-disable` de regra de segurança, entradas de `.gitleaksignore`. `review-by` vencido → achado; exceção **sem** motivo ou sem prazo → achado.
- **Riscos aceitos:** o gatilho de reavaliação disparou (ex.: primeiro endpoint de escrita, multi-user, nova dependência de runtime)? Disparou → achado citando o gatilho.
- **Achados adiados** do baseline anterior: ainda abertos e agora com fix disponível (ex.: CVE que só tinha correção em major e a major saiu)? → achado.
- **Controles declarados:** o teste/receita que prova cada um ainda existe e passa? Sumiu ou mudou → achado de **drift**, com a severidade do risco que ele cobria.

### 2. Superfície de ataque (agente `Explore`)
`Explore` (read-only) levanta os **entrypoints** e a superfície: rotas/handlers, parsers de input, fronteiras de confiança, autenticação/autorização, acesso a dados (incl. isolamento multi-tenant), segredos, dependências, workflows de CI/CD e pontos de I/O externo. Compare com o perfil: entrypoint, permissão ou dependência fora dele é **superfície não modelada**. Saída: o mapa que orienta a auditoria.

### 3. Auditoria
Duas frentes, **em paralelo** (um bloco com múltiplas chamadas), porque pegam classes diferentes de defeito.

**3a. Executada (ferramenta).** Use a skill **`security-analysis`** se estiver instalada: ela descobre as stacks, roda segredos (histórico + árvore), SAST, dependências por ecossistema, IaC, containers e CI, aplica o OWASP filtrado e confere o perfil. Sem ela, o `sre` faz o mesmo: roda as **receitas do próprio projeto** (Makefile, scripts, workflow de CI) ou, sem receita, os scanners da stack — no mínimo segredos no histórico completo e audit de dependências de cada manifesto — e devolve comando, versão e resultado de cada um, ou `não executado: <motivo>`.

**3b. Por leitura (painel).** Cada agente com lente distinta e o mapa do passo 2:
- **`tl-*` da stack — vulnerabilidades de código:** injeção (SQL/NoSQL/cmd/template), XSS e sinks de DOM, deserialização insegura, path traversal, SSRF, controle de acesso quebrado (predicado de autorização **deny-by-default**: lista de permissões exigidas vazia não pode autorizar; escopo de plataforma ≠ admin de tenant), corpo de erro que vaza **valor** sensível (o detalhe vai para o log, não para a resposta), criptografia e validação de cadeia mal usadas, CSP/CORS (meta e header se aplicam por interseção; `frame-ancestors` só no header; origem sem path e sem curinga).
- **`tl-qa` — invariantes sob abuso:** bypass de autorização, isolamento entre tenants, idempotência/replay e condições de corrida (check-then-act), ciclo de vida de token (rotação one-time, cleanup que apaga o que a detecção de reuse precisa), trade-offs rotulados como "sign-off rotineiro" que degradam um controle ativo — e se há **testes negativos** e **gates** protegendo cada invariante.
- **`sre` — configuração, infra e cadeia de entrega:** segredos versionados (o scanner lê o histórico cumulativo), permissões excessivas (IAM com `*`, token do CI amplo), headers/TLS, dependências vulneráveis e **simetria dos gates** entre stacks (um fail-closed e outro warning = piso mais fraco), supply chain do CI (actions sem pin por SHA, `pull_request_target` com checkout do PR, `${{ github.event.* }}` em `run:`, binário baixado sem checksum, lockfile sem hashes), exposição de superfície, logging de dados sensíveis, alarmes de custo/abuso.

Cada frente retorna achados com: descrição, **localização** (arquivo:linha), **caminho de exploração** plausível (uma frase), impacto, **evidência** (saída de scanner, teste, ou leitura marcada como tal) e correção sugerida.

### 4. Triagem por severidade
Consolide os achados (dedup entre a reauditoria, a frente executada e as três lentes do painel) e classifique cada um por **severidade** (Crítico/Alto/Médio/Baixo) combinando impacto × exploitabilidade no contexto real — CVE em dependência que não chega ao artefato não é Crítico. Separe:
- **Bloqueantes** (Crítico/Alto, ou Médio explorável) → corrigir nesta rodada.
- **Aceitos/adiados** (Baixo, teórico sem caminho, ou sem fix disponível) → registrar com justificativa, **`review-by:<data>` ou gatilho**, e item de dívida no backlog. Advisory sem fix disponível: gate continua **bloqueante** com allowlist **por ID** só do residual — a allowlist não inclui o CVE que esta rodada fechou, para que reverter a dependência volte a reprovar.

Apresente a triagem ao usuário antes de corrigir se o volume/risco for relevante.

### 5. Correção por severidade (skill `review-loop`)
Para cada achado bloqueante, **na ordem de severidade**, invoque a skill **`review-loop`** com a tarefa: "fechar a vulnerabilidade X" e as exigências:
1. **Teste que a prova** — falha antes do fix, passa depois. Para vazamento, asserte a ausência do **valor** sensível, não do nome do campo.
2. **Gate anti-regressão quando o defeito é de classe** — scanner/guard estático que reprova a próxima instância (ex.: toda rota exige escopo de autorização; nenhum sink de DOM com dado dinâmico; toda action pinada por SHA; nenhum step de audit com `|| true`). O gate deve ter **mutação provada** (introduzir a falha → vermelho) e **nascer verde no mesmo PR**: gate vermelho sem caminho para verde é build quebrado.

O `review-loop` executa `dev-*`/`spec-*` → `tl-*`+`tl-qa`, com escalonamento para o `spec-*` em 3 falhas. O `tl-qa` confirma que o teste negativo trava a causa e que o gate não é contornável.

### 6. Reverificação
Rode de novo a frente executada (passo 3a) sobre o resultado: os achados corrigidos somem, nenhum novo aparece, e as exceções restantes estão todas com motivo e prazo.

### 7. Encerramento
1. Resuma: a superfície auditada, os scanners rodados (e os `não executado`), a tabela de achados por severidade (corrigidos vs. aceitos/adiados com justificativa e prazo), os testes de prova e gates adicionados, e o risco residual.
2. **Atualize a memória de segurança do projeto** no mesmo PR das correções: perfil de ameaça (controles novos com evidência, riscos aceitos com gatilho, lacunas fechadas ou abertas, superfície nova) e/ou um baseline datado com os achados triados. É o ponto de partida da próxima reauditoria (passo 1).
3. Para achados adiados, **proponha tarefas de follow-up** no backlog, cada uma com o `review-by`. Se a auditoria revelar dívida estrutural, encadeie um `debt-flow`.
4. Classe de defeito que escapou de uma auditoria anterior ou que só a ferramenta pegou → proponha a lição destilada para o playbook de segurança.

## Observações
- Mantenha-se no contexto **defensivo/autorizado**. Recuse derivar para técnicas ofensivas de uso malicioso; o PoC existe só para provar e testar a correção.
- Severidade é contextual: replique o juízo de exploitabilidade ao *seu* sistema, não a um CVSS genérico.
- Nunca feche um achado bloqueante sem o teste de regressão de segurança rodando e verde.
- Auditoria e scanners são só leitura: nada de deploy, `apply`, chamada mutável à cloud ou tráfego contra ambiente de terceiros. Segredo encontrado é mascarado no relatório.
