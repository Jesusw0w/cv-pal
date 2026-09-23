import { Component, input, output, inject } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-sidebar',
  imports: [RouterLink, RouterLinkActive],
  template: `
    <aside class="sidebar" [class.open]="open()">
      <!-- The mark is inlined rather than an <img src="logo.svg">: it is drawn with
           fill="currentColor", and an <img> is an isolated document that cannot
           inherit the page's colour. Inline, one CSS rule themes it in both modes and
           it costs no extra request. -->
      <div class="sidebar-brand">
        <svg class="brand-icon" viewBox="0 0 32 32" width="32" height="32" aria-hidden="true">
          <path
            fill="currentColor"
            fill-rule="evenodd"
            d="M 8 26.4 L 8 8.2 L 8.35 5.1 Q 8.85 3.5 10.1 4.8 L 13.8 8.2 Q 16 8.9 18.2 8.2 L 21.9 4.8 Q 23.15 3.5 23.65 5.1 L 24 8.2 L 24 26.4 Q 24 29 21.4 29 L 10.6 29 Q 8 29 8 26.4 Z M 11.2 12.5 h 5.2 a 1.1 1.1 0 0 1 0 2.2 h -5.2 a 1.1 1.1 0 0 1 0 -2.2 Z M 11.2 17.1 h 9.6 a 0.85 0.85 0 0 1 0 1.7 h -9.6 a 0.85 0.85 0 0 1 0 -1.7 Z M 11.2 20.5 h 9.6 a 0.85 0.85 0 0 1 0 1.7 h -9.6 a 0.85 0.85 0 0 1 0 -1.7 Z M 11.2 23.9 h 6.4 a 0.85 0.85 0 0 1 0 1.7 h -6.4 a 0.85 0.85 0 0 1 0 -1.7 Z"
          />
        </svg>
        <span class="brand-text">CV Pal</span>
      </div>

      <!-- Ordered by the journey, not by object type: the profile is the source every
           CV is rendered from, so it comes before documents; documents are what a match
           is applied with, so they come before the search. A user reading top to bottom
           reads the order the work actually happens in. -->
      <nav class="sidebar-nav">
        <a
          routerLink="/dashboard"
          routerLinkActive="active"
          class="nav-item"
          (click)="closed.emit()"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="3" y="3" width="7" height="7" rx="1" />
            <rect x="14" y="3" width="7" height="7" rx="1" />
            <rect x="3" y="14" width="7" height="7" rx="1" />
            <rect x="14" y="14" width="7" height="7" rx="1" />
          </svg>
          <span>Dashboard</span>
        </a>
        <a routerLink="/profile" routerLinkActive="active" class="nav-item" (click)="closed.emit()">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" />
            <circle cx="12" cy="7" r="4" />
          </svg>
          <span>Career Profile</span>
        </a>
        <a routerLink="/goals" routerLinkActive="active" class="nav-item" (click)="closed.emit()">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10" />
            <circle cx="12" cy="12" r="6" />
            <circle cx="12" cy="12" r="2" />
          </svg>
          <span>Goals</span>
        </a>
        <a
          routerLink="/documents"
          routerLinkActive="active"
          class="nav-item"
          (click)="closed.emit()"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="16" y1="13" x2="8" y2="13" />
            <line x1="16" y1="17" x2="8" y2="17" />
            <polyline points="10 9 9 9 8 9" />
          </svg>
          <span>Documents</span>
        </a>
        <a
          routerLink="/analysis"
          routerLinkActive="active"
          class="nav-item"
          (click)="closed.emit()"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M3 3v18h18" />
            <polyline points="7 14 11 10 15 13 21 7" />
          </svg>
          <span>CV Analysis</span>
        </a>
        <a
          routerLink="/job-search"
          routerLinkActive="active"
          class="nav-item"
          (click)="closed.emit()"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <span>Job Search</span>
        </a>
        <a
          routerLink="/applications"
          routerLinkActive="active"
          class="nav-item"
          (click)="closed.emit()"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M9 11l3 3L22 4" />
            <path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11" />
          </svg>
          <span>Applications</span>
        </a>
        <a
          routerLink="/platforms"
          routerLinkActive="active"
          class="nav-item"
          (click)="closed.emit()"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="3" y="3" width="7" height="7" rx="1" />
            <rect x="14" y="3" width="7" height="7" rx="1" />
            <rect x="3" y="14" width="7" height="7" rx="1" />
            <rect x="14" y="14" width="7" height="7" rx="1" />
          </svg>
          <span>Platforms</span>
        </a>
        <a
          routerLink="/linkedin"
          routerLinkActive="active"
          class="nav-item"
          (click)="closed.emit()"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M16 8a6 6 0 016 6v7h-4v-7a2 2 0 00-4 0v7h-4v-7a6 6 0 016-6z" />
            <rect x="2" y="9" width="4" height="12" />
            <circle cx="4" cy="4" r="2" />
          </svg>
          <span>LinkedIn</span>
        </a>
        <a
          routerLink="/ai-tools"
          routerLinkActive="active"
          class="nav-item"
          (click)="closed.emit()"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 2a4 4 0 014 4c0 1.95-1.4 3.57-3.25 3.93a1.5 1.5 0 00-1.5 1.5V13" />
            <circle cx="12" cy="17" r="1" />
            <path
              d="M4.93 4.93l1.41 1.41M17.66 4.93l-1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 19.07l-1.41-1.41"
            />
          </svg>
          <span>AI Tools</span>
        </a>

        <div class="nav-divider"></div>

        <a
          routerLink="/settings"
          routerLinkActive="active"
          class="nav-item"
          (click)="closed.emit()"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="3" />
            <path
              d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z"
            />
          </svg>
          <span>Settings</span>
        </a>
      </nav>

      <div class="sidebar-footer">
        <div class="user-avatar">{{ auth.initials() }}</div>
        <div class="user-info">
          <span class="user-name">{{ auth.displayName() }}</span>
        </div>
      </div>
    </aside>
  `,
  styles: [
    `
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

      .sidebar-brand {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 20px 20px 24px;
      }

      /* The color property is what themes the mark — the path is fill="currentColor",
       so the accent follows light and dark mode without a second asset. Decorative:
       the adjacent .brand-text already names the app to a screen reader. */
      .brand-icon {
        width: 32px;
        height: 32px;
        flex-shrink: 0;
        color: var(--accent);
      }

      .brand-text {
        font-size: 18px;
        font-weight: 700;
        color: var(--text-primary);
        letter-spacing: -0.3px;
      }

      .sidebar-nav {
        flex: 1;
        padding: 0 12px;
        overflow-y: auto;
      }

      .nav-item {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 10px 12px;
        border-radius: var(--radius);
        color: var(--text-secondary);
        font-weight: 500;
        transition: all 0.15s;
        margin-bottom: 2px;
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
        width: 20px;
        height: 20px;
        flex-shrink: 0;
      }

      .nav-divider {
        height: 1px;
        background: var(--border-light);
        margin: 8px 12px;
      }

      .sidebar-footer {
        padding: 16px 20px;
        border-top: 1px solid var(--border-light);
        display: flex;
        align-items: center;
        gap: 10px;
      }

      .user-avatar {
        width: 36px;
        height: 36px;
        border-radius: 50%;
        background: var(--accent);
        color: white;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 600;
        font-size: 13px;
        flex-shrink: 0;
      }

      .user-info {
        display: flex;
        flex-direction: column;
        min-width: 0;
      }

      .user-name {
        font-weight: 600;
        font-size: 13px;
        color: var(--text-primary);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .user-role {
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
  ],
})
export class SidebarComponent {
  open = input(false);
  closed = output();
  auth = inject(AuthService);
}
