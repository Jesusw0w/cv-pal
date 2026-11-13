import { Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';

import { DashboardService } from '../../core/services/dashboard.service';

/** Answers "what should I do now?": one action, the pipeline, and the best matches. */
@Component({
  selector: 'app-dashboard',
  imports: [RouterLink],
  template: `
    <div class="page">
      @let next = dashboard.nextAction();
      <a class="card next" [class]="next.tone" [routerLink]="next.link">
        <div>
          <span class="eyebrow">Next</span>
          <h2>{{ next.headline }}</h2>
          <p>{{ next.detail }}</p>
        </div>
        <span class="link cta">{{ next.cta }} &rarr;</span>
      </a>

      <!-- Where applications stall is the most useful thing to see. -->
      <section class="card funnel" aria-label="Search pipeline">
        @for (stage of dashboard.funnel(); track stage.label; let last = $last) {
          <a class="stage" [routerLink]="stage.link">
            <span class="count">{{ stage.count }}</span>
            <span class="muted">{{ stage.label }}</span>
          </a>
          @if (!last) {
            <span class="muted arrow" aria-hidden="true">&rsaquo;</span>
          }
        }
      </section>

      <section class="card">
        <div class="card-header">
          <h3>Best matches</h3>
          <a routerLink="/jobs" class="card-link">All jobs</a>
        </div>
        <ul class="rows">
          @for (entry of dashboard.topMatches(); track entry.posting.id) {
            <li class="row">
              <div class="row-main">
                <span class="row-title">{{ entry.posting.title }}</span>
                <span class="row-meta">
                  {{ entry.posting.company ?? 'Unknown company' }}
                  @if (entry.posting.location) {
                    &middot; {{ entry.posting.location }}
                  }
                </span>
              </div>
              <span class="badge" [class]="entry.match.score >= 70 ? 'badge-green' : 'badge-blue'">
                {{ entry.match.score }}/100
              </span>
            </li>
          } @empty {
            <li class="empty">
              No postings saved yet. <a routerLink="/jobs">Add one</a> to see how it scores against
              your goals.
            </li>
          }
        </ul>
      </section>
    </div>
  `,
  styles: `
    .next {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 24px;
      padding: 24px;
      color: inherit;
    }
    .next h2 {
      margin: 6px 0 4px;
      font-size: 20px;
      line-height: 1.25;
    }
    .next p {
      color: var(--text-secondary);
      max-width: 60ch;
    }
    .eyebrow {
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--text-tertiary);
    }
    .cta {
      white-space: nowrap;
    }
    /* Tone signals cost of inaction, not decoration. */
    .attention {
      border-left: 3px solid var(--danger);
    }
    .opportunity {
      border-left: 3px solid var(--accent);
    }

    .funnel {
      display: flex;
      gap: 4px;
      padding: 8px;
      overflow-x: auto;
    }
    .stage {
      flex: 1 1 0;
      min-width: 88px;
      padding: 12px 8px;
      border-radius: var(--radius);
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 2px;
      color: inherit;
    }
    .stage:hover {
      background: var(--bg-hover);
    }
    .count {
      font-size: 22px;
      font-weight: 700;
      line-height: 1;
    }
    .arrow {
      align-self: center;
      font-size: 18px;
    }

    @media (max-width: 640px) {
      .next {
        flex-direction: column;
        align-items: flex-start;
        gap: 12px;
      }
    }
  `,
})
export class DashboardComponent {
  protected readonly dashboard = inject(DashboardService);
}
