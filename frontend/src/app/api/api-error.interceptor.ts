import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { catchError, throwError } from 'rxjs';
import { ApiError, ApiErrorCode } from './api-error';

/**
 * Interceptor que traduz HttpErrorResponse (application/problem+json) em ApiError tipado.
 *
 * Regras (ADR-0001 §4, 005-api-contract.md §4):
 * - Discrimina por `type`/`status`, NUNCA por `detail` (texto livre).
 * - `code` = sufixo do campo `type` (ex.: "https://blog-tutorial/errors/post_not_found" -> "post_not_found").
 * - Erro de rede (status=0) ou sem corpo Problem -> code: 'unknown'.
 * - Componentes recebem ApiError tipado, nunca HttpErrorResponse cru (P-11).
 */
export const apiErrorInterceptor: HttpInterceptorFn = (req, next) =>
  next(req).pipe(
    catchError((err: HttpErrorResponse) => {
      const body = err.error as Record<string, unknown> | null | undefined;

      const rawType = typeof body?.['type'] === 'string' ? body['type'] : null;
      const code: ApiErrorCode = rawType ? extractCode(rawType) : 'unknown';

      const apiError: ApiError = {
        type: rawType ?? 'about:blank',
        title: typeof body?.['title'] === 'string' ? body['title'] : httpStatusTitle(err.status),
        status: err.status,
        detail: typeof body?.['detail'] === 'string' ? body['detail'] : undefined,
        code,
        errors: Array.isArray(body?.['errors'])
          ? (body['errors'] as Array<{ field: string; code: string; message: string }>)
          : undefined,
      };

      return throwError(() => apiError);
    }),
  );

/**
 * Extrai o code do sufixo da URI de tipo.
 * Ex.: "https://blog-tutorial/errors/post_not_found" -> "post_not_found"
 */
function extractCode(typeUri: string): ApiErrorCode {
  const suffix = typeUri.split('/').pop() ?? '';
  const known: ApiErrorCode[] = [
    'validation_error',
    'idempotency_key_required',
    'idempotency_key_conflict',
    'invalid_cursor',
    'post_not_found',
  ];
  return known.includes(suffix as ApiErrorCode) ? (suffix as ApiErrorCode) : 'unknown';
}

/**
 * Titulo legivel de fallback quando nao ha corpo problem+json.
 */
function httpStatusTitle(status: number): string {
  if (status === 0) return 'Erro de rede';
  if (status >= 500) return 'Erro interno do servidor';
  if (status >= 400) return 'Erro na requisicao';
  return 'Erro desconhecido';
}
