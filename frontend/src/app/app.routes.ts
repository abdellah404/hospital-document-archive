import { Routes } from '@angular/router';
import { authGuard } from './core/guards/auth-guard';

export const routes: Routes = [
  {
    path: 'login',
    loadComponent: () =>
      import('./features/auth/login/login')
        .then(m => m.LoginComponent),
  },

  {
    path: 'documents/import',
    canActivate: [authGuard],
    loadComponent: () =>
    import(
      './features/documents/document-import/document-import'
    ).then(
      m => m.DocumentImportComponent
    ),
  }
  ,
  {
    path: 'dashboard',
     canActivate: [authGuard],
    loadComponent: () =>
      import('./features/dashboard/dashboard')
        .then(m => m.DashboardComponent),
  },

  {
    path: '**',
    redirectTo: 'dashboard',
  },

  
];