import { ApiError } from '../api/api-error';

/**
 * Estado discriminado para operacoes assincronas (T-S3-03).
 * Todos os estados sao obrigatorios: idle | loading | loaded | empty | error.
 * Anti "tela branca" e anti "loading infinito".
 */
export type AsyncState<T> =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'loaded'; data: T }
  | { kind: 'empty' }
  | { kind: 'error'; error: ApiError };

