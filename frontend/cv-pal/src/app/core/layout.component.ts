import { Component, effect, inject, signal } from '@angular/core';
import { Router, RouterOutlet } from '@angular/router';
import { SidebarComponent } from './components/sidebar/sidebar.component';
import { TopbarComponent } from './components/topbar/topbar.component';
import { AuthService } from './services/auth.service';
import { CareerProfileService } from './services/career-profile.service';
import { hasSeenWelcome } from './first-run';

@Component({
  selector: 'app-layout',
  imports: [RouterOutlet, SidebarComponent, TopbarComponent],
  template: `
    <div class="sidebar-overlay" [class.visible]="sidebarOpen()" (click)="sidebarOpen.set(false)"></div>
    <app-sidebar [open]="sidebarOpen()" (close)="sidebarOpen.set(false)" />
    <div class="main-area">
      <app-topbar (menuToggle)="sidebarOpen.set(!sidebarOpen())" />
      <router-outlet />
    </div>
  `,
  styles: [`
    :host {
      display: flex;
      min-height: 100vh;
    }

    .main-area {
      margin-left: var(--sidebar-width);
      flex: 1;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }

    .sidebar-overlay {
      display: none;
    }

    @media (max-width: 768px) {
      .main-area {
        margin-left: 0;
      }

      .sidebar-overlay {
        display: block;
        position: fixed;
        inset: 0;
        background: rgba(0, 0, 0, .4);
        z-index: 99;
        opacity: 0;
        pointer-events: none;
        transition: opacity .2s;
      }

      .sidebar-overlay.visible {
        opacity: 1;
        pointer-events: auto;
      }
    }
  `]
})
export class LayoutComponent {
  private readonly auth = inject(AuthService);
  private readonly career = inject(CareerProfileService);
  private readonly router = inject(Router);

  sidebarOpen = signal(false);

  constructor() {
    /**
     * Send a brand-new account to the first run rather than an empty dashboard.
     *
     * `id > 0` means the profile actually loaded — the placeholder is 0, so this cannot
     * fire mid-request. Only from `/dashboard`, where login lands: redirecting from
     * anywhere else would pull the user off a route they chose.
     */
    effect(() => {
      const profile = this.career.profile();
      const userId = this.auth.userId();
      if (
        profile.id > 0 &&
        userId !== null &&
        this.career.isEmpty() &&
        !hasSeenWelcome(userId) &&
        this.router.url === '/dashboard'
      ) {
        void this.router.navigate(['/welcome']);
      }
    });
  }
}
