import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';

/**
 * Componente raiz standalone.
 * Mantido magro por ADR-0001 — telas entram em T-S3-03.
 */
@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet],
  template: `
    <main id="main" role="main">
      <router-outlet />
    </main>
  `,
})
export class AppComponent {}
