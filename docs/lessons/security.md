# Playbook Segurança — autorização, segredos, confiança

> Lições generalizáveis. Confronte com o código atual antes de aplicar (ver [README](README.md)).

## Autorização multi-tenant e segregação de escopo

- **Escopo de plataforma ≠ admin-de-tenant.** Tratar `platform:admin` como um `admin` "graúdo" abre escalada cross-tenant (o admin do tenant A consegue agir sobre o tenant B). Os escopos de plataforma são um eixo separado de autorização, com seu próprio gate.
- **Privilégio de sistema só no caminho de leitura.** Em RLS, o ator de sistema (worker) entra só no `USING` da policy; escrita permanece amarrada ao tenant do registro (`WITH CHECK`). Ver [python.md](python.md).
- **Primeira credencial out-of-band.** A chave/admin inicial não pode ser auto-emissível pela própria API (senão é bootstrap inseguro). Gotcha: ambiente `live`/`test` errado na primeira chave → 401 silencioso.
- **Gate de scanner para a invariante de autorização.** Tenha um teste/scanner que falha se uma rota nova não tem cobertura cross-tenant — análogo ao gate de RLS.

- **Deny-by-default no predicado de autorização.** `if not needed: return False` — uma lista de scopes exigidos vazia não pode resultar em "autorizado" (fail-open). O curinga `admin` cobre só scopes de tenant (`not any(is_platform_scope(s) for s in needed)`), nunca os de plataforma.
- **Gate anti-regressão de autorização** (análogo ao scanner cross-tenant): scanner AST que captura o **valor** do `require_scope` — toda rota de plataforma exige o scope de plataforma; nenhuma rota de tenant aceita scope de plataforma; sentinela `exit 2`. Mutação: rota de plataforma volta ao scope de tenant → `exit 1`.

## Ponto cego de pentest

- **"Exclusão by-design" mascara escalada de autorização.** Quando o pentest *exclui* uma superfície por considerá-la "fora de escopo por design", pode estar pulando exatamente o caminho de escalada. Escopo de exclusão é decisão de risco — documente e revise, não trate como ausência de risco.

## Secret-scanning / segredos no repo

- **Nunca versione artefato assinado com certificado real** (golden assinado). Assine **em runtime** no teste; versione só o conteúdo pré-assinatura. Um certificado/chave commitado é vazamento permanente no histórico.
- **Scanner lê o histórico cumulativo**, não só o HEAD. Para limpar um segredo já commitado, achatar/reescrever o histórico — remover no último commit não basta.
- **Senha de teste canônica** (ex.: `testpassword`) para o scanner não acusar credencial de fixture como real.
- **Supressão cirúrgica e justificada:** quando uma primitiva fraca é exigida por um sistema externo legado (ex.: SHA1 numa assinatura que um parceiro externo legado exige), suprima o achado **na linha** com justificativa (`# nosec ...`), não globalmente.

## Trust store / cadeia de certificados (PKIX)

- **Valide a cadeia real, não substring.** Conferir o "issuer" por comparação de string é falsificável. Use verificação criptográfica da emissão (`verify_directly_issued_by` / construção de cadeia PKIX), não matching textual.
- **Vendorizar CA roots públicas é de graça; o ato de confiança é o confronto de fingerprint.** Trazer os certificados raiz para o repo custa $0 — mas o que estabelece confiança é comparar o fingerprint contra uma **fonte oficial independente** (o site da AC/SO), não o fato de o arquivo estar lá.
- **Raiz não-verificável ou revogada → exclua (fail-safe).** Na dúvida sobre uma raiz, removê-la falha fechado (rejeita) em vez de aberto (aceita cadeia duvidosa). Uma raiz ativa não-coberta vira **limitação rastreável** (item de monitoramento), não furo.
- **Use o validador de cadeia certo para o perfil do cert.** Um verificador TLS-servidor (exige SAN DNS + EKU `serverAuth`) **rejeita** um cert de assinatura legítimo (e-CNPJ A1 não tem isso). Construa a cadeia até a âncora (path-building) em vez de usar o perfil de servidor.

## Decisão de confiança e vazamento

- **Confiar em CA roots é decisão humana-auditada, não automatizável às cegas.** Leve a opção (vendorizar reais vs placeholder vs adiar) à pessoa e tenha um segundo par de olhos confrontando os fingerprints contra a fonte oficial **antes** de mergear. Não confie no auto-relato de quem implementou sobre quais raízes incluir.
- **Corrigir um binding de validação pode expor PII no corpo do erro.** Um `issue=str(err)` que formata "esperado X, encontrado Y" vaza o valor. O corpo do erro é literal/opaco; o par detalhado vai só para o log. Asserte ausência do **valor** sensível no corpo (não do nome do campo).
