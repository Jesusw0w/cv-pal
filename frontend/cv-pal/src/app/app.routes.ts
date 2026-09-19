import { Routes } from '@angular/router';
import { authGuard } from './core/auth';
import { LayoutComponent } from './core/layout.component';

export const routes: Routes = [
  { path: 'login', loadComponent: () => import('./pages/login/login.component').then(m => m.LoginComponent) },
  {
    path: '',
    component: LayoutComponent,
    canActivate: [authGuard],
    children: [
      // `data.title`, not the router's `title`: the tab should keep saying CV Pal.
      { path: '', redirectTo: 'dashboard', pathMatch: 'full' },
      { path: 'dashboard', data: { title: 'Dashboard' }, loadComponent: () => import('./pages/dashboard/dashboard.component').then(m => m.DashboardComponent) },
      // Not in the sidebar: a first run, not a destination. Reached by the redirect in
      // LayoutComponent and the dashboard's next-action card.
      { path: 'welcome', data: { title: 'Getting started' }, loadComponent: () => import('./pages/welcome/welcome.component').then(m => m.WelcomeComponent) },
      { path: 'profile', data: { title: 'Career Profile' }, loadComponent: () => import('./pages/profile/profile.component').then(m => m.ProfileComponent) },
      { path: 'goals', data: { title: 'Goals' }, loadComponent: () => import('./pages/goals/goals.component').then(m => m.GoalsComponent) },
      { path: 'documents', data: { title: 'Documents' }, loadComponent: () => import('./pages/documents/documents.component').then(m => m.DocumentsComponent) },
      { path: 'ai-tools', data: { title: 'AI Tools' }, loadComponent: () => import('./pages/ai-tools/ai-tools.component').then(m => m.AiToolsComponent) },
      { path: 'analysis', data: { title: 'CV Analysis' }, loadComponent: () => import('./pages/analysis/analysis.component').then(m => m.AnalysisComponent) },
      { path: 'job-search', data: { title: 'Job Search' }, loadComponent: () => import('./pages/job-search/job-search.component').then(m => m.JobSearchComponent) },
      { path: 'applications', data: { title: 'Applications' }, loadComponent: () => import('./pages/applications/applications.component').then(m => m.ApplicationsComponent) },
      { path: 'linkedin', data: { title: 'LinkedIn' }, loadComponent: () => import('./pages/linkedin/linkedin.component').then(m => m.LinkedInComponent) },
      { path: 'settings', data: { title: 'Settings' }, loadComponent: () => import('./pages/settings/settings.component').then(m => m.SettingsComponent) },
    ]
  },
  // Without this an unmatched path renders nothing — a blank page indistinguishable
  // from a broken build, and what a tab left open across a deploy actually hits.
  { path: '**', redirectTo: '' },
];
