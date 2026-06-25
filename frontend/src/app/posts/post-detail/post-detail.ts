import { Component, OnInit, inject } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { SlicePipe } from '@angular/common';
import { PostDetailStore } from '../post-store';

/**
 * PostDetailComponent — exibe post por id (F004).
 * 404 (rascunho OU inexistente) mostra mensagem generica — sem vazar existencia (ADR-0004 §8).
 * Componente "burro" (ADR-0001): so le signals e dispara intencoes.
 *
 * Template inline (requerido para Vitest/jsdom sem plugin Angular).
 */
@Component({
  selector: 'app-post-detail',
  standalone: true,
  imports: [RouterLink, SlicePipe],
  providers: [PostDetailStore],
  template: `
    <main>
      @if (store.state().kind === 'loading') {
        <div aria-busy="true" aria-live="polite">
          <p>Carregando post...</p>
        </div>
      }

      @if (store.state().kind === 'error') {
        <div role="alert" aria-live="assertive">
          @if ($any(store.state()).error.code === 'post_not_found') {
            <!-- Mensagem generica: nao distingue rascunho de inexistente (ADR-0004 §8) -->
            <h1>Post nao encontrado</h1>
            <p>O post que voce esta procurando nao existe ou nao esta disponivel.</p>
          } @else {
            <h1>Erro ao carregar post</h1>
            <p>{{ $any(store.state()).error.title }}</p>
          }
          <a routerLink="/">Voltar para a lista</a>
        </div>
      }

      @if (store.state().kind === 'loaded') {
        <article>
          <h1>{{ $any(store.state()).data.title }}</h1>

          @if ($any(store.state()).data.published_at) {
            <p>
              Publicado em:
              <time [attr.datetime]="$any(store.state()).data.published_at">
                {{ $any(store.state()).data.published_at | slice:0:10 }}
              </time>
            </p>
          }

          <div class="post-content">
            <!-- content via interpolacao (escapa XSS por padrao — RNF-S-01); proibido [innerHTML] -->
            <p>{{ $any(store.state()).data.content }}</p>
          </div>
        </article>

        <nav aria-label="Navegacao do post">
          <a routerLink="/">Voltar para a lista</a>
        </nav>
      }
    </main>
  `,
})
export class PostDetailComponent implements OnInit {
  readonly store = inject(PostDetailStore);
  private readonly route = inject(ActivatedRoute);

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id')!;
    this.store.load(id);
  }
}
