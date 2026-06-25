/**
 * Testes unitarios do apiErrorInterceptor.
 *
 * Cobre discriminacao por type/status, extracao de code, fallback para unknown.
 */
import { TestBed } from '@angular/core/testing';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { provideHttpClient, withInterceptors, HttpClient } from '@angular/common/http';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { apiErrorInterceptor } from './api-error.interceptor';
import { isApiError } from './api-error';

const URL = '/test-endpoint';

describe('apiErrorInterceptor', () => {
  let http: HttpClient;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([apiErrorInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    http = TestBed.inject(HttpClient);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
    TestBed.resetTestingModule();
  });

  it('passa resposta de sucesso sem alterar', () => {
    let result: unknown;
    http.get(URL).subscribe((r) => (result = r));

    httpMock.expectOne(URL).flush({ ok: true });
    expect(result).toEqual({ ok: true });
  });

  it('mapeia erro problem+json para ApiError com code correto', () => {
    let error: unknown;
    http.get(URL).subscribe({ error: (e) => (error = e) });

    httpMock.expectOne(URL).flush(
      {
        type: 'https://blog-tutorial/errors/post_not_found',
        title: 'Post nao encontrado',
        status: 404,
        detail: 'Nenhum post publicado com o id informado.',
      },
      { status: 404, statusText: 'Not Found', headers: { 'content-type': 'application/problem+json' } },
    );

    expect(isApiError(error)).toBe(true);
    if (isApiError(error)) {
      expect(error.code).toBe('post_not_found');
      expect(error.status).toBe(404);
      expect(error.type).toBe('https://blog-tutorial/errors/post_not_found');
      expect(error.detail).toBe('Nenhum post publicado com o id informado.');
    }
  });

  it('nao faz string-match em detail (detail pode ser qualquer texto)', () => {
    let error: unknown;
    http.get(URL).subscribe({ error: (e) => (error = e) });

    httpMock.expectOne(URL).flush(
      {
        type: 'https://blog-tutorial/errors/validation_error',
        title: 'Validacao',
        status: 422,
        detail: 'qualquer texto aqui que poderia mudar sem aviso',
        errors: [{ field: 'title', code: 'too_short', message: 'muito curto' }],
      },
      { status: 422, statusText: 'Unprocessable Entity' },
    );

    expect(isApiError(error)).toBe(true);
    if (isApiError(error)) {
      // Discrimina por code (sufixo de type), nao pelo conteudo de detail
      expect(error.code).toBe('validation_error');
      expect(error.errors?.[0]?.field).toBe('title');
    }
  });

  it('mapeia todos os 5 codes do catalogo 005', () => {
    const cases: Array<{ type: string; code: string; status: number }> = [
      { type: 'https://blog-tutorial/errors/validation_error', code: 'validation_error', status: 422 },
      { type: 'https://blog-tutorial/errors/idempotency_key_required', code: 'idempotency_key_required', status: 400 },
      { type: 'https://blog-tutorial/errors/idempotency_key_conflict', code: 'idempotency_key_conflict', status: 409 },
      { type: 'https://blog-tutorial/errors/invalid_cursor', code: 'invalid_cursor', status: 400 },
      { type: 'https://blog-tutorial/errors/post_not_found', code: 'post_not_found', status: 404 },
    ];

    for (const { type, code, status } of cases) {
      let error: unknown;
      http.get(URL).subscribe({ error: (e) => (error = e) });

      httpMock.expectOne(URL).flush(
        { type, title: 'Erro', status },
        { status, statusText: 'Error' },
      );

      expect(isApiError(error)).toBe(true);
      if (isApiError(error)) {
        expect(error.code).toBe(code);
      }
    }
  });

  it('type desconhecido resulta em code: unknown', () => {
    let error: unknown;
    http.get(URL).subscribe({ error: (e) => (error = e) });

    httpMock.expectOne(URL).flush(
      {
        type: 'https://blog-tutorial/errors/tipo_novo_nao_catalogado',
        title: 'Erro nao catalogado',
        status: 500,
      },
      { status: 500, statusText: 'Internal Server Error' },
    );

    expect(isApiError(error)).toBe(true);
    if (isApiError(error)) {
      expect(error.code).toBe('unknown');
    }
  });

  it('erro sem corpo problem+json resulta em code: unknown com title de fallback', () => {
    let error: unknown;
    http.get(URL).subscribe({ error: (e) => (error = e) });

    httpMock.expectOne(URL).flush('Internal Server Error', {
      status: 500,
      statusText: 'Internal Server Error',
    });

    expect(isApiError(error)).toBe(true);
    if (isApiError(error)) {
      expect(error.code).toBe('unknown');
      expect(error.status).toBe(500);
      expect(error.title).toBe('Erro interno do servidor');
    }
  });

  it('erro de rede (status 0, sem corpo) resulta em code: unknown', () => {
    let error: unknown;
    http.get(URL).subscribe({ error: (e) => (error = e) });

    httpMock.expectOne(URL).error(new ProgressEvent('error'));

    expect(isApiError(error)).toBe(true);
    if (isApiError(error)) {
      expect(error.code).toBe('unknown');
      expect(error.status).toBe(0);
      expect(error.title).toBe('Erro de rede');
    }
  });
});
