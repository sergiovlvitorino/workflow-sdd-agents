---
name: debt-flow
description: Refatora código ou paga dívida técnica preservando o comportamento. Primeiro o QA escreve testes de caracterização que fixam o comportamento atual, depois o Plan desenha o refactor e a execução vai à skill review-loop — os testes de caracterização não podem mudar. Use quando o usuário pedir para "refatorar", "pagar dívida técnica", "limpar/modernizar um módulo" sem alterar funcionalidade, ou disser /debt-flow <alvo>.
---

# debt-flow

Estratégia de **refactor com rede de segurança**: muda a forma do código **sem mudar o comportamento observável**. A garantia vem de testes de caracterização escritos *antes* do refactor. Reutiliza `Plan` para o desenho e `review-loop` para a execução.

## Quando usar

Quando o alvo é melhorar estrutura/legibilidade/performance/idiomatismo **sem** alterar a funcionalidade: extrair módulos, trocar padrão de injeção, eliminar duplicação, modernizar APIs internas. Vem como argumento (`/debt-flow <módulo/alvo>`) ou da conversa.

> **Comportamento novo NÃO é debt-flow.** Se o objetivo muda o que o sistema faz, use `sprint-flow` (feature) ou `bug-flow` (correção). Aqui a invariante é: *mesma entrada → mesma saída*.

## Princípios

- **Caracterizar antes de mexer.** Sem testes que fixam o comportamento atual, refatorar é apostar. Os testes de caracterização são a âncora.
- **Os testes de caracterização são imutáveis durante o refactor.** Se um deles precisar mudar para o código passar, isso é uma **mudança de comportamento** — pare e reporte; não é mais refactor.
- **Passos pequenos e reversíveis.** Prefira uma sequência de transformações seguras a um big-bang.
- **Você é o orquestrador.** Caracterização → `qa`/`qa-automator`; desenho → `Plan`; execução → `review-loop`.

## Mapeamento

| Passo | Agente |
|-------|--------|
| Mapear comportamento e pontos de risco | `Explore` (read-only) |
| Testes de caracterização | `qa-automator` (ou `qa`) |
| Desenhar o refactor (estratégia, ordem) | `Plan` |
| Refatorar + revisar + escalar | skill `review-loop` |

## Procedimento

### 0. Preparação
1. Defina o alvo e o **motivo** da dívida (o que dói: acoplamento, duplicação, performance, padrão obsoleto). Se vago, faça 1–2 perguntas.
2. Crie um TODO: caracterizar → desenhar → refatorar via review-loop → confirmar comportamento preservado.

### 1. Rede de segurança (agentes `Explore` + `qa-automator`)
- `Explore` mapeia o comportamento observável do alvo (entradas, saídas, efeitos colaterais, contratos públicos) e os pontos de risco.
- `qa-automator` (ou `qa`) escreve **testes de caracterização** que fixam esse comportamento atual — incluindo edge cases e efeitos colaterais — e os roda mostrando **verde no código atual**. Se a cobertura do alvo já for forte, confirme e reaproveite; senão, complete as lacunas antes de seguir.

Não prossiga enquanto não houver uma rede que falharia se o comportamento mudasse.

### 2. Desenho do refactor (agente `Plan`)
Acione o `Plan` para produzir a estratégia: sequência de transformações, arquivos afetados, ordem segura, riscos e critério de "pronto". O plano deve ser **incremental** (cada passo mantém a suíte verde).

Apresente o plano ao usuário e obtenha aprovação se o refactor for amplo.

### 3. Execução (skill `review-loop`)
Invoque a skill **`review-loop`** passando o plano como tarefa, com a **restrição explícita**: "os testes de caracterização `<...>` NÃO podem ser alterados; eles devem continuar verdes". O `review-loop` executa com `dev-*` → `tl-*`+`tl-qa` → escala `spec-*` em 3 falhas.

- O `tl-qa` deve verificar especificamente que: (a) os testes de caracterização não foram tocados; (b) não houve rebaixamento de quality gate; (c) a suíte roda verde de verdade.

### 4. Encerramento
Resuma: o que mudou estruturalmente (antes/depois em alto nível), os testes de caracterização usados como âncora, confirmação de que permaneceram intactos e verdes, métricas relevantes (cobertura, complexidade, performance se aplicável) e eventuais escalonamentos.

## Observações
- Se no meio do caminho ficar claro que um teste de caracterização **precisa** mudar, isso revela uma mudança de comportamento escondida — **pare, reporte ao usuário** e reclassifique (feature/bug), não force.
- Mantenha o refactor no escopo do alvo; não deixe virar reescrita.
