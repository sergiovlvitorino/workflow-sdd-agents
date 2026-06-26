import { defineConfig } from 'vitest/config';

/**
 * Vitest config para testes unitarios do frontend.
 *
 * Runner: Vitest (nao Karma/browser) — mais rapido, sem JDK, compativel com CI.
 * Environment: jsdom (suporta Angular TestBed, HttpTestingController, crypto.randomUUID).
 * Cobertura: v8 com thresholds — 2o ratchet (front), barrado SEPARADAMENTE do Python.
 *
 * Nao usa @analogjs/vite-plugin-angular pois os testes de scaffold (service + interceptor)
 * nao renderizam componentes Angular — TestBed puro e suficiente.
 */
export default defineConfig({
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['src/test-setup.ts'],
    include: ['src/**/*.spec.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'lcov', 'html'],
      reportsDirectory: './coverage',
      include: ['src/app/**/*.ts'],
      exclude: [
        'src/app/**/*.spec.ts',
        'src/app/api/generated/**',
        'src/main.ts',
        'src/app/app.routes.ts',
        'src/app/app.ts',
        'src/app/app.config.ts',
        // Apenas declaracoes de tipo (AsyncState<T>): sem codigo executavel, nao mensuravel
        'src/app/shared/async-state.ts',
      ],
      thresholds: {
        // 2o ratchet aperatado em T-S3-07 — folga ≤1pp do patamar real medido.
        // Real medido (T-S3-03+T-S3-07): stmts 98.38, branches 91.42, funcs 97.82, lines 98.38.
        // Ratchet so sobe, nunca desce sem ADR (P-07).
        // Gate AND separado do Python (NUNCA media global combinada — ADR-0001 §4.1).
        branches: 90,
        functions: 96,
        lines: 97,
        statements: 97,

        // Piso por-arquivo: logica de negocio do front (post-store.ts).
        // Espelha anti-diluicao do backend (coverage-gates.sh).
        // post-store.ts real: stmts 100, branches 87.5, funcs 100, lines 100.
        // Branch 87.5 por ramos defensivos (isApiError ternario) — nao exercitaveis via HTTP.
        'src/app/posts/post-store.ts': {
          statements: 99,
          functions: 99,
          lines: 99,
          branches: 86,
        },
      },
    },
  },
  resolve: {
    alias: {
      '@api': '/src/app/api',
      '@app': '/src/app',
    },
  },
});
