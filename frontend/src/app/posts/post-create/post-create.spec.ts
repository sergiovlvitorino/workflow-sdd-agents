/**
 * Testes do PostCreateComponent (CA-F001/F002).
 * Testing Library + HttpTestingController.
 * Verifica: criar->publicar feliz, Idempotency-Key estavel no retry, 422 mapeia campos,
 * 400/409 exibidos por code.
 */
import { TestBed } from '@angular/core/testing';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideRouter } from '@angular/router';
import { describe, it, expect, afterEach } from 'vitest';
import { render, screen } from '@testing-library/angular';
import userEvent from '@testing-library/user-event';
import { PostCreateComponent } from './post-create';
import { apiErrorInterceptor } from '../../api/api-error.interceptor';
import { API_BASE_URL } from '../../app.config';
import type { Post } from '../../api/api.types';

const BASE = '/v1';

const DRAFT: Post = {
  id: 'post-new',
  title: 'Novo Post',
  content: 'Conteudo novo',
  status: 'draft',
  created_at: '2024-01-01T00:00:00Z',
  published_at: null,
};

const PUBLISHED: Post = { ...DRAFT, status: 'published', published_at: '2024-01-01T00:00:00Z' };

const providers = [
  provideRouter([{ path: 'posts/:id', component: PostCreateComponent }]),
  provideHttpClient(withInterceptors([apiErrorInterceptor])),
  provideHttpClientTesting(),
  { provide: API_BASE_URL, useValue: BASE },
];

async function renderComponent() {
  TestBed.resetTestingModule();
  const result = await render(PostCreateComponent, { providers });
  const http = TestBed.inject(HttpTestingController);
  return { ...result, http };
}

describe('PostCreateComponent', () => {
  afterEach(() => {
    TestBed.resetTestingModule();
  });

  it('exibe formulario com campos titulo e conteudo', async () => {
    const { http } = await renderComponent();

    expect(screen.getByLabelText(/titulo/i)).toBeTruthy();
    expect(screen.getByLabelText(/conteudo/i)).toBeTruthy();
    expect(screen.getByRole('button', { name: /criar e publicar/i })).toBeTruthy();
    http.verify();
  });

  it('botao desabilitado com form invalido', async () => {
    const { http } = await renderComponent();

    const btn = screen.getByRole('button', { name: /criar e publicar/i }) as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
    http.verify();
  });

  it('fluxo feliz: cria -> publica -> estado done (CA-F001/F002)', async () => {
    const { http, detectChanges } = await renderComponent();
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/titulo/i), 'Novo Post');
    await user.type(screen.getByLabelText(/conteudo/i), 'Conteudo novo');
    await user.click(screen.getByRole('button', { name: /criar e publicar/i }));

    // POST /v1/posts com Idempotency-Key
    const createReq = http.expectOne(`${BASE}/posts`);
    expect(createReq.request.method).toBe('POST');
    expect(createReq.request.headers.has('Idempotency-Key')).toBe(true);
    const createKey = createReq.request.headers.get('Idempotency-Key')!;
    expect(createKey).toBeTruthy();
    createReq.flush(DRAFT);
    detectChanges();

    // PUT /v1/posts/:id/publish com OUTRA Idempotency-Key
    const publishReq = http.expectOne(`${BASE}/posts/${DRAFT.id}/publish`);
    expect(publishReq.request.method).toBe('PUT');
    const publishKey = publishReq.request.headers.get('Idempotency-Key')!;
    // Keys distintas: criacao e publicacao sao operacoes separadas (P-03)
    expect(publishKey).not.toBe(createKey);
    publishReq.flush(PUBLISHED);
    detectChanges();

    http.verify();
  });

  it('Idempotency-Key de criacao e estavel no retry da mesma intencao (P-03)', async () => {
    const { http, detectChanges } = await renderComponent();
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/titulo/i), 'T');
    await user.type(screen.getByLabelText(/conteudo/i), 'C');
    await user.click(screen.getByRole('button', { name: /criar e publicar/i }));

    // Primeiro submit - captura key
    const req1 = http.expectOne(`${BASE}/posts`);
    const key1 = req1.request.headers.get('Idempotency-Key')!;

    // Erro de rede
    req1.flush(
      { type: 'about:blank', title: 'Erro', status: 500, code: 'unknown' },
      { status: 500, statusText: 'Server Error' },
    );
    detectChanges();

    // Clica "Tentar novamente"
    const retryBtn = screen.getByRole('button', { name: /tentar novamente/i });
    await user.click(retryBtn);
    detectChanges();

    // Re-submete o form
    await user.click(screen.getByRole('button', { name: /criar e publicar/i }));

    const req2 = http.expectOne(`${BASE}/posts`);
    const key2 = req2.request.headers.get('Idempotency-Key')!;

    // Mesma key — mesma intencao (P-03)
    expect(key2).toBe(key1);

    req2.error(new ProgressEvent('error'));
    http.verify();
  });

  it('422 validation_error: mapeia errors[].field ao campo correto (CA-F002-03)', async () => {
    const { http, detectChanges } = await renderComponent();
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/titulo/i), 'T');
    await user.type(screen.getByLabelText(/conteudo/i), 'C');
    await user.click(screen.getByRole('button', { name: /criar e publicar/i }));

    http.expectOne(`${BASE}/posts`).flush(
      {
        type: 'https://blog-tutorial/errors/validation_error',
        title: 'Validation error',
        status: 422,
        code: 'validation_error',
        errors: [{ field: 'title', code: 'max_length', message: 'Titulo muito longo' }],
      },
      { status: 422, statusText: 'Unprocessable Entity' },
    );
    detectChanges();

    expect(screen.getByText('Titulo muito longo')).toBeTruthy();
    http.verify();
  });

  it('409 idempotency_key_conflict: exibe mensagem por code (nao por detail)', async () => {
    const { http, detectChanges } = await renderComponent();
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/titulo/i), 'T');
    await user.type(screen.getByLabelText(/conteudo/i), 'C');
    await user.click(screen.getByRole('button', { name: /criar e publicar/i }));

    http.expectOne(`${BASE}/posts`).flush(
      {
        type: 'https://blog-tutorial/errors/idempotency_key_conflict',
        title: 'Conflict',
        status: 409,
        code: 'idempotency_key_conflict',
        detail: 'payload divergente — nao deve ser exibido',
      },
      { status: 409, statusText: 'Conflict' },
    );
    detectChanges();

    // Exibe mensagem propria do front (nao o detail do back — 005 §4)
    expect(screen.queryByText('payload divergente — nao deve ser exibido')).toBeNull();
    expect(screen.getByRole('alert')).toBeTruthy();
    http.verify();
  });

  it('400 idempotency_key_required: exibe erro tecnico por code', async () => {
    const { http, detectChanges } = await renderComponent();
    const user = userEvent.setup();

    await user.type(screen.getByLabelText(/titulo/i), 'T');
    await user.type(screen.getByLabelText(/conteudo/i), 'C');
    await user.click(screen.getByRole('button', { name: /criar e publicar/i }));

    http.expectOne(`${BASE}/posts`).flush(
      {
        type: 'https://blog-tutorial/errors/idempotency_key_required',
        title: 'Key required',
        status: 400,
        code: 'idempotency_key_required',
      },
      { status: 400, statusText: 'Bad Request' },
    );
    detectChanges();

    expect(screen.getByRole('alert')).toBeTruthy();
    http.verify();
  });
});
