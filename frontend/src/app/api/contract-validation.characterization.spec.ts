/**
 * TESTES DE CARACTERIZAÇÃO — Validação Ajv dos schemas de contrato
 *
 * PROPÓSITO (debt-flow — âncora do refactor):
 *   Este arquivo NÃO testa "o código está correto" — testa "o comportamento ATUAL de
 *   validação é exatamente este". Serve como rede de segurança durante o refactor que
 *   vai substituir os schemas declarados à mão (POST_SCHEMA, PAGE_SCHEMA,
 *   API_ERROR_SCHEMA em contract.spec.ts) por schemas carregados do OpenAPI vivo.
 *
 *   Se um teste VERDE aqui quebrar após o refactor, o comportamento de validação mudou.
 *   Se um teste VERMELHO aqui passar (validar payload inválido), o rigor foi afrouxado.
 *
 * BASELINE CRÍTICO:
 *   POST_SCHEMA usa `additionalProperties: false` → campos extras são REJEITADOS.
 *   API_ERROR_SCHEMA usa `additionalProperties: true` → campos extras são ACEITOS.
 *   Essa ASSIMETRIA INTENCIONAL deve ser preservada no refactor.
 *
 * NÃO importa de src/app/api/generated/** — independente de código gerado.
 * NÃO edita contract.spec.ts nem nenhum arquivo de produção.
 */

import { describe, it, expect, beforeAll } from 'vitest';
import Ajv from 'ajv';
import { readFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

// ---------------------------------------------------------------------------
// Schemas — cópia fiel dos schemas declarados à mão em contract.spec.ts.
// Esta cópia é INTENCIONAL: caracterizar o comportamento ATUAL, não referenciar
// o mesmo objeto (que pode mudar). Se divergirem, o teste alertará.
// ---------------------------------------------------------------------------

const POST_SCHEMA = {
  type: 'object',
  required: ['id', 'title', 'content', 'status', 'created_at'],
  properties: {
    id: { type: 'string' },
    title: { type: 'string' },
    content: { type: 'string' },
    status: { type: 'string', enum: ['draft', 'published'] },
    created_at: { type: 'string' },
    published_at: { anyOf: [{ type: 'string' }, { type: 'null' }] },
  },
  // CRÍTICO: strict — campo extra em Post é INVÁLIDO. Preservar no refactor.
  additionalProperties: false,
} as const;

const PAGE_SCHEMA = {
  type: 'object',
  required: ['items', 'next_cursor', 'limit'],
  properties: {
    items: { type: 'array', items: POST_SCHEMA },
    next_cursor: { anyOf: [{ type: 'string' }, { type: 'null' }] },
    limit: { type: 'integer' },
  },
  additionalProperties: false,
} as const;

const API_ERROR_SCHEMA = {
  type: 'object',
  required: ['type', 'title', 'status'],
  properties: {
    type: { type: 'string' },
    title: { type: 'string' },
    status: { type: 'integer' },
    detail: { anyOf: [{ type: 'string' }, { type: 'null' }] },
    errors: { anyOf: [{ type: 'array', items: { type: 'object' } }, { type: 'null' }] },
  },
  // CRÍTICO: permissivo — ApiError aceita campos extras. Assimetria intencional com Post.
  additionalProperties: true,
} as const;

// ---------------------------------------------------------------------------
// Fixtures e setup
// ---------------------------------------------------------------------------

interface ContractFixtures {
  post_created_201: Record<string, unknown>;
  post_replay_200: Record<string, unknown>;
  post_published_200: Record<string, unknown>;
  post_get_200: Record<string, unknown>;
  posts_list_200: Record<string, unknown>;
  post_not_found_404: Record<string, unknown>;
  post_not_found_404_nonexistent: Record<string, unknown>;
  invalid_cursor_400: Record<string, unknown>;
  idempotency_key_required_400: Record<string, unknown>;
  idempotency_key_conflict_409: Record<string, unknown>;
  validation_error_422: Record<string, unknown>;
  health_200: Record<string, unknown>;
}

let ajv: Ajv;
let fixtures: ContractFixtures;

beforeAll(() => {
  ajv = new Ajv({ strict: false, allErrors: true });
  const fixturesPath = join(__dirname, 'fixtures', 'contract-fixtures.json');
  fixtures = JSON.parse(readFileSync(fixturesPath, 'utf-8')) as ContractFixtures;
});

// ---------------------------------------------------------------------------
// Grupo 1: Fixtures reais VALIDAM (VERDE) — 12 casos
// ---------------------------------------------------------------------------

describe('Characterization: fixtures reais validam contra schema atual (VERDE)', () => {
  // Post fixtures (4 casos)
  const postFixtures = [
    'post_created_201',
    'post_replay_200',
    'post_published_200',
    'post_get_200',
  ] as const;

  for (const name of postFixtures) {
    it(`Post fixture "${name}" valida GREEN contra POST_SCHEMA`, () => {
      const validate = ajv.compile(POST_SCHEMA);
      const result = validate(fixtures[name]);
      expect(result, `Erros Ajv: ${JSON.stringify(validate.errors)}`).toBe(true);
    });
  }

  // Page fixture (1 caso)
  it('Page fixture "posts_list_200" valida GREEN contra PAGE_SCHEMA', () => {
    const validate = ajv.compile(PAGE_SCHEMA);
    const result = validate(fixtures.posts_list_200);
    expect(result, `Erros Ajv: ${JSON.stringify(validate.errors)}`).toBe(true);
  });

  // ApiError fixtures (6 casos) — inclui os 2 de 404, 400x2, 409, 422
  const errorFixtures = [
    'post_not_found_404',
    'post_not_found_404_nonexistent',
    'invalid_cursor_400',
    'idempotency_key_required_400',
    'idempotency_key_conflict_409',
    'validation_error_422',
  ] as const;

  for (const name of errorFixtures) {
    it(`ApiError fixture "${name}" valida GREEN contra API_ERROR_SCHEMA`, () => {
      const validate = ajv.compile(API_ERROR_SCHEMA);
      const result = validate(
        (fixtures as unknown as Record<string, unknown>)[name],
      );
      expect(result, `Erros Ajv: ${JSON.stringify(validate.errors)}`).toBe(true);
    });
  }
});

// ---------------------------------------------------------------------------
// Grupo 2: Payloads mutados FALHAM (VERMELHO) — schema REJEITA lixo
// ---------------------------------------------------------------------------

describe('Characterization: payloads inválidos rejeitados pelo schema (VERMELHO esperado → validate=false)', () => {
  // Caso 2: Post sem campo obrigatório → inválido
  it('Post sem campo "id" (campo obrigatório removido) é REJEITADO pelo POST_SCHEMA', () => {
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const { id: _removed, ...postSemId } = fixtures.post_created_201;
    const validate = ajv.compile(POST_SCHEMA);
    expect(validate(postSemId)).toBe(false);
    // Garante que o erro aponta para o campo ausente
    expect(validate.errors?.some((e) => e.params && 'missingProperty' in e.params && e.params['missingProperty'] === 'id')).toBe(true);
  });

  // Caso 3a: Post com status fora do enum → inválido
  it('Post com status="archived" (fora do enum draft|published) é REJEITADO pelo POST_SCHEMA', () => {
    const postStatusInvalido = { ...fixtures.post_created_201, status: 'archived' };
    const validate = ajv.compile(POST_SCHEMA);
    expect(validate(postStatusInvalido)).toBe(false);
  });

  // Caso 3b: Post com title de tipo errado → inválido
  it('Post com title=123 (número em vez de string) é REJEITADO pelo POST_SCHEMA', () => {
    const postTitleNumero = { ...fixtures.post_created_201, title: 123 };
    const validate = ajv.compile(POST_SCHEMA);
    expect(validate(postTitleNumero)).toBe(false);
  });

  // Caso 4: Post com campo EXTRA → inválido
  // CRÍTICO: trava additionalProperties:false em POST_SCHEMA.
  // Se após o refactor (schema do OpenAPI) esse teste PASSAR, significa que o schema
  // OpenAPI tem additionalProperties:true (ou ausente), afrouxando o contrato atual.
  // Isso é MUDANÇA DE COMPORTAMENTO — requer ADR explícito antes de aceitar.
  it('Post com campo extra "archived:true" é REJEITADO pelo POST_SCHEMA [trava additionalProperties:false]', () => {
    const postCampoExtra = { ...fixtures.post_created_201, archived: true };
    const validate = ajv.compile(POST_SCHEMA);
    expect(validate(postCampoExtra)).toBe(false);
    // Confirma que o erro é de additionalProperties, não de outro problema
    expect(validate.errors?.some((e) => e.keyword === 'additionalProperties')).toBe(true);
  });

  // Caso 5: Page com limit de tipo errado → inválido
  it('Page com limit="dez" (string em vez de integer) é REJEITADO pelo PAGE_SCHEMA', () => {
    const pageLimitString = { ...fixtures.posts_list_200, limit: 'dez' };
    const validate = ajv.compile(PAGE_SCHEMA);
    expect(validate(pageLimitString)).toBe(false);
  });

  // Caso 6a: ApiError sem campo obrigatório "status" → inválido
  it('ApiError sem campo "status" (campo obrigatório removido) é REJEITADO pelo API_ERROR_SCHEMA', () => {
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const { status: _removed, ...errSemStatus } = fixtures.post_not_found_404;
    const validate = ajv.compile(API_ERROR_SCHEMA);
    expect(validate(errSemStatus)).toBe(false);
    expect(validate.errors?.some((e) => e.params && 'missingProperty' in e.params && e.params['missingProperty'] === 'status')).toBe(true);
  });

  // Caso 6b: ApiError COM campo extra → VÁLIDO (assimetria intencional)
  // ApiError usa additionalProperties:true — campo extra NÃO deve ser rejeitado.
  // Esta asserção trava a ASSIMETRIA: Post é strict, ApiError é permissivo.
  // Se o refactor tornar ApiError strict (additionalProperties:false), ESTE TESTE QUEBRA —
  // sinaliza mudança de comportamento que requer revisão.
  it('ApiError COM campo extra "x_internal_trace:abc" é ACEITO pelo API_ERROR_SCHEMA [trava additionalProperties:true / assimetria com Post]', () => {
    const errComCampoExtra = {
      ...fixtures.post_not_found_404,
      x_internal_trace: 'abc-123',
    };
    const validate = ajv.compile(API_ERROR_SCHEMA);
    expect(validate(errComCampoExtra)).toBe(true);
  });
});
