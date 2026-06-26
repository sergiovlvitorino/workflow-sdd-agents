import { Component, inject, computed } from '@angular/core';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { PostCreateStore } from '../post-store';

/**
 * PostCreateComponent — formulario para criar + publicar post (F001 + F002).
 * Reactive Form: validacao client-side espelha contrato (1-200 / 1-50000) mas back e autoridade.
 * Componente "burro" (ADR-0001): so le signals e dispara intencoes ao PostCreateStore.
 *
 * Template inline (requerido para Vitest/jsdom sem plugin Angular).
 */
@Component({
  selector: 'app-post-create',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink],
  providers: [PostCreateStore],
  template: `
    <main>
      <h1>Criar novo post</h1>

      @if (globalError()) {
        <div role="alert" aria-live="assertive" class="error-summary">
          <p>{{ globalError() }}</p>
          <button type="button" (click)="retry()">Tentar novamente</button>
        </div>
      }

      @if (store.state().kind === 'publishing') {
        <div aria-busy="true" aria-live="polite">
          <p>Publicando post...</p>
        </div>
      }

      <form [formGroup]="form" (ngSubmit)="submit()" novalidate>
        <div class="field">
          <label for="title">Titulo</label>
          <input
            id="title"
            type="text"
            formControlName="title"
            [attr.aria-invalid]="(form.get('title')?.invalid && form.get('title')?.touched) || !!fieldError('title')"
            [attr.aria-describedby]="(form.get('title')?.invalid && form.get('title')?.touched) || fieldError('title') ? 'title-error' : null"
            maxlength="200"
          />
          @if (form.get('title')?.invalid && form.get('title')?.touched) {
            <span id="title-error" role="alert">
              @if (form.get('title')?.errors?.['required']) {
                Titulo e obrigatorio.
              } @else if (form.get('title')?.errors?.['maxlength']) {
                Titulo deve ter no maximo 200 caracteres.
              }
            </span>
          } @else if (fieldError('title')) {
            <span id="title-error" role="alert">{{ fieldError('title') }}</span>
          }
        </div>

        <div class="field">
          <label for="content">Conteudo</label>
          <textarea
            id="content"
            formControlName="content"
            rows="10"
            [attr.aria-invalid]="(form.get('content')?.invalid && form.get('content')?.touched) || !!fieldError('content')"
            [attr.aria-describedby]="(form.get('content')?.invalid && form.get('content')?.touched) || fieldError('content') ? 'content-error' : null"
            maxlength="50000"
          ></textarea>
          @if (form.get('content')?.invalid && form.get('content')?.touched) {
            <span id="content-error" role="alert">
              @if (form.get('content')?.errors?.['required']) {
                Conteudo e obrigatorio.
              } @else if (form.get('content')?.errors?.['maxlength']) {
                Conteudo deve ter no maximo 50000 caracteres.
              }
            </span>
          } @else if (fieldError('content')) {
            <span id="content-error" role="alert">{{ fieldError('content') }}</span>
          }
        </div>

        <div class="actions">
          <button
            type="submit"
            [disabled]="form.invalid || isSubmitting()"
            [attr.aria-busy]="isSubmitting()">
            @if (store.state().kind === 'creating') {
              Criando...
            } @else if (store.state().kind === 'publishing') {
              Publicando...
            } @else {
              Criar e publicar
            }
          </button>
          <a routerLink="/">Cancelar</a>
        </div>
      </form>
    </main>
  `,
})
export class PostCreateComponent {
  readonly store = inject(PostCreateStore);
  private readonly fb = inject(FormBuilder);

  readonly form = this.fb.group({
    title: ['', [Validators.required, Validators.maxLength(200)]],
    content: ['', [Validators.required, Validators.maxLength(50000)]],
  });

  readonly isSubmitting = computed(
    () => this.store.state().kind === 'creating' || this.store.state().kind === 'publishing',
  );

  /** Mensagem de erro de campo do servidor (422) */
  fieldError(field: string): string | null {
    const s = this.store.state();
    if (s.kind !== 'error') return null;
    return s.fieldErrors?.[field] ?? null;
  }

  globalError(): string | null {
    const s = this.store.state();
    if (s.kind !== 'error') return null;
    return s.globalError ?? null;
  }

  submit(): void {
    if (this.form.invalid || this.isSubmitting()) return;

    const { title, content } = this.form.getRawValue();
    this.store.submit({ title: title!, content: content! });
  }

  retry(): void {
    this.store.reset();
    // Nao regenera createKey: reutiliza na proxima submit() (P-03)
  }
}
