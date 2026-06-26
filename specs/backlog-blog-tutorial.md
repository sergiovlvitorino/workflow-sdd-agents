# Backlog Refinado — Blog Tutorial (projeto-exemplo SDD)

**Status:** Refinado (discovery concluído)
**Versão:** 1.0.0
**Data:** 2026-06-24
**Responsável:** PO
**Constitution:** v1.0.0
**Origem:** discovery-flow
**Handoff:** pronto para sprint-flow

> Este backlog é o produto do discovery. Ele NAO detalha tarefas técnicas (isso é papel dos tl-* no sprint-flow). Cada story só ganhou lugar por ensinar um princípio da constitution ou exercitar um passo do fluxo de agentes.

---

## 1. Elevator pitch

> PARA desenvolvedores que acabaram de clonar este projeto-base de Spec-Driven Development e nao sabem por onde comecar, o Blog Tutorial e um projeto-exemplo minimo que os leva de ponta a ponta pelo ciclo discovery-flow -> design-flow -> sprint-flow -> review-loop -> retrospectiva. DIFERENTE de ler a documentacao solta ou um README extenso, ele deixa o dev ver os agentes (PO/TL/dev/QA) atuando de verdade sobre um dominio trivial e familiar (posts de blog), aprendendo na pratica como specs, licoes e quality gates se encaixam — sem precisar entender um dominio de negocio complexo ao mesmo tempo.

O blog e o "hello world" didatico. O dominio "posts de blog" foi escolhido por ser universalmente compreendido (zero carga cognitiva de negocio), deixando 100% da atencao do dev no processo SDD. O valor nao esta no blog funcionar — esta no caminho percorrido para construi-lo.

## 2. Personas

| # | Persona | Quem e | O que quer | Dor atual |
|---|---|---|---|---|
| P1 (primaria) | Dev-aprendiz | Dev que clonou o base e quer aprender a opera-lo | Percorrer o ciclo SDD completo uma vez, vendo os agentes e gates em acao | "Tenho 9 skills, 20+ agentes e 7 templates — nao sei por onde comecar nem como eles se conectam." |
| P2 (secundaria) | Autor ficticio | Personagem do dominio do blog | Criar/editar/listar seus posts | (existe so para dar substancia as stories — nao e cliente real) |
| P3 (secundaria) | Leitor ficticio | Personagem do dominio do blog | Ler posts publicados | (idem — da substancia a leitura/listagem/paginacao) |

> Importante: o cliente real e a P1. P2/P3 existem para que o dominio exercite os principios. Toda decisao de escopo e tomada a favor de P1.

## 3. Valor / dor que resolve

- Reduz time-to-first-contribution do projeto-base: do "clonei e travei" para "completei um ciclo e entendi o fluxo".
- Torna os principios da constitution tangiveis: em vez de ler "P-03 idempotencia", o dev ve um teste de idempotencia nascer e passar.
- Serve de referencia viva: vira o exemplo canonico que a documentacao aponta ("siga o blog-tutorial").

## 4. Metricas de sucesso (didaticas)

| # | Metrica | Alvo |
|---|---|---|
| M1 | Dev novo completa o ciclo ponta-a-ponta (discovery -> retrospectiva) seguindo o exemplo | < 1 dia de trabalho guiado |
| M2 | Principios da constitution demonstrados pelo MVP (pelo menos um teste/artefato visivel por principio coberto) | >= 6 dos 14 principios exercitados |
| M3 | Skills da espinha dorsal percorridas ao seguir o exemplo (discovery -> design -> sprint -> review-loop -> retrospectiva) | 5 de 5 |
| M4 | Dev consegue explicar, ao final, "o que e um quality gate ratchet e por que a regressao nasce vermelha" | autoavaliacao positiva (checklist no fim do tutorial) |

---

## 5. Epicos

| Epico | Nome | Proposito pedagogico |
|---|---|---|
| E1 | Autoria de posts (escrita) | Demonstrar API-First, idempotencia, autorizacao e falha explicita no caminho de escrita |
| E2 | Leitura e listagem (consumo) | Demonstrar contrato de leitura, paginacao e isolamento de autorizacao (rascunho vs publicado) |
| E3 | Observabilidade e operacao | Demonstrar observabilidade dia-1 e DoD vinculante de forma minima |
| E4 | Trilha didatica do fluxo SDD | O "meta-epico": garantir que o exemplo ensine o processo, nao so o blog |

---

## 6. User Stories, MoSCoW e Criterios de Aceite

> Estimativas: Valor e Esforco em escala S/M/L. Valor = aporte pedagogico para P1.

### E1 - Autoria de posts

#### F001 - Criar post com idempotencia - Must

Como autor ficticio, quero criar um post enviando uma chave de idempotencia, para que retries de rede nao dupliquem o post - e o dev-aprendiz veja o P-03 em acao.

- Valor: L | Esforco: M
- Principios demonstrados: P-01 (API-First), P-03 (idempotencia), P-11 (falha explicita), P-02 (rastreavel a CA)

Criterios de aceite (Gherkin):

    Cenario: CA-F001-01 Criacao bem-sucedida
      Dado um autor autenticado
      Quando ele envia POST /v1/posts com titulo e conteudo validos e uma chave de idempotencia nova
      Entao a resposta e 201
      E o corpo contem o id do post e status rascunho

    Cenario: CA-F001-02 Retry com a mesma chave nao duplica (P-03)
      Dado um post ja criado com a chave de idempotencia K1
      Quando o mesmo POST /v1/posts e reenviado com a chave K1
      Entao a resposta e 200 ou 201 idempotente
      E nenhum post novo e criado
      E o id retornado e o mesmo da primeira chamada

    Cenario: CA-F001-03 Payload invalido falha explicitamente (P-11)
      Dado um autor autenticado
      Quando ele envia POST /v1/posts sem titulo
      Entao a resposta e 422
      E o corpo contem erro tipado validation_error apontando o campo title

    Cenario: CA-F001-04 Sem chave de idempotencia em rota de escrita e rejeitado (P-03)
      Dado um autor autenticado
      Quando ele envia POST /v1/posts sem o cabecalho de idempotencia
      Entao a resposta e 400
      E o corpo contem erro idempotency_key_required

#### F002 - Editar e publicar post - Must

Como autor ficticio (contexto local, sem autenticacao - ADR-0004), quero publicar e editar posts, para que o blog publique de verdade e o dev-aprendiz veja uma maquina de estados (draft -> published) com idempotencia e falha explicita.

- Valor: L | Esforco: M
- Principios demonstrados: P-03 (idempotencia na escrita), P-11 (falha explicita), P-08 (versionamento /v1), P-04 (rascunho nao vaza - garantido pela allowlist de leitura, nao por ownership)

> Decisao ADR-0004 (aceita): nao ha autenticacao/usuario/ownership. "Publicar" e uma transicao de estado aberta; P-04 e satisfeito exclusivamente pela allowlist de leitura (rascunho invisivel em GET /v1/posts e por id). Edicao de conteudo (PUT /v1/posts/{id}) esta fora do MVP - F002 entrega a transicao de publicacao, que e a entrega de valor.

Criterios de aceite (Gherkin):

    Cenario: CA-F002-01 Publicar um rascunho
      Dado um post em rascunho de id P1
      Quando o cliente envia PUT /v1/posts/P1/publish
      Entao a resposta e 200
      E o status do post passa a published
      E published_at e preenchido com o instante da publicacao

    Cenario: CA-F002-02 Republicar e idempotente (P-03)
      Dado um post ja publicado de id P1 com published_at = T1
      Quando o cliente envia PUT /v1/posts/P1/publish novamente
      Entao a resposta e 200
      E o status permanece published
      E published_at continua igual a T1 (sem efeito colateral, sem duplicar)

    Cenario: CA-F002-03 Publicar post inexistente falha explicitamente (P-11)
      Dado nenhum post com id 999
      Quando o cliente envia PUT /v1/posts/999/publish
      Entao a resposta e 404
      E o corpo contem erro tipado post_not_found

### E2 - Leitura e listagem

#### F003 - Listar posts publicados com paginacao - Must

Como leitor ficticio, quero listar os posts publicados de forma paginada, para que o dev-aprendiz veja paginacao como contrato de API estavel.

- Valor: L | Esforco: S
- Principios demonstrados: P-01 (API-First), P-06 (contrato extensivel), P-04 (so publicados aparecem ao publico)

Criterios de aceite (Gherkin):

    Cenario: CA-F003-01 Lista paginada de publicados
      Dado 25 posts publicados
      Quando o leitor envia GET /v1/posts?limit=10
      Entao a resposta e 200
      E retorna 10 itens
      E retorna um cursor/next para a proxima pagina

    Cenario: CA-F003-02 Rascunhos nao aparecem para o publico (P-04)
      Dado 3 posts em rascunho e 2 publicados
      Quando o leitor anonimo envia GET /v1/posts
      Entao a resposta contem apenas os 2 posts publicados

    Cenario: CA-F003-03 Pagina seguinte via cursor e estavel
      Dado uma primeira pagina obtida com cursor C1
      Quando o leitor envia GET /v1/posts?cursor=C1
      Entao a resposta retorna os itens seguintes sem repetir os ja vistos

#### F004 - Ler um post pelo id - Must

Como leitor ficticio, quero abrir um post publicado pelo id, para que o exemplo tenha o caminho de leitura unitaria e seu caso negativo.

- Valor: M | Esforco: S
- Principios demonstrados: P-01 (API-First), P-04 (rascunho de terceiro nao e legivel por anonimo), P-11 (404 tipado)

Criterios de aceite (Gherkin):

    Cenario: CA-F004-01 Leitura de post publicado
      Dado um post publicado de id P1
      Quando o leitor envia GET /v1/posts/P1
      Entao a resposta e 200 com o conteudo do post

    Cenario: CA-F004-02 Rascunho nao e legivel por anonimo (P-04)
      Dado um post em rascunho de id P2
      Quando um leitor anonimo envia GET /v1/posts/P2
      Entao a resposta e 404 e nao revela existencia

### E3 - Observabilidade e operacao

#### F005 - Observabilidade minima dos endpoints - Should

Como dev-aprendiz, quero ver metricas RED e log estruturado nos endpoints do blog, para que eu entenda como o P-05 nasce no dia 1, nao depois.

- Valor: M | Esforco: M
- Principios demonstrados: P-05 (observabilidade dia-1), P-13 (DoD: RED instrumentado), P-09 (log sem dado sensivel)

Criterios de aceite (Gherkin):

    Cenario: CA-F005-01 Endpoint emite metrica RED
      Dado o endpoint POST /v1/posts instrumentado
      Quando uma requisicao e processada
      Entao sao registradas as metricas de Rate, Errors e Duration

    Cenario: CA-F005-02 Log estruturado sem dado sensivel (P-09)
      Quando qualquer endpoint do blog e chamado
      Entao e emitido um log estruturado com request_id
      E o log nao contem segredos

#### F006 - Dashboard/healthcheck do servico - Could

Como dev-aprendiz, quero um healthcheck e um esboco de dashboard, para que eu veja saude do servico como entregavel de produto.

- Valor: S | Esforco: M
- Principios demonstrados: P-05 (dashboard e entregavel de produto)

Criterios de aceite (Gherkin):

    Cenario: CA-F006-01 Healthcheck responde
      Quando GET /v1/health e chamado
      Entao a resposta e 200 com status ok

### E4 - Trilha didatica do fluxo SDD

#### F007 - Specs preenchidas do blog como exemplo canonico - Must

Como dev-aprendiz, quero encontrar os templates 001-007 preenchidos para o blog, para que eu tenha um exemplo de referencia de SDD bem feito.

- Valor: L | Esforco: M
- Principios demonstrados: P-02 (spec e fonte da verdade), P-01, P-13, P-14 (decisoes registradas)

Criterios de aceite (Gherkin):

    Cenario: CA-F007-01 Specs essenciais existem e sao rastreaveis
      Dado o projeto-exemplo do blog
      Entao existem specs 001 overview, 003 RFs, 005 API e 007 test-strategy preenchidas
      E cada RF e rastreavel a pelo menos um CA-XXX (P-02)

    Cenario: CA-F007-02 Pelo menos um ADR documenta uma decisao do blog (P-14)
      Dado uma escolha tecnica do exemplo, ex. paginacao por cursor vs offset
      Entao existe um ADR em specs/adr/ que a registra

#### F008 - Guia percorra o ciclo com o blog - Should

Como dev-aprendiz, quero um passo-a-passo que me diga qual skill acionar em cada etapa do blog, para que eu reproduza o ciclo completo sozinho.

- Valor: L | Esforco: S
- Principios demonstrados: meta - amarra o fluxo de agentes; suporta M1, M3, M4

Criterios de aceite (Gherkin):

    Cenario: CA-F008-01 Trilha cobre a espinha dorsal
      Dado o guia do blog-tutorial
      Entao ele indica, em ordem, discovery-flow -> design-flow -> sprint-flow -> review-loop -> retrospectiva
      E aponta qual artefato cada passo produz

    Cenario: CA-F008-02 Checklist de aprendizado ao final (M4)
      Quando o dev conclui a trilha
      Entao ha um checklist que valida entendimento de gate ratchet e red-green

#### F009 - Categorias/tags nos posts - Wont (v1)

Como autor, quero classificar posts por categoria/tag.
Decisao: Wont nesta versao. Nao ensina nenhum principio novo alem do que F001-F004 ja cobrem; so infla o dominio e desvia o foco de P1. Fica registrado para evitar escopo implicito.

#### F010 - Comentarios nos posts - Wont (v1)

Como leitor, quero comentar em posts.
Decisao: Wont nesta versao. Adicionaria uma segunda entidade e moderacao sem aporte pedagogico proporcional. Candidato a segundo exemplo, se um dia quisermos demonstrar relacionamento entre entidades.

---

## 7. Tabela priorizada (saida obrigatoria)

| Epico | Story | Prioridade MoSCoW | Valor | Esforco | No MVP? |
|---|---|---|---|---|---|
| E1 | F001 - Criar post com idempotencia | Must | L | M | Sim |
| E1 | F002 - Editar e publicar post (transicao aberta - ADR-0004) | Must | L | M | Sim |
| E2 | F003 - Listar posts publicados (paginacao) | Must | L | S | Sim |
| E2 | F004 - Ler um post pelo id | Must | M | S | Sim |
| E4 | F007 - Specs-exemplo preenchidas | Must | L | M | Sim |
| E3 | F005 - Observabilidade minima | Should | M | M | Recomendado |
| E4 | F008 - Guia percorra o ciclo | Should | L | S | Recomendado |
| E3 | F006 - Dashboard/healthcheck | Could | S | M | Nao |
| E1/E2 | F009 - Categorias/tags | Wont (v1) | S | M | Nao |
| E2 | F010 - Comentarios | Wont (v1) | S | L | Nao |

---

## 8. Definicao do MVP

MVP = o menor conjunto que entrega o valor pedagogico (P1 percorre o ciclo e ve os principios em acao).

Nucleo obrigatorio (Must): F001, F002, F003, F004, F007.
Esse nucleo ja exercita o CRUD essencial do dominio E demonstra os principios mais didaticos (API-First, idempotencia, autorizacao, paginacao, falha explicita, spec como fonte da verdade).

Inclusao recomendada no MVP (Should de alto valor / baixo esforco):
- F008 (guia da trilha) - esforco S e valor L: sem ele, P1 nao sabe como percorrer o ciclo. Recomendo fortemente incluir.
- F005 (observabilidade minima) - demonstra P-05, que e um diferencial forte do base. Incluir se a sprint comportar.

Fora do MVP: F006 (Could), F009 e F010 (Wont v1). Ficam registrados para evitar escopo implicito.

> Sugestao de fatiamento para o sprint-flow:
> - Sprint 1: F007 (specs) + F001 + F003 - esqueleto SDD + escrita idempotente + leitura paginada (o esqueleto andante).
> - Sprint 2: F002 (transicao aberta) + F004 + migracao SQLite (ADR-0003) + bumps de spec (003 v1.1.0, 005) - o blog publica de verdade e persiste estado.
> - Sprint 3: frontend Angular (ADR-0001/0005) + F005 (observabilidade) + F008 (guia da trilha) - costura cross-stack e fechamento didatico.

---

## 9. Rastreabilidade Story -> Principio (constitution)

| Story (MVP) | Principios demonstrados |
|---|---|
| F001 - Criar post idempotente | P-01 API-First, P-02 spec->CA, P-03 idempotencia, P-11 falha explicita |
| F002 - Editar/publicar | P-03 idempotencia (transicao idempotente), P-08 versionamento /v1, P-11 404 tipado, P-04 rascunho nao vaza (allowlist de leitura - ADR-0004, nao ownership) |
| F003 - Listar paginado | P-01 API-First, P-04 so publicados ao publico, P-06 contrato extensivel |
| F004 - Ler por id | P-01 API-First, P-04 rascunho nao legivel, P-11 404 tipado |
| F005 - Observabilidade (recomendado) | P-05 observabilidade dia-1, P-09 log sem dado sensivel, P-13 DoD |
| F007 - Specs-exemplo | P-02 fonte da verdade, P-13 DoD vinculante, P-14 ADR |
| F008 - Guia da trilha (recomendado) | meta-processo (suporta M1/M3/M4) |

Cobertura de principios pelo MVP nucleo: P-01, P-02, P-03, P-04, P-06, P-08, P-11, P-13, P-14 -> 9 principios (supera a meta M2 de >= 6). Com F005: +P-05, +P-09 -> 11.

> Principios nao demonstrados de proposito (nao cabem num exemplo minimo, e tudo bem): P-07 (cobertura por risco - aparece no comportamento dos gates, nao como feature), P-10 (custodia de segredos), P-12 (reversibilidade de integracao - nao ha integracao externa). Registrar isso evita a expectativa de que o exemplo cubra os 14.

---

## 10. Handoff

Discovery concluido. Proximo passo: sprint-flow para planejar as sprints a partir deste backlog (TLs detalham os DETAIL e a execucao roda via review-loop). Antes ou em paralelo, design-flow pode registrar o ADR de paginacao (cursor vs offset) referenciado em F007/CA-F007-02.
