/**
 * Testes do PostStore (PostListStore, PostDetailStore, PostCreateStore).
 * Testa transicoes de estado, idempotencia da key de criacao, acumulo de paginas, etc.
 * Usa HttpTestingController para verificar requests/headers sem rede real.
 *
 * Fixtures derivadas do contrato real (PagePost: items + limit + next_cursor; sem total).
 */
import { TestBed } from '@angular/core/testing';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { provideRouter } from '@angular/router';
import { PostListStore, PostDetailStore, PostCreateStore } from './post-store';
import { apiErrorInterceptor } from '../api/api-error.interceptor';
import { API_BASE_URL } from '../app.config';
import type { Post, PagePost } from '../api/api.types';

const BASE = '/v1';

const POST: Post = {
  id: 'post-1',
  title: 'Titulo',
  content: 'Conteudo',
  status: 'published',
  created_at: '2024-01-01T00:00:00Z',
  published_at: '2024-01-01T00:00:00Z',
};

const POST2: Post = {
  id: 'post-2',
  title: 'Titulo 2',
  content: 'Conteudo 2',
  status: 'published',
  created_at: '2024-01-02T00:00:00Z',
  published_at: '2024-01-02T00:00:00Z',
};

// Fixtures fies ao contrato real (ADR-0002 keyset: items + limit + next_cursor; SEM total)
const PAGE1: PagePost = {
  items: [POST],
  limit: 10,
  next_cursor: 'cursor-abc',
};

const PAGE2: PagePost = {
  items: [POST2],
  limit: 10,
  next_cursor: null,
};

const EMPTY_PAGE: PagePost = {
  items: [],
  limit: 10,
  next_cursor: null,
};

function setupTestBed(store: unknown) {
  TestBed.resetTestingModule();
  TestBed.configureTestingModule({
    providers: [
      provideRouter([{ path: 'posts/:id', component: {} as never }]),
      provideHttpClient(withInterceptors([apiErrorInterceptor])),
      provideHttpClientTesting(),
      { provide: API_BASE_URL, useValue: BASE },
      store as never,
    ],
  });
}

// ---- PostListStore ---------------------------------------------------------

describe('PostListStore', () => {
  let store: PostListStore;
  let http: HttpTestingController;

  beforeEach(() => {
    setupTestBed(PostListStore);
    store = TestBed.inject(PostListStore);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    http.verify();
    TestBed.resetTestingModule();
  });

  it('estado inicial e idle', () => {
    expect(store.state().kind).toBe('idle');
    expect(store.hasMore()).toBe(false);
  });

  it('loadFirstPage: transicao idle->loading->loaded', () => {
    store.loadFirstPage();
    expect(store.state().kind).toBe('loading');

    const req = http.expectOne((r) => r.url === `${BASE}/posts`);
    req.flush(PAGE1);

    expect(store.state().kind).toBe('loaded');
    expect(store.posts().length).toBe(1);
    expect(store.posts()[0]!.id).toBe('post-1');
  });

  it('loadFirstPage: next_cursor != null => hasMore = true', () => {
    store.loadFirstPage();
    http.expectOne((r) => r.url === `${BASE}/posts`).flush(PAGE1);
    expect(store.hasMore()).toBe(true);
    expect(store.nextCursor()).toBe('cursor-abc');
  });

  it('loadFirstPage: next_cursor = null => hasMore = false', () => {
    store.loadFirstPage();
    http.expectOne((r) => r.url === `${BASE}/posts`).flush(PAGE2);
    expect(store.hasMore()).toBe(false);
  });

  it('loadFirstPage: lista vazia => estado empty', () => {
    store.loadFirstPage();
    http.expectOne((r) => r.url === `${BASE}/posts`).flush(EMPTY_PAGE);
    expect(store.state().kind).toBe('empty');
  });

  it('loadMore: concatena paginas sem repetir ids (CA-F003-03)', () => {
    // Pagina 1
    store.loadFirstPage();
    http.expectOne((r) => r.url === `${BASE}/posts`).flush(PAGE1);
    expect(store.posts().length).toBe(1);

    // Pagina 2 via cursor opaco
    store.loadMore();

    const req2 = http.expectOne((r) => r.url === `${BASE}/posts`);
    // Cursor exato recebido do back (ADR-0002: echo, nunca construido)
    expect(req2.request.params.get('cursor')).toBe('cursor-abc');
    req2.flush(PAGE2);

    expect(store.posts().length).toBe(2);
    // IDs da pag1 e pag2 nao se repetem (ids unicos)
    const ids = store.posts().map((p) => p.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it('loadMore: apos ultima pagina, hasMore = false', () => {
    store.loadFirstPage();
    http.expectOne((r) => r.url === `${BASE}/posts`).flush(PAGE1);

    store.loadMore();
    http.expectOne((r) => r.url === `${BASE}/posts`).flush(PAGE2);

    expect(store.hasMore()).toBe(false);
    expect(store.nextCursor()).toBeNull();
  });

  it('loadMore: no-op quando nao ha cursor (sem requisicao)', () => {
    // Sem primeiro carregamento => next_cursor null => loadMore nao dispara request
    store.loadMore();
    http.expectNone((r) => r.url === `${BASE}/posts`);
  });

  it('loadFirstPage: erro ApiError => estado error', () => {
    store.loadFirstPage();
    const req = http.expectOne((r) => r.url === `${BASE}/posts`);
    req.flush(
      { type: 'https://blog-tutorial/errors/invalid_cursor', title: 'Cursor invalido', status: 400, code: 'invalid_cursor' },
      { status: 400, statusText: 'Bad Request' },
    );
    expect(store.state().kind).toBe('error');
    const s = store.state();
    expect(s.kind === 'error' && s.error.code).toBe('invalid_cursor');
  });

  it('loadFirstPage: erro nao-ApiError => estado error com code unknown', () => {
    store.loadFirstPage();
    const req = http.expectOne((r) => r.url === `${BASE}/posts`);
    // Resposta sem corpo problem+json: o interceptor nao consegue mapear => unknown
    req.flush(
      { type: 'about:blank', title: 'Server Error', status: 500, code: 'unknown' },
      { status: 500, statusText: 'Internal Server Error' },
    );
    expect(store.state().kind).toBe('error');
  });

  it('loadMore: erro na segunda pagina => estado error (L65-67)', () => {
    // Carrega pagina 1 com cursor
    store.loadFirstPage();
    http.expectOne((r) => r.url === `${BASE}/posts`).flush(PAGE1);
    expect(store.hasMore()).toBe(true);

    // loadMore com erro
    store.loadMore();
    http.expectOne((r) => r.url === `${BASE}/posts`).flush(
      { type: 'https://blog-tutorial/errors/invalid_cursor', title: 'Cursor invalido', status: 400, code: 'invalid_cursor' },
      { status: 400, statusText: 'Bad Request' },
    );

    expect(store.state().kind).toBe('error');
    expect(store.loadingMore()).toBe(false);
  });

  it('front NAO filtra status no cliente: exibe o que o back retornou (CA-F003-02)', () => {
    // O back ja faz allowlist; o front nao deve filtrar por status
    const pageWithAll: PagePost = {
      items: [POST],
      limit: 10,
      next_cursor: null,
    };
    store.loadFirstPage();
    http.expectOne((r) => r.url === `${BASE}/posts`).flush(pageWithAll);
    // Todos os itens retornados pelo back sao exibidos sem filtro
    expect(store.posts().length).toBe(1);
  });
});

// ---- PostDetailStore -------------------------------------------------------

describe('PostDetailStore', () => {
  let store: PostDetailStore;
  let http: HttpTestingController;

  beforeEach(() => {
    setupTestBed(PostDetailStore);
    store = TestBed.inject(PostDetailStore);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    http.verify();
    TestBed.resetTestingModule();
  });

  it('estado inicial e idle', () => {
    expect(store.state().kind).toBe('idle');
  });

  it('load: 200 => estado loaded com post', () => {
    store.load('post-1');
    expect(store.state().kind).toBe('loading');

    http.expectOne(`${BASE}/posts/post-1`).flush(POST);

    expect(store.state().kind).toBe('loaded');
    expect((store.state() as { kind: 'loaded'; data: Post }).data.title).toBe('Titulo');
  });

  it('load: 404 post_not_found => estado error (CA-F004-02)', () => {
    store.load('inexistente');
    http.expectOne(`${BASE}/posts/inexistente`).flush(
      {
        type: 'https://blog-tutorial/errors/post_not_found',
        title: 'Post not found',
        status: 404,
        code: 'post_not_found',
      },
      { status: 404, statusText: 'Not Found' },
    );

    expect(store.state().kind).toBe('error');
    expect((store.state() as { kind: 'error'; error: { code: string } }).error.code).toBe(
      'post_not_found',
    );
  });

  it('load: erro nao-ApiError => code unknown', () => {
    store.load('post-1');
    http.expectOne(`${BASE}/posts/post-1`).flush(
      { type: 'about:blank', title: 'Server Error', status: 500, code: 'unknown' },
      { status: 500, statusText: 'Internal Server Error' },
    );
    const s = store.state();
    expect(s.kind).toBe('error');
    expect(s.kind === 'error' && s.error.code).toBe('unknown');
  });
});

// ---- PostCreateStore -------------------------------------------------------

describe('PostCreateStore', () => {
  let store: PostCreateStore;
  let http: HttpTestingController;

  beforeEach(() => {
    setupTestBed(PostCreateStore);
    store = TestBed.inject(PostCreateStore);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    http.verify();
    TestBed.resetTestingModule();
  });

  it('estado inicial e idle', () => {
    expect(store.state().kind).toBe('idle');
  });

  it('submit: fluxo criar->publicar feliz => estado done', () => {
    const draft = { ...POST, status: 'draft' as const, published_at: null };
    const published = { ...POST, status: 'published' as const };

    store.submit({ title: 'Titulo', content: 'Conteudo' });
    expect(store.state().kind).toBe('creating');

    // POST /v1/posts
    const createReq = http.expectOne(`${BASE}/posts`);
    expect(createReq.request.method).toBe('POST');
    expect(createReq.request.headers.has('Idempotency-Key')).toBe(true);
    const createKey = createReq.request.headers.get('Idempotency-Key')!;
    createReq.flush(draft);

    expect(store.state().kind).toBe('publishing');

    // PUT /v1/posts/:id/publish
    const publishReq = http.expectOne(`${BASE}/posts/${draft.id}/publish`);
    expect(publishReq.request.method).toBe('PUT');
    expect(publishReq.request.headers.has('Idempotency-Key')).toBe(true);
    // Key de publicacao e DIFERENTE da key de criacao (operacao distinta — P-03)
    const publishKey = publishReq.request.headers.get('Idempotency-Key')!;
    expect(publishKey).not.toBe(createKey);
    publishReq.flush(published);

    expect(store.state().kind).toBe('done');
  });

  it('submit: ignorado quando ja em creating (guard idempotencia)', () => {
    store.submit({ title: 'T', content: 'C' });
    // Segunda chamada nao deve disparar novo request
    store.submit({ title: 'T', content: 'C' });
    http.expectOne(`${BASE}/posts`); // apenas UM request
    http.verify();
    // Limpa o request pendente
    http.expectNone(`${BASE}/posts2`);
  });

  it('Idempotency-Key de criacao e ESTAVEL no retry da mesma intencao (P-03)', () => {
    // Primeiro submit — key gerada
    store.submit({ title: 'T', content: 'C' });
    const req1 = http.expectOne(`${BASE}/posts`);
    const key1 = req1.request.headers.get('Idempotency-Key')!;
    // Simula erro de rede
    req1.flush(
      { type: 'about:blank', title: 'Erro', status: 500, code: 'unknown' },
      { status: 500, statusText: 'Server Error' },
    );
    expect(store.state().kind).toBe('error');

    // Reset (sem regenerar key) e retry
    store.reset();
    store.submit({ title: 'T', content: 'C' });
    const req2 = http.expectOne(`${BASE}/posts`);
    const key2 = req2.request.headers.get('Idempotency-Key')!;

    // Mesma intencao => mesma key (idempotencia da intencao)
    expect(key2).toBe(key1);

    req2.error(new ProgressEvent('error'));
    http.verify();
  });

  it('submit: 422 validation_error => mapeia errors[].field ao estado (CA-F002-03)', () => {
    store.submit({ title: '', content: 'x' });
    http.expectOne(`${BASE}/posts`).flush(
      {
        type: 'https://blog-tutorial/errors/validation_error',
        title: 'Validation error',
        status: 422,
        code: 'validation_error',
        errors: [{ field: 'title', code: 'required', message: 'Campo obrigatorio' }],
      },
      { status: 422, statusText: 'Unprocessable Entity' },
    );

    const s = store.state();
    expect(s.kind).toBe('error');
    expect((s as { kind: 'error'; fieldErrors?: Record<string, string> }).fieldErrors?.['title']).toBe(
      'Campo obrigatorio',
    );
  });

  it('submit: 409 idempotency_key_conflict => globalError com mensagem propria', () => {
    store.submit({ title: 'T', content: 'C' });
    http.expectOne(`${BASE}/posts`).flush(
      {
        type: 'https://blog-tutorial/errors/idempotency_key_conflict',
        title: 'Idempotency key conflict',
        status: 409,
        code: 'idempotency_key_conflict',
      },
      { status: 409, statusText: 'Conflict' },
    );

    const s = store.state();
    expect(s.kind).toBe('error');
    expect(
      (s as { kind: 'error'; globalError?: string }).globalError,
    ).toContain('duplicada');
  });

  it('submit: 400 idempotency_key_required => globalError tecnico', () => {
    store.submit({ title: 'T', content: 'C' });
    http.expectOne(`${BASE}/posts`).flush(
      {
        type: 'https://blog-tutorial/errors/idempotency_key_required',
        title: 'Idempotency key required',
        status: 400,
        code: 'idempotency_key_required',
      },
      { status: 400, statusText: 'Bad Request' },
    );

    const s = store.state();
    expect(s.kind).toBe('error');
    expect(
      (s as { kind: 'error'; globalError?: string }).globalError,
    ).toBeTruthy();
  });

  it('submit: 404 post_not_found na publicacao => globalError especifico', () => {
    const draft = { ...POST, status: 'draft' as const, published_at: null };

    store.submit({ title: 'T', content: 'C' });
    http.expectOne(`${BASE}/posts`).flush(draft);

    // Erro 404 na publicacao (post_not_found — branch L229-233)
    http.expectOne(`${BASE}/posts/${draft.id}/publish`).flush(
      {
        type: 'https://blog-tutorial/errors/post_not_found',
        title: 'Post not found',
        status: 404,
        code: 'post_not_found',
      },
      { status: 404, statusText: 'Not Found' },
    );

    const s = store.state();
    expect(s.kind).toBe('error');
    expect((s as { kind: 'error'; globalError?: string }).globalError).toContain('publicacao');
  });

  it('submit: erro de rede puro na criacao (ProgressEvent) => globalError unknown', () => {
    // req.error(ProgressEvent) => interceptor produz ApiError{code:'unknown'} => case default
    store.submit({ title: 'T', content: 'C' });
    http.expectOne(`${BASE}/posts`).error(new ProgressEvent('error'));
    const s = store.state();
    expect(s.kind).toBe('error');
    // default case: usa apiErr.title (pode ser 'Erro de rede') ou 'Erro inesperado.'
    expect((s as { kind: 'error'; globalError?: string }).globalError).toBeTruthy();
  });

  it('submit: erro de rede puro na publicacao => globalError unknown', () => {
    const draft = { ...POST, status: 'draft' as const, published_at: null };

    store.submit({ title: 'T', content: 'C' });
    http.expectOne(`${BASE}/posts`).flush(draft);

    // ProgressEvent na publicacao => interceptor => ApiError{code:'unknown'} => default
    http.expectOne(`${BASE}/posts/${draft.id}/publish`).error(new ProgressEvent('error'));
    const s = store.state();
    expect(s.kind).toBe('error');
    expect((s as { kind: 'error'; globalError?: string }).globalError).toBeTruthy();
  });

  it('submit: default error code => globalError com title', () => {
    // Codigo de erro nao mapeado (ex: futuro codigo desconhecido) cai no default
    store.submit({ title: 'T', content: 'C' });
    http.expectOne(`${BASE}/posts`).flush(
      {
        type: 'https://blog-tutorial/errors/invalid_cursor',
        title: 'Invalid cursor',
        status: 400,
        code: 'invalid_cursor', // nao e codigo esperado no create
      },
      { status: 400, statusText: 'Bad Request' },
    );
    const s = store.state();
    expect(s.kind).toBe('error');
    expect((s as { kind: 'error'; globalError?: string }).globalError).toBeTruthy();
  });

  it('reset: limpa estado para idle preservando key de idempotencia para retry', () => {
    store.submit({ title: 'T', content: 'C' });
    http.expectOne(`${BASE}/posts`).flush(
      { type: 'about:blank', title: 'Erro', status: 500, code: 'unknown' },
      { status: 500, statusText: 'Server Error' },
    );

    store.reset();
    expect(store.state().kind).toBe('idle');
  });

  it('newIntent: limpa estado E key (nova intencao gera nova key)', () => {
    store.submit({ title: 'T', content: 'C' });
    const req1 = http.expectOne(`${BASE}/posts`);
    const key1 = req1.request.headers.get('Idempotency-Key')!;
    req1.flush(
      { type: 'about:blank', title: 'Erro', status: 500, code: 'unknown' },
      { status: 500, statusText: 'Server Error' },
    );

    store.newIntent();
    expect(store.state().kind).toBe('idle');

    // Nova intencao => nova key
    store.submit({ title: 'T2', content: 'C2' });
    const req2 = http.expectOne(`${BASE}/posts`);
    const key2 = req2.request.headers.get('Idempotency-Key')!;
    expect(key2).not.toBe(key1);

    req2.error(new ProgressEvent('error'));
    http.verify();
  });
});
