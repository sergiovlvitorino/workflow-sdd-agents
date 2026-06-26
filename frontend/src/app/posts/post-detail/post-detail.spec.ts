/**
 * Testes do PostDetailComponent (CA-F004-01/02).
 * Testing Library + HttpTestingController.
 * Verifica: 200 exibe post, 404 mostra mensagem generica sem vazar existencia.
 */
import { TestBed } from '@angular/core/testing';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { provideRouter, ActivatedRoute } from '@angular/router';
import { describe, it, expect, afterEach } from 'vitest';
import { render, screen } from '@testing-library/angular';
import { PostDetailComponent } from './post-detail';
import { apiErrorInterceptor } from '../../api/api-error.interceptor';
import { API_BASE_URL } from '../../app.config';
import type { Post } from '../../api/api.types';

const BASE = '/v1';

const POST: Post = {
  id: 'post-abc',
  title: 'Meu Post Publicado',
  content: 'Conteudo do post aqui.',
  status: 'published',
  created_at: '2024-01-01T00:00:00Z',
  published_at: '2024-01-01T00:00:00Z',
};

function makeProviders(id: string) {
  return [
    provideRouter([]),
    provideHttpClient(withInterceptors([apiErrorInterceptor])),
    provideHttpClientTesting(),
    { provide: API_BASE_URL, useValue: BASE },
    {
      provide: ActivatedRoute,
      useValue: {
        snapshot: { paramMap: { get: () => id } },
      },
    },
  ];
}

async function renderWithId(id: string) {
  TestBed.resetTestingModule();
  const result = await render(PostDetailComponent, { providers: makeProviders(id) });
  const http = TestBed.inject(HttpTestingController);
  return { ...result, http };
}

describe('PostDetailComponent', () => {
  afterEach(() => {
    TestBed.resetTestingModule();
  });

  it('exibe estado de loading enquanto aguarda resposta', async () => {
    const { http } = await renderWithId('post-abc');

    expect(screen.getByText('Carregando post...')).toBeTruthy();

    http.expectOne(`${BASE}/posts/post-abc`).flush(POST);
    http.verify();
  });

  it('200: exibe titulo e conteudo do post (CA-F004-01)', async () => {
    const { http, detectChanges } = await renderWithId('post-abc');

    http.expectOne(`${BASE}/posts/post-abc`).flush(POST);
    detectChanges();

    expect(screen.getByRole('heading', { name: 'Meu Post Publicado' })).toBeTruthy();
    expect(screen.getByText('Conteudo do post aqui.')).toBeTruthy();
    http.verify();
  });

  it('404: exibe mensagem generica sem revelar se e rascunho ou inexistente (CA-F004-02)', async () => {
    const { http, detectChanges } = await renderWithId('post-inexistente');

    http.expectOne(`${BASE}/posts/post-inexistente`).flush(
      {
        type: 'https://blog-tutorial/errors/post_not_found',
        title: 'Post not found',
        status: 404,
        code: 'post_not_found',
      },
      { status: 404, statusText: 'Not Found' },
    );
    detectChanges();

    // Mensagem generica unica (ADR-0004 §8)
    expect(screen.getByText(/Post nao encontrado/i)).toBeTruthy();

    // Assercao negativa: nao deve distinguir rascunho de inexistente
    expect(screen.queryByText(/rascunho/i)).toBeNull();
    expect(screen.queryByText(/draft/i)).toBeNull();
    expect(screen.queryByText(/nao publicado/i)).toBeNull();
    expect(screen.queryByText(/Post not found/i)).toBeNull(); // nao exibe detail do back
    http.verify();
  });

  it('404 rascunho: mesma mensagem generica que 404 inexistente (CA-F004-02)', async () => {
    const { http, detectChanges } = await renderWithId('post-draft');

    // Mesmo payload para rascunho e inexistente (005 §2.4)
    http.expectOne(`${BASE}/posts/post-draft`).flush(
      {
        type: 'https://blog-tutorial/errors/post_not_found',
        title: 'Post not found',
        status: 404,
        code: 'post_not_found',
      },
      { status: 404, statusText: 'Not Found' },
    );
    detectChanges();

    // Mesma mensagem — sem vazar existencia
    expect(screen.getByText(/Post nao encontrado/i)).toBeTruthy();
    http.verify();
  });

  it('erro generico (500): exibe titulo do erro', async () => {
    const { http, detectChanges } = await renderWithId('post-xyz');

    http.expectOne(`${BASE}/posts/post-xyz`).flush(
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
});
