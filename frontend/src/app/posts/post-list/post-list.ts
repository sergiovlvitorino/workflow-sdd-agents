import { Component, OnInit, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { SlicePipe } from '@angular/common';
import { PostListStore } from '../post-store';

/**
 * PostListComponent — lista posts publicados com paginacao cursor (F003).
 * Componente "burro" (ADR-0001): so le signals e dispara intencoes ao PostListStore.
 * Sem logica de negocio, sem HTTP direto.
 *
 * Template inline (requerido para Vitest/jsdom sem plugin Angular — resolveComponentResources).
 */
@Component({
  selector: 'app-post-list',
  standalone: true,
  imports: [RouterLink, SlicePipe],
  providers: [PostListStore],
  template: `
    <main>
      <h1>Posts publicados</h1>

      @if (store.state().kind === 'loading') {
        <div aria-busy="true" aria-live="polite">
          <p>Carregando posts...</p>
        </div>
      }

      @if (store.state().kind === 'error') {
        <div role="alert" aria-live="assertive">
          <p>Erro ao carregar posts: {{ $any(store.state()).error.title }}</p>
        </div>
      }

      @if (store.state().kind === 'empty') {
        <div aria-live="polite">
          <p>Nenhum post publicado ainda.</p>
        </div>
      }

      @if (store.state().kind === 'loaded') {
        <section aria-live="polite" aria-label="Lista de posts">
          <ul>
            @for (post of store.posts(); track post.id) {
              <li>
                <a [routerLink]="['/posts', post.id]">{{ post.title }}</a>
                @if (post.published_at) {
                  <time [attr.datetime]="post.published_at">
                    {{ post.published_at | slice:0:10 }}
                  </time>
                }
              </li>
            }
          </ul>

          @if (store.hasMore()) {
            <button
              type="button"
              (click)="loadMore()"
              [disabled]="store.loadingMore()"
              [attr.aria-busy]="store.loadingMore()">
              @if (store.loadingMore()) {
                Carregando mais...
              } @else {
                Carregar mais
              }
            </button>
          }
        </section>
      }

      <nav aria-label="Acao principal">
        <a routerLink="/posts/new">Criar novo post</a>
      </nav>
    </main>
  `,
})
export class PostListComponent implements OnInit {
  readonly store = inject(PostListStore);

  ngOnInit(): void {
    this.store.loadFirstPage();
  }

  loadMore(): void {
    this.store.loadMore();
  }
}
