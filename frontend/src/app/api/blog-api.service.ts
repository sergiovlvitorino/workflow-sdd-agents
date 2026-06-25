import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';
import { API_BASE_URL } from '../app.config';
import { Post, PagePost, CreatePostRequest } from './api.types';
import { generateIdempotencyKey } from './idempotency';

/**
 * BlogApiService — UNICO ponto que fala HTTP no frontend (ADR-0001 §4).
 *
 * Regras:
 * - Tipos de retorno sao aliases do gerado (anti-drift; ADR-0005 §4).
 * - Escritas EXIGEM Idempotency-Key (P-03). A key e gerada pelo chamador ou aqui por default.
 *   Em T-S3-03 a UI passara a key para controlar retentativas da mesma intencao.
 * - Base URL via API_BASE_URL token (/v1) — P-08 centralizacao.
 * - Erros chegam como ApiError (via apiErrorInterceptor), nunca HttpErrorResponse cru.
 * - Cursor de paginacao e tratado como token opaco (ADR-0002) — nunca interpretado.
 */
@Injectable({ providedIn: 'root' })
export class BlogApiService {
  private readonly http = inject(HttpClient);
  private readonly base = inject(API_BASE_URL);

  /**
   * Lista posts publicados com paginacao keyset (F003).
   * @param opts.limit   1-100; default 10
   * @param opts.cursor  Token opaco retornado por `next_cursor`; ausente = primeira pagina
   */
  listPosts(opts?: { limit?: number; cursor?: string }): Observable<PagePost> {
    const params: Record<string, string | number> = {};
    if (opts?.limit !== undefined) params['limit'] = opts.limit;
    if (opts?.cursor !== undefined) params['cursor'] = opts.cursor;

    return this.http.get<PagePost>(`${this.base}/posts`, { params });
  }

  /**
   * Le post publicado por id (F004).
   * Rascunho ou inexistente -> ApiError code: 'post_not_found' (P-04, nao revela existencia).
   */
  getPost(id: string): Observable<Post> {
    return this.http.get<Post>(`${this.base}/posts/${id}`);
  }

  /**
   * Cria post (F001) — exige Idempotency-Key (P-03).
   * @param body           Titulo e conteudo do post
   * @param idempotencyKey Chave fornecida pelo chamador (string UUID). Se omitida, gera uma nova.
   *                       ATENCAO: retentativas da MESMA intencao devem reutilizar a MESMA key.
   */
  createPost(body: CreatePostRequest, idempotencyKey?: string): Observable<Post> {
    const key = idempotencyKey ?? generateIdempotencyKey();
    const headers = new HttpHeaders({ 'Idempotency-Key': key });
    return this.http.post<Post>(`${this.base}/posts`, body, { headers });
  }

  /**
   * Publica post (F002) — exige Idempotency-Key (P-03).
   * Idempotente por estado: republicar post ja publicado e no-op (RF-009).
   * @param id             ULID do post
   * @param idempotencyKey Chave fornecida pelo chamador. Se omitida, gera uma nova.
   */
  publishPost(id: string, idempotencyKey?: string): Observable<Post> {
    const key = idempotencyKey ?? generateIdempotencyKey();
    const headers = new HttpHeaders({
      'Idempotency-Key': key,
      'Content-Type': 'application/json',
    });
    return this.http.put<Post>(`${this.base}/posts/${id}/publish`, null, { headers });
  }
}
