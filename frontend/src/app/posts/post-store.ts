import { Injectable, inject, signal, computed } from '@angular/core';
import { Router } from '@angular/router';
import { BlogApiService } from '../api/blog-api.service';
import { isApiError, unknownApiError } from '../api/api-error';
import { generateIdempotencyKey } from '../api/idempotency';
import { AsyncState } from '../shared/async-state';
import { Post, PagePost, CreatePostRequest } from '../api/api.types';

/**
 * PostStore — camada de estado fina (signals) para as 3 telas.
 * Orquestra chamadas ao BlogApiService; mantém negócio fora do componente (ADR-0001).
 * Instanciado por componente (providedIn: null) para escopo por rota.
 */

// ---- PostListStore --------------------------------------------------------

@Injectable()
export class PostListStore {
  private readonly api = inject(BlogApiService);

  private readonly _posts = signal<Post[]>([]);
  private readonly _nextCursor = signal<string | null>(null);
  private readonly _state = signal<AsyncState<Post[]>>({ kind: 'idle' });
  private readonly _loadingMore = signal(false);

  /** Estado da lista: idle | loading | loaded | empty | error */
  readonly state = this._state.asReadonly();

  /** Token opaco para proxima pagina (ADR-0002: nunca interpretado) */
  readonly nextCursor = this._nextCursor.asReadonly();

  /** Ha proxima pagina disponivel */
  readonly hasMore = computed(() => this._nextCursor() !== null);

  /** Carregando pagina adicional (apos primeira) */
  readonly loadingMore = this._loadingMore.asReadonly();

  /** Lista acumulada de posts */
  readonly posts = this._posts.asReadonly();

  loadFirstPage(limit = 10): void {
    this._state.set({ kind: 'loading' });
    this._posts.set([]);
    this._nextCursor.set(null);

    this.api.listPosts({ limit }).subscribe({
      next: (page: PagePost) => this._applyPage(page, false),
      error: (err: unknown) => this._setError(err),
    });
  }

  loadMore(limit = 10): void {
    const cursor = this._nextCursor();
    if (!cursor || this._loadingMore()) return;

    this._loadingMore.set(true);

    // Cursor e token cego: repassado exatamente como recebido (ADR-0002)
    this.api.listPosts({ limit, cursor }).subscribe({
      next: (page: PagePost) => {
        this._loadingMore.set(false);
        this._applyPage(page, true);
      },
      error: (err: unknown) => {
        this._loadingMore.set(false);
        this._setError(err);
      },
    });
  }

  private _applyPage(page: PagePost, accumulate: boolean): void {
    const items = page.items ?? [];
    const all = accumulate ? [...this._posts(), ...items] : items;
    this._posts.set(all);
    // next_cursor null = ultima pagina (005 §1)
    this._nextCursor.set(page.next_cursor ?? null);

    if (all.length === 0) {
      this._state.set({ kind: 'empty' });
    } else {
      this._state.set({ kind: 'loaded', data: all });
    }
  }

  private _setError(err: unknown): void {
    this._state.set({
      kind: 'error',
      error: isApiError(err) ? err : unknownApiError(),
    });
  }
}

// ---- PostDetailStore -------------------------------------------------------

@Injectable()
export class PostDetailStore {
  private readonly api = inject(BlogApiService);

  private readonly _state = signal<AsyncState<Post>>({ kind: 'idle' });
  readonly state = this._state.asReadonly();

  load(id: string): void {
    this._state.set({ kind: 'loading' });

    this.api.getPost(id).subscribe({
      next: (post: Post) => this._state.set({ kind: 'loaded', data: post }),
      error: (err: unknown) => {
        this._state.set({
          kind: 'error',
          error: isApiError(err) ? err : unknownApiError(),
        });
      },
    });
  }
}

// ---- PostCreateStore -------------------------------------------------------

export interface SubmitState {
  kind: 'idle' | 'creating' | 'publishing' | 'done' | 'error';
  fieldErrors?: Record<string, string>;
  globalError?: string;
  post?: Post;
}

@Injectable()
export class PostCreateStore {
  private readonly api = inject(BlogApiService);
  private readonly router = inject(Router);

  private readonly _state = signal<SubmitState>({ kind: 'idle' });
  readonly state = this._state.asReadonly();

  /**
   * Idempotency-Key da criacao — gerada UMA VEZ por intencao e reutilizada no retry (P-03).
   * null = nenhuma intencao iniciada.
   */
  private _createKey: string | null = null;

  /**
   * Reseta estado para 'idle' sem apagar a Idempotency-Key.
   * A key e preservada para que o proximo submit() seja retry da mesma intencao (P-03).
   * Para iniciar uma NOVA intencao (ex: usuario decidiu mudar dados), chame newIntent().
   */
  reset(): void {
    this._state.set({ kind: 'idle' });
    // _createKey preservado intencionalmente: retry da mesma intencao (P-03)
  }

  /** Inicia nova intencao: limpa estado E key de idempotencia. */
  newIntent(): void {
    this._state.set({ kind: 'idle' });
    this._createKey = null;
  }

  /**
   * Submete criacao seguida de publicacao.
   * A Idempotency-Key de criacao e estavel no retry da mesma intencao.
   * Publicacao usa key separada (operacao distinta — P-03).
   */
  submit(body: CreatePostRequest): void {
    if (this._state().kind === 'creating' || this._state().kind === 'publishing') return;

    // Gera key UMA VEZ por intencao; retry reutiliza a mesma (P-03)
    if (!this._createKey) {
      this._createKey = generateIdempotencyKey();
    }

    this._state.set({ kind: 'creating' });

    this.api.createPost(body, this._createKey).subscribe({
      next: (post: Post) => this._doPublish(post),
      error: (err: unknown) => this._handleError(err),
    });
  }

  private _doPublish(post: Post): void {
    this._state.set({ kind: 'publishing', post });

    // Publicacao usa NOVA key (operacao distinta da criacao — P-03)
    const publishKey = generateIdempotencyKey();

    this.api.publishPost(post.id, publishKey).subscribe({
      next: (published: Post) => {
        this._state.set({ kind: 'done', post: published });
        this.router.navigate(['/posts', published.id]);
      },
      error: (err: unknown) => this._handleError(err),
    });
  }

  private _handleError(err: unknown): void {
    // O interceptor (apiErrorInterceptor) garante que err e sempre ApiError.
    // Se por algum motivo nao for (ex: bug de wiring), trata como unknown.
    const apiErr = isApiError(err) ? err : unknownApiError();

    switch (apiErr.code) {
      case 'validation_error': {
        // Mapeia errors[].field -> controle do form (005 §4, CA-F002-03)
        const fieldErrors: Record<string, string> = {};
        for (const e of apiErr.errors ?? []) {
          fieldErrors[e.field] = e.message;
        }
        this._state.set({ kind: 'error', fieldErrors });
        break;
      }
      case 'idempotency_key_conflict':
        this._state.set({
          kind: 'error',
          globalError: 'Requisição duplicada com dados diferentes. Recarregue e tente novamente.',
        });
        break;
      case 'idempotency_key_required':
        // Nao deve ocorrer (key sempre enviada); erro tecnico
        this._state.set({
          kind: 'error',
          globalError: 'Erro tecnico: chave de idempotencia ausente.',
        });
        break;
      case 'post_not_found':
        this._state.set({
          kind: 'error',
          globalError: 'Post nao encontrado para publicacao.',
        });
        break;
      default:
        this._state.set({ kind: 'error', globalError: apiErr.title || 'Erro inesperado.' });
    }
  }
}
