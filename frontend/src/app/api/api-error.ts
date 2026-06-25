/**
 * Tipos de erro tipados — RFC 9457 Problem Details (005-api-contract.md §4).
 * Discriminar SEMPRE por `type` ou `code`, NUNCA por `detail` (texto livre).
 */

/**
 * Sufixos do campo `type` do catalogo de erros de 005-api-contract.md §4.
 * Exaustivo: qualquer novo tipo de erro exige atualizacao aqui + no contrato.
 */
export type ApiErrorCode =
  | 'validation_error'
  | 'idempotency_key_required'
  | 'idempotency_key_conflict'
  | 'invalid_cursor'
  | 'post_not_found'
  | 'unknown'; // Erros de rede ou sem corpo problem+json

export interface ApiErrorDetail {
  field: string;
  code: string;
  message: string;
}

export interface ApiError {
  /** URI do tipo de erro (ex.: "https://blog-tutorial/errors/post_not_found") */
  type: string;
  /** Resumo legivel, estavel por type */
  title: string;
  /** Codigo HTTP */
  status: number;
  /** Texto livre — NAO usar para discriminar (005 §4) */
  detail?: string;
  /** Sufixo de `type` — chave tipada para logica de UI */
  code: ApiErrorCode;
  /** Apenas em validation_error: lista de campos com problema */
  errors?: ApiErrorDetail[];
}

/**
 * Factory para ApiError de fallback (rede pura ou corpo nao-problem+json).
 * Evita literar o objeto em 3 lugares do store.
 */
export function unknownApiError(): ApiError {
  return { type: 'unknown', title: 'Erro inesperado', status: 0, code: 'unknown' };
}

/**
 * Type guard para verificar se um valor e um ApiError.
 */
export function isApiError(value: unknown): value is ApiError {
  return (
    typeof value === 'object' &&
    value !== null &&
    'type' in value &&
    'title' in value &&
    'status' in value &&
    'code' in value
  );
}
