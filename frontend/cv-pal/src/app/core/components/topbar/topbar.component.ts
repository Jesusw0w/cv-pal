import { Component, inject, output } from '@angular/core';
import { Router } from '@angular/router';

import { PageTitleStrategy } from '../../page-title';
import { AuthService } from '../../services/auth.service';
import { ThemeService } from '../../services/theme.service';

@Component({
  selector: 'app-topbar',
  template: `
    <header class="topbar">
      <button type="button" class="icon-btn menu" aria-label="Open the menu" (click)="menu.emit()">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6h18M3 12h18M3 18h18" /></svg>
      </button>
      <!-- The page's one heading: screens do not repeat their own name under it. -->
      <h1>{{ title.current() }}</h1>
      <button
        type="button"
        class="icon-btn"
        [attr.aria-label]="theme.dark() ? 'Switch to light mode' : 'Switch to dark mode'"
        (click)="theme.toggle()"
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          @if (theme.dark()) {
            <path
              d="M12 7a5 5 0 100 10 5 5 0 000-10zM12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"
            />
          } @else {
            <path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z" />
          }
        </svg>
      </button>
      <button type="button" class="icon-btn" aria-label="Sign out" (click)="signOut()">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9" />
        </svg>
      </button>
    </header>
  `,
  styles: `
    .topbar {
      height: var(--topbar-height);
      border-bottom: 1px solid var(--border-light);
      display: flex;
      align-items: center;
      gap: 4px;
      padding: 0 28px;
      background: var(--bg-primary);
      position: sticky;
      top: 0;
      z-index: 50;
    }

    h1 {
      flex: 1;
      font-size: 18px;
      font-weight: 700;
      letter-spacing: -0.3px;
    }

    .icon-btn {
      width: 36px;
      height: 36px;
      border-radius: var(--radius);
      display: flex;
      align-items: center;
      justify-content: center;
      color: var(--text-secondary);
    }
    .icon-btn:hover {
      background: var(--bg-hover);
      color: var(--text-primary);
    }
    .icon-btn svg {
      width: 20px;
      height: 20px;
      fill: none;
      stroke: currentColor;
      stroke-width: 2;
      stroke-linecap: round;
      stroke-linejoin: round;
    }

    .menu {
      display: none;
      margin-right: 8px;
    }

    @media (max-width: 768px) {
      .topbar {
        padding: 0 16px;
      }
      .menu {
        display: flex;
      }
    }
  `,
})
export class TopbarComponent {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  protected readonly title = inject(PageTitleStrategy);
  protected readonly theme = inject(ThemeService);

  readonly menu = output();

  protected signOut(): void {
    this.auth.logout();
    void this.router.navigate(['/login']);
  }
}
