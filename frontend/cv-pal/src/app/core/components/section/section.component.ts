import { Component, input } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

export interface SectionTab {
  /** Relative to the section: `./` for its first screen. */
  path: string;
  label: string;
}

/**
 * A sidebar destination with more than one screen: a tab strip over the child route.
 *
 * It is what keeps the sidebar to the steps of a search — goals and the LinkedIn review
 * are parts of the profile, not places of their own. `tabs` arrives from route data.
 */
@Component({
  selector: 'app-section',
  imports: [RouterLink, RouterLinkActive, RouterOutlet],
  template: `
    <nav class="tabs" aria-label="In this section">
      @for (tab of tabs(); track tab.path) {
        <a
          [routerLink]="tab.path"
          routerLinkActive="active"
          ariaCurrentWhenActive="page"
          [routerLinkActiveOptions]="{ exact: true }"
          >{{ tab.label }}</a
        >
      }
    </nav>
    <router-outlet />
  `,
  styles: `
    .tabs {
      padding: 16px 28px 0;
    }
    @media (max-width: 768px) {
      .tabs {
        padding: 12px 16px 0;
      }
    }
  `,
})
export class SectionComponent {
  readonly tabs = input.required<SectionTab[]>();
}
