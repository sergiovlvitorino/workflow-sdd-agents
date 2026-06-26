/**
 * Testes unitarios do BlogApiService.
 *
 * Usa HttpTestingController (provideHttpClientTesting) para interceptar requisicoes
 * na borda — sem rede real, mas cobrindo o wiring de DI (007 §1).
 *
 * Cobre:
 * - URL correta para cada metodo (/v1/posts, /v1/posts/{id}, etc.)
 * - Idempotency-Key presente nas escritas (P-03)
 * - Mapeamento de resposta para os tipos corretos (Post, PagePost)
 * - Propagacao de ApiError via interceptor (erro tipado, nunca HttpErrorResponse cru)
 */
import { TestBed } from '@angular/core/testing';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { BlogApiService } from './blog-api.service';
import { API_BASE_URL } from '../app.config';
import { apiErrorInterceptor } from './api-error.interceptor';
import { isApiError } from './api-error';
import type { Post, PagePost, CreatePostRequest } from './api.types';

const BASE = '/v1';

const FIXTURE_POST: Post = {
  id: '01J9Z3K7Q2M4N5P6R7S8T9V0W1',
  title: 'Post de teste',
  content: 'Conteudo de teste.',
  status: 'draft',
  created_at: '2026-06-24T14:30:00Z',
  published_at: null,
};

const FIXTURE_POST_PUBLISHED: Post = {
  ...FIXTURE_POST,
  status: 'published',
  published_at: '2026-06-25T10:00:00Z',
};

const FIXTURE_PAGE: PagePost = {
  items: [FIXTURE_POST_PUBLISHED],
  next_cursor: 'eyJwIjoiMjAyNiJ9',
  limit: 10,
};

describe('BlogApiService', () => {
  let service: BlogApiService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([apiErrorInterceptor])),
        provideHttpClientTesting(),
        BlogApiService,
        { provide: API_BASE_URL, useValue: BASE },
      ],
    });
    service = TestBed.inject(BlogApiService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
    TestBed.resetTestingModule();
  });

  // --- listPosts ---

  it('listPosts: GET /v1/posts sem params', () => {
    let result: PagePost | undefined;
    service.listPosts().subscribe((r) => (result = r));

    const req = httpMock.expectOne(`${BASE}/posts`);
    expect(req.request.method).toBe('GET');
    req.flush(FIXTURE_PAGE);

    expect(result).toEqual(FIXTURE_PAGE);
  });

  it('listPosts: envia limit e cursor como query params', () => {
    service.listPosts({ limit: 5, cursor: 'token123' }).subscribe();

    const req = httpMock.expectOne((r) => r.url === `${BASE}/posts`);
    expect(req.request.params.get('limit')).toBe('5');
    expect(req.request.params.get('cursor')).toBe('token123');
    req.flush(FIXTURE_PAGE);
  });

  it('listPosts: next_cursor null preservado (ultima pagina)', () => {
    const lastPage: PagePost = { items: [], next_cursor: null, limit: 10 };
    let result: PagePost | undefined;
    service.listPosts().subscribe((r) => (result = r));

    httpMock.expectOne(`${BASE}/posts`).flush(lastPage);
    expect(result?.next_cursor).toBeNull();
  });

  // --- getPost ---

  it('getPost: GET /v1/posts/{id}', () => {
    let result: Post | undefined;
    service.getPost(FIXTURE_POST_PUBLISHED.id).subscribe((r) => (result = r));

    const req = httpMock.expectOne(`${BASE}/posts/${FIXTURE_POST_PUBLISHED.id}`);
    expect(req.request.method).toBe('GET');
    req.flush(FIXTURE_POST_PUBLISHED);

    expect(result?.status).toBe('published');
    expect(result?.published_at).toBe('2026-06-25T10:00:00Z');
  });

  it('getPost: published_at null preservado quando draft', () => {
    // O interceptor retorna ApiError para 404 — aqui testamos a resposta 200 com published_at=null
    let result: Post | undefined;
    service.getPost('draft-id').subscribe((r) => (result = r));

    httpMock.expectOne(`${BASE}/posts/draft-id`).flush(FIXTURE_POST);
    expect(result?.published_at).toBeNull();
  });

  // --- createPost ---

  it('createPost: POST /v1/posts com Idempotency-Key', () => {
    const body: CreatePostRequest = { title: 'Novo post', content: 'Conteudo.' };
    let result: Post | undefined;
    const key = 'minha-chave-123';

    service.createPost(body, key).subscribe((r) => (result = r));

    const req = httpMock.expectOne(`${BASE}/posts`);
    expect(req.request.method).toBe('POST');
    expect(req.request.headers.get('Idempotency-Key')).toBe(key);
    expect(req.request.body).toEqual(body);
    req.flush({ ...FIXTURE_POST, title: body.title }, { status: 201, statusText: 'Created' });

    expect(result?.title).toBe('Novo post');
  });

  it('createPost: gera Idempotency-Key automaticamente quando nao fornecida', () => {
    const body: CreatePostRequest = { title: 'Auto key', content: 'Conteudo.' };
    service.createPost(body).subscribe();

    const req = httpMock.expectOne(`${BASE}/posts`);
    const key = req.request.headers.get('Idempotency-Key');
    expect(key).toBeTruthy();
    // UUID v4: 8-4-4-4-12 hex
    expect(key).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i);
    req.flush(FIXTURE_POST, { status: 201, statusText: 'Created' });
  });

  // --- publishPost ---

  it('publishPost: PUT /v1/posts/{id}/publish com Idempotency-Key', () => {
    const id = FIXTURE_POST.id;
    const key = 'publish-key-456';
    let result: Post | undefined;

    service.publishPost(id, key).subscribe((r) => (result = r));

    const req = httpMock.expectOne(`${BASE}/posts/${id}/publish`);
    expect(req.request.method).toBe('PUT');
    expect(req.request.headers.get('Idempotency-Key')).toBe(key);
    req.flush(FIXTURE_POST_PUBLISHED);

    expect(result?.status).toBe('published');
    expect(result?.published_at).toBeTruthy();
  });

  it('publishPost: gera Idempotency-Key automaticamente quando nao fornecida', () => {
    service.publishPost('some-id').subscribe();

    const req = httpMock.expectOne(`${BASE}/posts/some-id/publish`);
    const key = req.request.headers.get('Idempotency-Key');
    expect(key).toBeTruthy();
    expect(key).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i);
    req.flush(FIXTURE_POST_PUBLISHED);
  });

  // --- Mapeamento de erros via interceptor ---

  it('listPosts: erro 400 invalid_cursor mapeado para ApiError', () => {
    let error: unknown;
    service.listPosts({ cursor: 'invalido' }).subscribe({ error: (e) => (error = e) });

    httpMock.expectOne((r) => r.url === `${BASE}/posts`).flush(
      {
        type: 'https://blog-tutorial/errors/invalid_cursor',
        title: 'Cursor invalido',
        status: 400,
        detail: 'O cursor fornecido e invalido.',
      },
      { status: 400, statusText: 'Bad Request', headers: { 'content-type': 'application/problem+json' } },
    );

    expect(isApiError(error)).toBe(true);
    if (isApiError(error)) {
      expect(error.code).toBe('invalid_cursor');
      expect(error.status).toBe(400);
    }
  });

  it('createPost: erro 409 idempotency_key_conflict mapeado para ApiError', () => {
    let error: unknown;
    service.createPost({ title: 'T', content: 'C' }, 'dup-key').subscribe({ error: (e) => (error = e) });

    httpMock.expectOne(`${BASE}/posts`).flush(
      {
        type: 'https://blog-tutorial/errors/idempotency_key_conflict',
        title: 'Conflito de idempotencia',
        status: 409,
      },
      { status: 409, statusText: 'Conflict', headers: { 'content-type': 'application/problem+json' } },
    );

    expect(isApiError(error)).toBe(true);
    if (isApiError(error)) {
      expect(error.code).toBe('idempotency_key_conflict');
    }
  });

  it('getPost: erro 404 post_not_found mapeado para ApiError', () => {
    let error: unknown;
    service.getPost('inexistente').subscribe({ error: (e) => (error = e) });

    httpMock.expectOne(`${BASE}/posts/inexistente`).flush(
      {
        type: 'https://blog-tutorial/errors/post_not_found',
        title: 'Post nao encontrado',
        status: 404,
      },
      { status: 404, statusText: 'Not Found', headers: { 'content-type': 'application/problem+json' } },
    );

    expect(isApiError(error)).toBe(true);
    if (isApiError(error)) {
      expect(error.code).toBe('post_not_found');
      expect(error.status).toBe(404);
    }
  });

  it('createPost: erro 422 validation_error com errors[] mapeado para ApiError', () => {
    let error: unknown;
    service.createPost({ title: '', content: 'C' }).subscribe({ error: (e) => (error = e) });

    httpMock.expectOne(`${BASE}/posts`).flush(
      {
        type: 'https://blog-tutorial/errors/validation_error',
        title: 'Erro de validacao',
        status: 422,
        errors: [{ field: 'title', code: 'missing', message: 'Field required' }],
      },
      { status: 422, statusText: 'Unprocessable Entity', headers: { 'content-type': 'application/problem+json' } },
    );

    expect(isApiError(error)).toBe(true);
    if (isApiError(error)) {
      expect(error.code).toBe('validation_error');
      expect(error.errors).toHaveLength(1);
      expect(error.errors?.[0]?.field).toBe('title');
    }
  });

  it('publishPost: erro 400 idempotency_key_required mapeado para ApiError', () => {
    let error: unknown;
    // Simulando resposta do backend quando Idempotency-Key estava ausente
    service.publishPost('some-id', 'qualquer').subscribe({ error: (e) => (error = e) });

    httpMock.expectOne(`${BASE}/posts/some-id/publish`).flush(
      {
        type: 'https://blog-tutorial/errors/idempotency_key_required',
        title: 'Idempotency-Key obrigatoria',
        status: 400,
      },
      { status: 400, statusText: 'Bad Request', headers: { 'content-type': 'application/problem+json' } },
    );

    expect(isApiError(error)).toBe(true);
    if (isApiError(error)) {
      expect(error.code).toBe('idempotency_key_required');
    }
  });

  it('erro de rede (status 0) resulta em code: unknown', () => {
    let error: unknown;
    service.listPosts().subscribe({ error: (e) => (error = e) });

    httpMock.expectOne(`${BASE}/posts`).error(new ProgressEvent('error'));

    expect(isApiError(error)).toBe(true);
    if (isApiError(error)) {
      expect(error.code).toBe('unknown');
      expect(error.status).toBe(0);
    }
  });
});
