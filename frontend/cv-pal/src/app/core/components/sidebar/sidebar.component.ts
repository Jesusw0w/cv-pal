import { Component, inject, input, output } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';

import { AuthService } from '../../services/auth.service';

interface NavItem {
  path: string;
  label: string;
  /** One stroked path on a 24px grid. */
  icon: string;
}

/**
 * Ordered by the journey, not by object type: the profile is the record every CV is
 * rendered from, CVs are what a match is checked with, jobs are what gets applied to.
 * Reading top to bottom reads the order the work happens in.
 */
const NAV: NavItem[] = [
  {
    path: '/dashboard',
    label: 'Dashboard',
    icon: 'M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z',
  },
  {
    path: '/profile',
    label: 'Profile',
    icon: 'M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2M12 3a4 4 0 100 8 4 4 0 000-8z',
  },
  {
    path: '/cvs',
    label: 'CVs',
    icon: 'M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8zM14 2v6h6M8 13h8M8 17h8',
  },
  {
    path: '/jobs',
    label: 'Jobs',
    icon: 'M11 3a8 8 0 100 16 8 8 0 000-16zM21 21l-4.35-4.35',
  },
  {
    path: '/applications',
    label: 'Applications',
    icon: 'M9 11l3 3L22 4M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11',
  },
];

const SETTINGS: NavItem = {
  path: '/settings',
  label: 'Settings',
  icon: 'M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6',
};

@Component({
  selector: 'app-sidebar',
  imports: [RouterLink, RouterLinkActive],
  template: `
    <aside class="sidebar" [class.open]="open()">
      <!-- The mark is inlined rather than an <img>: it is drawn with currentColor, and
           an <img> is an isolated document that cannot inherit the page's colour. -->
      <div class="brand">
        <svg viewBox="0 0 32 32" width="32" height="32" aria-hidden="true">
          <path
            fill="currentColor"
            fill-rule="evenodd"
            d="M 8 26.4 L 8 8.2 L 8.35 5.1 Q 8.85 3.5 10.1 4.8 L 13.8 8.2 Q 16 8.9 18.2 8.2 L 21.9 4.8 Q 23.15 3.5 23.65 5.1 L 24 8.2 L 24 26.4 Q 24 29 21.4 29 L 10.6 29 Q 8 29 8 26.4 Z M 11.2 12.5 h 5.2 a 1.1 1.1 0 0 1 0 2.2 h -5.2 a 1.1 1.1 0 0 1 0 -2.2 Z M 11.2 17.1 h 9.6 a 0.85 0.85 0 0 1 0 1.7 h -9.6 a 0.85 0.85 0 0 1 0 -1.7 Z M 11.2 20.5 h 9.6 a 0.85 0.85 0 0 1 0 1.7 h -9.6 a 0.85 0.85 0 0 1 0 -1.7 Z M 11.2 23.9 h 6.4 a 0.85 0.85 0 0 1 0 1.7 h -6.4 a 0.85 0.85 0 0 1 0 -1.7 Z"
          />
        </svg>
        <span>CV Pal</span>
      </div>

      <nav class="nav" aria-label="Main">
        @for (item of nav; track item.path) {
          <a
            [routerLink]="item.path"
            routerLinkActive="active"
            ariaCurrentWhenActive="page"
            class="nav-item"
            (click)="closed.emit()"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true"><path [attr.d]="item.icon" /></svg>
            {{ item.label }}
          </a>
        }
      </nav>

      <a
        [routerLink]="settings.path"
        routerLinkActive="active"
        ariaCurrentWhenActive="page"
        class="nav-item account"
        (click)="closed.emit()"
      >
        <span class="avatar" aria-hidden="true">{{ auth.initials() }}</span>
        <span class="account-text">
          <span class="account-name">{{ auth.displayName() }}</span>
          <span class="account-hint">{{ settings.label }}</span>
        </span>
      </a>
    </aside>
  `,
  styles: `
    .sidebar {
      width: var(--sidebar-width);
      height: 100vh;
      background: var(--sidebar-bg);
      border-right: 1px solid var(--sidebar-border);
      display: flex;
      flex-direction: column;
      position: fixed;
      top: 0;
      left: 0;
      z-index: 100;
      transition: transform 0.2s ease;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 20px 20px 24px;
      font-size: 18px;
      font-weight: 700;
      letter-spacing: -0.3px;
    }
    .brand svg {
      flex: none;
      color: var(--accent);
    }

    .nav {
      flex: 1;
      padding: 0 12px;
      overflow-y: auto;
    }

    .nav-item {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 10px 12px;
      margin-bottom: 2px;
      border-radius: var(--radius);
      color: var(--text-secondary);
      font-weight: 500;
    }
    .nav-item:hover {
      background: var(--bg-hover);
      color: var(--text-primary);
    }
    .nav-item.active {
      background: var(--accent-light);
      color: var(--accent);
    }
    .nav-item svg {
      flex: none;
      width: 20px;
      height: 20px;
      fill: none;
      stroke: currentColor;
      stroke-width: 2;
      stroke-linecap: round;
      stroke-linejoin: round;
    }

    .account {
      margin: 12px;
      border-top: 1px solid var(--border-light);
    }
    .avatar {
      flex: none;
      width: 32px;
      height: 32px;
      border-radius: 50%;
      background: var(--accent);
      color: var(--accent-text);
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 600;
      font-size: 12px;
    }
    .account-text {
      display: flex;
      flex-direction: column;
      min-width: 0;
    }
    .account-name {
      font-weight: 600;
      font-size: 13px;
      color: var(--text-primary);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .account-hint {
      font-size: 12px;
      color: var(--text-tertiary);
    }

    @media (max-width: 768px) {
      .sidebar {
        transform: translateX(-100%);
      }
      .sidebar.open {
        transform: translateX(0);
      }
    }
  `,
})
export class SidebarComponent {
  readonly open = input(false);
  readonly closed = output();

  protected readonly auth = inject(AuthService);
  protected readonly nav = NAV;
  protected readonly settings = SETTINGS;
}
