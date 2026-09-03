import { Routes } from '@angular/router';
import { authGuard } from './core/guards/auth-guard';
import { adminGuard } from './core/guards/admin-guard';
import { AppShellComponent } from './core/layout/app-shell';

export const routes: Routes = [
  {
    path: 'login',
    loadComponent: () =>
      import('./features/auth/login/login')
        .then(m => m.LoginComponent),
  },

  {
    path: 'change-password',
    canActivate: [authGuard],
    loadComponent: () =>
      import('./features/auth/change-password/change-password')
        .then(m => m.ChangePasswordComponent),
  },

  {
    path: '',
    component: AppShellComponent,
    canActivate: [authGuard],
    children: [
      {
        path: 'dashboard',
        loadComponent: () => import('./features/dashboard/dashboard')
          .then(m => m.DashboardComponent),
      },
      {
        path: 'documents/import',
        loadComponent: () => import('./features/documents/document-import/document-import')
          .then(m => m.DocumentImportComponent),
      },
      {
        path: 'documents/search',
        loadComponent: () => import('./features/documents/document-search/document-search')
          .then(m => m.DocumentSearchComponent),
      },
      {
        path: 'documents',
        pathMatch: 'full',
        loadComponent: () => import('./features/documents/document-list/document-list')
          .then(m => m.DocumentListComponent),
      },
      {
        path: 'documents/:documentId',
        loadComponent: () => import('./features/documents/document-details/document-details')
          .then(m => m.DocumentDetailsComponent),
      },
      {
        path: 'admin',
        pathMatch: 'full',
        redirectTo: 'admin/users',
      },
      {
        path: 'admin/users',
        canActivate: [adminGuard],
        data: { section: 'users' },
        loadComponent: () => import('./features/admin/admin').then(m => m.AdminComponent),
      },
      {
        path: 'admin/services',
        canActivate: [adminGuard],
        data: { section: 'services' },
        loadComponent: () => import('./features/admin/admin').then(m => m.AdminComponent),
      },
      {
        path: 'admin/logs',
        canActivate: [adminGuard],
        data: { section: 'logs' },
        loadComponent: () => import('./features/admin/admin').then(m => m.AdminComponent),
      },
      { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
    ],
  },

  {
    path: '**',
    redirectTo: 'dashboard',
  },

  
];
