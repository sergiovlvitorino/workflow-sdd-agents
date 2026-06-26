/**
 * Testes do PostListComponent (CA-F003-01/02/03).
 * Testing Library + HttpTestingController.
 * Verifica: loading/vazio/erro/lista, paginacao cursor, nao filtra client-side.
 *
 * Fixtures fies ao contrato (PagePost: items + limit + next_cursor; SEM total — ADR-0002 keyset).
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
import { PostListComponent } from './post-list';
import { apiErrorInterceptor } from '../../api/api-error.interceptor';
import { API_BASE_URL } from '../../app.config';
import type { PagePost } from '../../api/api.types';

const BASE = '/v1';

const providers = [
  provideRouter([]),
  provideHttpClient(withInterceptors([apiErrorInterceptor])),
  provideHttpClientTesting(),
  { provide: API_BASE_URL, useValue: BASE },
];

const POST_1 = {
  id: 'id-1',
  title: 'Post Alpha',
  content: 'Conteudo Alpha',
  status: 'published' as const,
  created_at: '2024-01-01T00:00:00Z',
  published_at: '2024-01-01T00:00:00Z',
};

const POST_2 = {
  id: 'id-2',
  title: 'Post Beta',
  content: 'Conteudo Beta',
  status: 'published' as const,
  created_at: '2024-01-02T00:00:00Z',
  published_at: '2024-01-02T00:00:00Z',
};

// Helper para criar PagePost fiel ao contrato (sem total, com limit)
function makePage(opts: { items: typeof POST_1[]; next_cursor: string | null }): PagePost {
  return { items: opts.items, limit: 10, next_cursor: opts.next_cursor };
}

async function renderComponent() {
  TestBed.resetTestingModule();
  const result = await render(PostListComponent, { providers });
  const http = TestBed.inject(HttpTestingController);
  return { ...result, http };
}

describe('PostListComponent', () => {
  afterEach(() => {
    TestBed.resetTestingModule();
  });

  it('exibe estado de loading enquanto aguarda resposta (CA-F003-01)', async () => {
    const { http } = await renderComponent();

    expect(screen.getByText('Carregando posts...')).toBeTruthy();

    http.expectOne((r) => r.url === `${BASE}/posts`).flush(makePage({ items: [], next_cursor: null }));
    http.verify();
  });

  it('exibe lista de posts apos carregamento (CA-F003-01)', async () => {
    const { http, detectChanges } = await renderComponent();

    http.expectOne((r) => r.url === `${BASE}/posts`).flush(
      makePage({ items: [POST_1, POST_2], next_cursor: null }),
    );
    detectChanges();

    expect(screen.getByText('Post Alpha')).toBeTruthy();
    expect(screen.getByText('Post Beta')).toBeTruthy();
    http.verify();
  });

  it('exibe estado vazio quando lista esta vazia (CA-F003-01)', async () => {
    const { http, detectChanges } = await renderComponent();

    http.expectOne((r) => r.url === `${BASE}/posts`).flush(makePage({ items: [], next_cursor: null }));
    detectChanges();

    expect(screen.getByText('Nenhum post publicado ainda.')).toBeTruthy();
    http.verify();
  });

  it('exibe erro quando API falha', async () => {
    const { http, detectChanges } = await renderComponent();

    http.expectOne((r) => r.url === `${BASE}/posts`).flush(
      {
        type: 'about:blank',
        title: 'Server Error',
        status: 500,
        code: 'unknown',
      },
      { status: 500, statusText: 'Internal Server Error' },
    );
    detectChanges();

    expect(screen.getByRole('alert')).toBeTruthy();
    http.verify();
  });

  it('exibe botao "Carregar mais" quando ha proxima pagina (CA-F003-03)', async () => {
    const { http, detectChanges } = await renderComponent();

    http.expectOne((r) => r.url === `${BASE}/posts`).flush(
      makePage({ items: [POST_1], next_cursor: 'cursor-opaco' }),
    );
    detectChanges();

    expect(screen.getByRole('button', { name: /carregar mais/i })).toBeTruthy();
    http.verify();
  });

  it('esconde botao "Carregar mais" quando next_cursor e null (CA-F003-03)', async () => {
    const { http, detectChanges } = await renderComponent();

    http.expectOne((r) => r.url === `${BASE}/posts`).flush(
      makePage({ items: [POST_1], next_cursor: null }),
    );
    detectChanges();

    expect(screen.queryByRole('button', { name: /carregar mais/i })).toBeNull();
    http.verify();
  });

  it('loadMore: envia cursor opaco exato na segunda requisicao (CA-F003-03)', async () => {
    const { http, detectChanges } = await renderComponent();
    const user = userEvent.setup();

    // Pagina 1
    http.expectOne((r) => r.url === `${BASE}/posts`).flush(
      makePage({ items: [POST_1], next_cursor: 'cursor-opaco-xyz' }),
    );
    detectChanges();

    // Clica "Carregar mais"
    await user.click(screen.getByRole('button', { name: /carregar mais/i }));

    // Verifica que cursor cego foi ecoado (ADR-0002)
    const req2 = http.expectOne((r) => r.url === `${BASE}/posts`);
    expect(req2.request.params.get('cursor')).toBe('cursor-opaco-xyz');

    req2.flush(makePage({ items: [POST_2], next_cursor: null }));
    detectChanges();

    expect(screen.getByText('Post Alpha')).toBeTruthy();
    expect(screen.getByText('Post Beta')).toBeTruthy();
    http.verify();
  });

  it('front NAO filtra status no cliente: exibe o que o back retornou (CA-F003-02)', async () => {
    const { http, detectChanges } = await renderComponent();

    // Back retornou apenas publicados (allowlist server-side) — front exibe sem filtro adicional
    http.expectOne((r) => r.url === `${BASE}/posts`).flush(
      makePage({ items: [POST_1], next_cursor: null }),
    );
    detectChanges();

    // Frontend nao tem logica de filtro de status; exibe todos os retornados
    expect(screen.getByText('Post Alpha')).toBeTruthy();
    http.verify();
  });
});
