import { ApplicationConfig, InjectionToken } from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { routes } from './app.routes';
import { apiErrorInterceptor } from './api/api-error.interceptor';

/**
 * Token para a base URL da API (P-08 — centralizacao do prefixo /v1).
 * Em dev: proxy.conf.json encaminha /v1 -> http://127.0.0.1:8000/v1 (sem CORS, sem hardcode de host).
 * Em producao: injetar via environment/APP_INITIALIZER.
 */
export const API_BASE_URL = new InjectionToken<string>('API_BASE_URL', {
  providedIn: 'root',
  factory: () => '/v1',
});

export const appConfig: ApplicationConfig = {
  providers: [
    provideRouter(routes),
    provideHttpClient(withInterceptors([apiErrorInterceptor])),
    { provide: API_BASE_URL, useValue: '/v1' },
  ],
};
