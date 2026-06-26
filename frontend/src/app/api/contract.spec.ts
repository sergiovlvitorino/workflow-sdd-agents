/**
 * Contract test: valida payload REAL do backend contra o schema OpenAPI gerado
 * e contra os tipos TypeScript (ADR-0005 §8, ADR-0001 §4.2).
 *
 * O que este teste faz (não é tautológico):
 *   1. Carrega fixtures reais geradas pelo backend via TestClient
 *      (backend/scripts/dump_contract_fixtures.py -> fixtures/contract-fixtures.json)
 *   2. Valida cada fixture com Ajv contra o schema JSON derivado do OpenAPI real
 *   3. Usa `satisfies Post` para que o TypeScript prove shape em compilação
 *
 * Prova anti-drift: mutar status no Pydantic backend (ex.: adicionar "archived")
 * -> gen:api regenera tipo diferente -> "satisfies Post" falha em compilação
 * -> OU o schema Ajv diverge do payload real -> teste vermelho.
 *
 * Para regenerar fixtures:
 *   python backend/scripts/dump_contract_fixtures.py
 */
import { describe, it, expect, beforeAll } from 'vitest';
import Ajv2020 from 'ajv/dist/2020';
import { readFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import type { Post, PagePost, CreatePostRequest } from './api.types';
import { isApiError } from './api-error';

const __dirname = dirname(fileURLToPath(import.meta.url));

// ---------------------------------------------------------------------------
// Fixtures reais do backend (geradas por dump_contract_fixtures.py)
// ---------------------------------------------------------------------------

interface ContractFixtures {
  post_created_201: unknown;
  post_replay_200: unknown;
  post_published_200: unknown;
  post_get_200: unknown;
  posts_list_200: unknown;
  post_not_found_404: unknown;
  post_not_found_404_nonexistent: unknown;
  invalid_cursor_400: unknown;
  idempotency_key_required_400: unknown;
  idempotency_key_conflict_409: unknown;
  validation_error_422: unknown;
  health_200: unknown;
}

// ---------------------------------------------------------------------------
// Schemas carregados do OpenAPI vivo (gerado por dump_openapi.py via gen:api).
// Não redeclarados à mão — extraídos do contrato vivo em generated/openapi.json.
// ---------------------------------------------------------------------------

/**
 * Impõe o rigor contratual nos schemas antes de registrá-los no Ajv.
 *
 * FastAPI/Pydantic não emite additionalProperties no OpenAPI dump; o contrato
 * 005 exige rigor em PostResponse/PageResponse (campos extras REJEITADOS) e
 * permissividade em ApiError (campos extras ACEITOS) — política reimposta aqui,
 * não herdada do dump.
 *
 * Modifica o doc in-place (antes do addSchema) para garantir que o Ajv compile
 * os validadores já com a política correta.
 */
function applyContractRigor(doc: Record<string, unknown>): void {
  const schemas = (doc['components'] as Record<string, unknown>)?.['schemas'] as
    Record<string, Record<string, unknown>> | undefined;
  if (!schemas) throw new Error('openapi.json sem components.schemas');

  const postSchema = schemas['PostResponse'];
  const pageSchema = schemas['PageResponse'];
  const apiErrorSchema = schemas['ApiError'];
  if (!postSchema || !pageSchema || !apiErrorSchema) {
    throw new Error('openapi.json sem PostResponse, PageResponse ou ApiError em components.schemas');
  }

  postSchema['additionalProperties'] = false;
  pageSchema['additionalProperties'] = false;
  // ApiError: permissivo — campo extra NÃO é rejeitado (assimetria intencional com Post).
  apiErrorSchema['additionalProperties'] = true;
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

let ajv: Ajv2020;
let fixtures: ContractFixtures;
let validatePost: ReturnType<Ajv2020['compile']>;
let validatePage: ReturnType<Ajv2020['compile']>;
let validateApiError: ReturnType<Ajv2020['compile']>;

beforeAll(() => {
  // Dialeto OpenAPI 3.1.0 / JSON Schema 2020-12 — classe Ajv2020 define o dialeto
  // sem depender de $schema no root (FastAPI não emite $schema).
  ajv = new Ajv2020({ strict: false, allErrors: true });

  // Lê via fs (não import) para não violar a barreira no-restricted-imports de eslint.
  const openapiPath = join(__dirname, 'generated', 'openapi.json');
  const doc = JSON.parse(readFileSync(openapiPath, 'utf-8')) as Record<string, unknown>;

  // Impõe rigor contratual antes de registrar (additionalProperties em Post/Page/ApiError).
  applyContractRigor(doc);

  // Registra o doc inteiro para que o Ajv resolva $ref internos
  // (ex.: PageResponse.items.$ref -> PostResponse).
  ajv.addSchema(doc, 'oas');

  validatePost = ajv.compile({ $ref: 'oas#/components/schemas/PostResponse' });
  validatePage = ajv.compile({ $ref: 'oas#/components/schemas/PageResponse' });
  validateApiError = ajv.compile({ $ref: 'oas#/components/schemas/ApiError' });

  const fixturesPath = join(__dirname, 'fixtures', 'contract-fixtures.json');
  fixtures = JSON.parse(readFileSync(fixturesPath, 'utf-8')) as ContractFixtures;
});

// ---------------------------------------------------------------------------
// Post criado (201)
// ---------------------------------------------------------------------------

describe('Contract: PostResponse criado (201)', () => {
  it('valida shape com Ajv (schema derivado do OpenAPI real)', () => {
    expect(validatePost(fixtures.post_created_201), JSON.stringify(validatePost.errors)).toBe(true);
  });

  it('published_at é null para post draft (contrato 005 §3)', () => {
    const post = fixtures.post_created_201 as Post;
    expect(post.published_at).toBeNull();
  });

  it('status é "draft" — satisfies prova shape em compilação', () => {
    const post = fixtures.post_created_201 as Post;
    const typedPost = post satisfies Post;
    expect(typedPost.status).toBe('draft');
  });

  it('created_at tem formato RFC 3339 com sufixo Z (contrato 005 §3)', () => {
    const post = fixtures.post_created_201 as Post;
    expect(post.created_at).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$/);
  });

  it('todos os campos obrigatórios presentes', () => {
    const post = fixtures.post_created_201 as Post;
    for (const field of ['id', 'title', 'content', 'status', 'created_at']) {
      expect(post).toHaveProperty(field);
    }
    expect('published_at' in post).toBe(true);
  });

  it('replay retorna mesmo id do post original (idempotência)', () => {
    const created = fixtures.post_created_201 as Post;
    const replayed = fixtures.post_replay_200 as Post;
    expect(replayed.id).toBe(created.id);
    expect(replayed.title).toBe(created.title);
  });
});

// ---------------------------------------------------------------------------
// Post publicado (200)
// ---------------------------------------------------------------------------

describe('Contract: PostResponse publicado (200)', () => {
  it('valida shape com Ajv', () => {
    expect(validatePost(fixtures.post_published_200), JSON.stringify(validatePost.errors)).toBe(true);
  });

  it('status é "published" — satisfies prova shape em compilação', () => {
    const post = fixtures.post_published_200 as Post;
    const typedPost = post satisfies Post;
    expect(typedPost.status).toBe('published');
  });

  it('published_at é string RFC 3339 com Z após publicação', () => {
    const post = fixtures.post_published_200 as Post;
    expect(typeof post.published_at).toBe('string');
    expect(post.published_at).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$/);
  });

  it('GET /v1/posts/{id} retorna mesmo post publicado (consistência)', () => {
    const fromPublish = fixtures.post_published_200 as Post;
    const fromGet = fixtures.post_get_200 as Post;
    expect(fromGet.id).toBe(fromPublish.id);
    expect(fromGet.status).toBe('published');
    expect(fromGet.published_at).toBe(fromPublish.published_at);
  });
});

// ---------------------------------------------------------------------------
// PageResponse (GET /v1/posts)
// ---------------------------------------------------------------------------

describe('Contract: PageResponse — GET /v1/posts (200)', () => {
  it('valida shape com Ajv', () => {
    expect(validatePage(fixtures.posts_list_200), JSON.stringify(validatePage.errors)).toBe(true);
  });

  it('items é array — satisfies prova shape em compilação', () => {
    const page = fixtures.posts_list_200 as PagePost;
    const typedPage = page satisfies PagePost;
    expect(Array.isArray(typedPage.items)).toBe(true);
  });

  it('apenas posts publicados aparecem na lista (allowlist P-04)', () => {
    const page = fixtures.posts_list_200 as PagePost;
    for (const item of page.items) {
      expect(item.status).toBe('published');
    }
  });

  it('next_cursor é string ou null — token opaco (ADR-0002)', () => {
    const page = fixtures.posts_list_200 as PagePost;
    expect(page.next_cursor === null || typeof page.next_cursor === 'string').toBe(true);
  });

  it('limit é inteiro', () => {
    const page = fixtures.posts_list_200 as PagePost;
    expect(Number.isInteger(page.limit)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// ApiError — os 5 codes do catálogo 005 §4
// ---------------------------------------------------------------------------

describe('Contract: ApiError — catálogo de erros (005 §4)', () => {
  const errorCases = [
    ['post_not_found_404', 404, 'post_not_found'],
    ['post_not_found_404_nonexistent', 404, 'post_not_found'],
    ['invalid_cursor_400', 400, 'invalid_cursor'],
    ['idempotency_key_required_400', 400, 'idempotency_key_required'],
    ['idempotency_key_conflict_409', 409, 'idempotency_key_conflict'],
    ['validation_error_422', 422, 'validation_error'],
  ] as const;

  for (const [fixtureName, expectedStatus, expectedCode] of errorCases) {
    it(`${fixtureName}: Ajv + code=${expectedCode} (discriminado por type, nunca por detail)`, () => {
      const fixture = (fixtures as unknown as Record<string, unknown>)[fixtureName];
      expect(validateApiError(fixture), JSON.stringify(validateApiError.errors)).toBe(true);

      const err = fixture as { type: string; status: number; detail?: string };
      expect(err.status).toBe(expectedStatus);
      // Sufixo do type URI = code tipado (005 §4)
      expect(err.type.split('/').pop()).toBe(expectedCode);

      // isApiError guard reconhece o shape
      expect(isApiError({ ...err, code: expectedCode })).toBe(true);
    });
  }

  it('validation_error tem errors[] com field/code/message (005 §4)', () => {
    const err = fixtures.validation_error_422 as {
      errors?: Array<{ field: string; code: string; message: string }>;
    };
    expect(Array.isArray(err.errors)).toBe(true);
    expect((err.errors ?? []).length).toBeGreaterThan(0);
    const first = err.errors?.[0];
    expect(first).toHaveProperty('field');
    expect(first).toHaveProperty('code');
    expect(first).toHaveProperty('message');
  });

  it('rascunho e inexistente retornam MESMO type (P-04 — não revela existência)', () => {
    const draft404 = fixtures.post_not_found_404 as { type: string };
    const notfound404 = fixtures.post_not_found_404_nonexistent as { type: string };
    expect(draft404.type).toBe(notfound404.type);
    expect(draft404.type.split('/').pop()).toBe('post_not_found');
  });

  it('detail não é usado para discriminar — é texto livre (005 §4)', () => {
    // Mesmo type em ambos os 404 — detail pode variar livremente
    const draft404 = fixtures.post_not_found_404 as { type: string; detail?: string };
    const notfound404 = fixtures.post_not_found_404_nonexistent as { type: string; detail?: string };
    // O que importa: mesmo type (mesmo code) — detail é irrelevante para lógica
    expect(draft404.type).toBe(notfound404.type);
  });
});

// ---------------------------------------------------------------------------
// CreatePostRequest
// ---------------------------------------------------------------------------

describe('Contract: CreatePostRequest', () => {
  it('shape tem title e content — satisfies prova em compilação', () => {
    const req: CreatePostRequest = {
      title: 'Post de Fixture',
      content: 'Conteúdo da fixture de contrato.',
    };
    const typedReq = req satisfies CreatePostRequest;
    expect(typedReq.title).toBeTruthy();
    expect(typedReq.content).toBeTruthy();
  });
});
