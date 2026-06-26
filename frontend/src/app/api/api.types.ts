/**
 * Aliases de domínio derivados do arquivo gerado (ADR-0005 §8).
 *
 * REGRA: componentes importam DAQUI, nunca de api/generated diretamente.
 * A barreira é enforced pelo ESLint (eslint.config.js: no-restricted-imports).
 *
 * Nomes reais dos schemas conferidos no gerado (openapi-types.ts):
 *   PostResponse  -> alias Post
 *   PageResponse  -> alias PagePost
 */
import type { components } from './generated/openapi-types';

/** Post — shape canônico de 005-api-contract.md §3 */
export type Post = components['schemas']['PostResponse'];

/**
 * Status do post: "draft" | "published" (union, não string).
 * Derivado do tipo gerado — nunca declarado à mão (anti-drift).
 */
export type PostStatus = Post['status'];

/** Página de posts (keyset/cursor — ADR-0002) */
export type PagePost = components['schemas']['PageResponse'];

/** Request de criação de post */
export type CreatePostRequest = components['schemas']['CreatePostRequest'];

/** Erro RFC 9457 — shape de wire (usar ApiError de api-error.ts para lógica de UI) */
export type ApiErrorSchema = components['schemas']['ApiError'];
