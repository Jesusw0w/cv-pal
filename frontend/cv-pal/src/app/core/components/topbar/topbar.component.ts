import { Component, inject, output } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, NavigationEnd, Router } from '@angular/router';
import { filter, map } from 'rxjs';
import { AuthService } from '../../services/auth.service';
import { ThemeService } from '../../services/theme.service';

@Component({
  selector: 'app-topbar',
  template: `
    <header class="topbar">
      <div class="topbar-left">
        <button class="icon-btn hamburger" (click)="menuToggle.emit()">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="3" y1="12" x2="21" y2="12" />
            <line x1="3" y1="6" x2="21" y2="6" />
            <line x1="3" y1="18" x2="21" y2="18" />
          </svg>
        </button>
        <h1 class="page-title">{{ pageTitle() }}</h1>
      </div>
      <div class="topbar-right">
        <button
          class="icon-btn"
          (click)="theme.toggle()"
          [attr.aria-label]="theme.dark() ? 'Switch to light mode' : 'Switch to dark mode'"
        >
          @if (theme.dark()) {
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="5" />
              <line x1="12" y1="1" x2="12" y2="3" />
              <line x1="12" y1="21" x2="12" y2="23" />
              <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
              <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
              <line x1="1" y1="12" x2="3" y2="12" />
              <line x1="21" y1="12" x2="23" y2="12" />
              <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
              <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
            </svg>
          } @else {
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z" />
            </svg>
          }
        </button>
        <button class="icon-btn" (click)="signOut()" aria-label="Sign out">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4" />
            <polyline points="16 17 21 12 16 7" />
            <line x1="21" y1="12" x2="9" y2="12" />
          </svg>
        </button>
      </div>
    </header>
  `,
  styles: [
    `
      .topbar {
        height: var(--topbar-height);
        border-bottom: 1px solid var(--border-light);
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 28px;
        background: var(--bg-primary);
        position: sticky;
        top: 0;
        z-index: 50;
      }

      .topbar-left {
        display: flex;
        align-items: center;
        gap: 12px;
      }

      .page-title {
        font-size: 18px;
        font-weight: 700;
        letter-spacing: -0.3px;
      }

      .topbar-right {
        display: flex;
        align-items: center;
        gap: 4px;
      }

      .icon-btn {
        width: 36px;
        height: 36px;
        border-radius: var(--radius);
        display: flex;
        align-items: center;
        justify-content: center;
        color: var(--text-secondary);
        transition: all 0.15s;
      }

      .icon-btn:hover {
        background: var(--bg-hover);
        color: var(--text-primary);
      }

      .icon-btn svg {
        width: 20px;
        height: 20px;
      }

      .hamburger {
        display: none;
      }

      @media (max-width: 768px) {
        .topbar {
          padding: 0 16px;
        }

        .hamburger {
          display: flex;
        }
      }
    `,
  ],
})
export class TopbarComponent {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  theme = inject(ThemeService);
  menuToggle = output();

  /**
   * The current screen's name, from the route's `data.title`. Read from the router
   * rather than passed in: the topbar outlives every child route, so an input would be
   * one more thing each page has to remember to set.
   */
  readonly pageTitle = toSignal(
    this.router.events.pipe(
      filter((event) => event instanceof NavigationEnd),
      map(() => this.currentTitle()),
    ),
    { initialValue: this.currentTitle() },
  );

  private currentTitle(): string {
    let route = this.route.root;
    while (route.firstChild) {
      route = route.firstChild;
    }
    // Constructed mid-navigation, the deepest route has no snapshot yet and reading
    // through it throws before the first render — a blank page, not a missing title.
    // The NavigationEnd subscription above supplies the real one a moment later.
    return (route.snapshot?.data['title'] as string | undefined) ?? '';
  }

  signOut(): void {
    this.auth.logout();
    void this.router.navigate(['/login']);
  }
}
