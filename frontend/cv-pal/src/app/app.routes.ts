import { Routes } from '@angular/router';

import { authGuard } from './core/auth';
import { SectionComponent, SectionTab } from './core/components/section/section.component';
import { LayoutComponent } from './core/layout.component';

const PROFILE_TABS: SectionTab[] = [
  { path: './', label: 'Career profile' },
  { path: 'goals', label: 'Goals' },
  { path: 'linkedin', label: 'LinkedIn' },
];

const APPLICATION_TABS: SectionTab[] = [
  { path: './', label: 'Applications' },
  { path: 'platforms', label: 'Platforms' },
];

export const routes: Routes = [
  {
    path: 'login',
    title: 'Sign in',
    loadComponent: () => import('./pages/login/login.component').then((m) => m.LoginComponent),
  },
  {
    path: '',
    component: LayoutComponent,
    canActivate: [authGuard],
    children: [
      { path: '', redirectTo: 'dashboard', pathMatch: 'full' },
      {
        path: 'dashboard',
        title: 'Dashboard',
        loadComponent: () =>
          import('./pages/dashboard/dashboard.component').then((m) => m.DashboardComponent),
      },
      // Not in the sidebar: a first run, not a destination. Reached by the redirect in
      // LayoutComponent, the dashboard's next-action card and Settings.
      {
        path: 'welcome',
        title: 'Getting started',
        loadComponent: () =>
          import('./pages/welcome/welcome.component').then((m) => m.WelcomeComponent),
      },
      {
        path: 'profile',
        component: SectionComponent,
        data: { tabs: PROFILE_TABS },
        children: [
          {
            path: '',
            title: 'Career profile',
            loadComponent: () =>
              import('./pages/profile/profile.component').then((m) => m.ProfileComponent),
          },
          {
            path: 'goals',
            title: 'Goals',
            loadComponent: () =>
              import('./pages/goals/goals.component').then((m) => m.GoalsComponent),
          },
          {
            path: 'linkedin',
            title: 'LinkedIn review',
            loadComponent: () =>
              import('./pages/linkedin/linkedin.component').then((m) => m.LinkedInComponent),
          },
        ],
      },
      {
        path: 'cvs',
        title: 'CVs',
        loadComponent: () => import('./pages/cvs/cvs.component').then((m) => m.CvsComponent),
      },
      {
        path: 'jobs',
        title: 'Jobs',
        loadComponent: () => import('./pages/jobs/jobs.component').then((m) => m.JobsComponent),
      },
      {
        path: 'applications',
        component: SectionComponent,
        data: { tabs: APPLICATION_TABS },
        children: [
          {
            path: '',
            title: 'Applications',
            loadComponent: () =>
              import('./pages/applications/applications.component').then(
                (m) => m.ApplicationsComponent,
              ),
          },
          {
            path: 'platforms',
            title: 'Platforms',
            loadComponent: () =>
              import('./pages/platforms/platforms.component').then((m) => m.PlatformsComponent),
          },
        ],
      },
      {
        path: 'settings',
        title: 'Settings',
        loadComponent: () =>
          import('./pages/settings/settings.component').then((m) => m.SettingsComponent),
      },
    ],
  },
  // Without this an unmatched path renders nothing — a blank page indistinguishable
  // from a broken build, and what a tab left open across a deploy actually hits.
  { path: '**', redirectTo: '' },
];
