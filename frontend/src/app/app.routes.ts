import { Routes } from '@angular/router';

/**
 * Rotas lazy-loaded das 3 telas (T-S3-03).
 * Componentes standalone com loadComponent — sem NgModule.
 */
export const routes: Routes = [
  {
    path: '',
    pathMatch: 'full',
    loadComponent: () =>
      import('./posts/post-list/post-list').then((m) => m.PostListComponent),
  },
  {
    path: 'posts/new',
    loadComponent: () =>
      import('./posts/post-create/post-create').then((m) => m.PostCreateComponent),
  },
  {
    path: 'posts/:id',
    loadComponent: () =>
      import('./posts/post-detail/post-detail').then((m) => m.PostDetailComponent),
  },
];
