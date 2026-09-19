import { Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { DatePipe } from '@angular/common';
import { DashboardService } from '../../core/services/dashboard.service';

@Component({
  selector: 'app-dashboard',
  imports: [RouterLink, DatePipe],
  template: `
    <div class="page">
      <!-- One thing worth doing next, rather than a row of equal tiles. -->
      <a
        class="card next-action"
        [class]="'tone-' + dashboard.nextAction().tone"
        [routerLink]="dashboard.nextAction().link"
      >
        <div class="next-action-body">
          <span class="next-action-eyebrow">Next</span>
          <h2>{{ dashboard.nextAction().headline }}</h2>
          <p>{{ dashboard.nextAction().detail }}</p>
        </div>
        <span class="next-action-cta">
          {{ dashboard.nextAction().cta }}
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            aria-hidden="true"
          >
            <line x1="5" y1="12" x2="19" y2="12" />
            <polyline points="12 5 19 12 12 19" />
          </svg>
        </span>
      </a>

      <!-- The pipeline: where applications stall is the most useful thing to see. -->
      <section class="card funnel" aria-label="Search pipeline">
        @for (stage of dashboard.funnel(); track stage.label; let last = $last) {
          <a class="funnel-stage" [routerLink]="stage.link">
            <span class="funnel-count">{{ stage.count }}</span>
            <span class="funnel-label">{{ stage.label }}</span>
          </a>
          @if (!last) {
            <span class="funnel-arrow" aria-hidden="true">&rsaquo;</span>
          }
        }
      </section>

      <section class="card health" aria-label="Profile health">
        <div class="health-head">
          <span class="health-label">Profile health</span>
          <span class="health-value">{{ dashboard.profileHealth() }}<small>/100</small></span>
        </div>
        <div
          class="health-bar"
          role="progressbar"
          [attr.aria-valuenow]="dashboard.profileHealth()"
          aria-valuemin="0"
          aria-valuemax="100"
        >
          <div class="health-fill" [style.width.%]="dashboard.profileHealth()"></div>
        </div>
        <p class="health-note">
          @if (!dashboard.hasDocuments()) {
            No CV uploaded yet, so there is nothing to score.
          } @else if (dashboard.staleDocuments().length > 0) {
            {{ dashboard.staleDocuments().length }} document(s) not updated in 90 days.
          } @else {
            Everything current. This score falls as CVs age.
          }
        </p>
      </section>

      <div class="content-grid">
        <div class="card">
          <div class="card-header">
            <h3>Recent Documents</h3>
            <a routerLink="/documents" class="card-link">View all</a>
          </div>
          <div class="doc-list">
            @for (doc of dashboard.recentDocuments(); track doc.id) {
              <div class="doc-item">
                <div class="doc-icon doc-icon-cv">CV</div>
                <div class="doc-info">
                  <span class="doc-name">{{ doc.filename }}</span>
                  <span class="doc-date">{{ doc.created_at | date: 'mediumDate' }}</span>
                </div>
                <span class="badge">v{{ doc.version }}</span>
              </div>
            }
          </div>
        </div>

        <div class="card">
          <div class="card-header">
            <h3>Job Matches</h3>
            <a routerLink="/job-search" class="card-link">View all</a>
          </div>
          <div class="job-list">
            @for (entry of dashboard.jobMatches(); track entry.posting.id) {
              <div class="job-item">
                <div class="job-company">{{ entry.posting.company ?? 'Unknown company' }}</div>
                <span class="job-title">{{ entry.posting.title }}</span>
                <div class="job-meta">
                  <span
                    class="badge"
                    [class.badge-green]="entry.match.score >= 80"
                    [class.badge-blue]="entry.match.score < 80"
                    >{{ entry.match.score }}% Match</span
                  >
                  <span class="job-location">{{ entry.posting.location }}</span>
                </div>
              </div>
            } @empty {
              <p class="job-empty">No postings saved yet.</p>
            }
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [
    `
      /* .card, .card-header and .badge come from styles.css; these declare only their
       own layout. Tone signals cost of inaction, not decoration. */
      .next-action {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 24px;
        padding: 24px;
        margin-bottom: 20px;
        text-decoration: none;
        color: inherit;
      }
      .next-action:focus-visible {
        outline: 2px solid var(--accent);
        outline-offset: 2px;
      }
      .next-action h2 {
        margin: 6px 0 4px;
        font-size: 20px;
        line-height: 1.25;
      }
      .next-action p {
        margin: 0;
        color: var(--text-tertiary);
        font-size: 14px;
        max-width: 60ch;
      }
      .next-action-eyebrow {
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--text-tertiary);
      }
      .next-action-cta {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        white-space: nowrap;
        font-weight: 600;
        font-size: 14px;
        color: var(--accent);
      }
      .next-action-cta svg {
        width: 16px;
        height: 16px;
      }
      .tone-attention {
        border-left: 3px solid #ef4444;
      }
      .tone-opportunity {
        border-left: 3px solid var(--accent);
      }

      .funnel {
        display: flex;
        gap: 4px;
        padding: 8px;
        margin-bottom: 20px;
        overflow-x: auto;
      }
      .funnel-stage {
        flex: 1 1 0;
        min-width: 88px;
        padding: 12px 8px;
        border-radius: var(--radius);
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 2px;
        text-decoration: none;
        color: inherit;
      }
      .funnel-stage:focus-visible {
        outline: 2px solid var(--accent);
        outline-offset: -2px;
      }
      .funnel-count {
        font-size: 22px;
        font-weight: 700;
        line-height: 1;
      }
      .funnel-label,
      .funnel-arrow,
      .health-note {
        color: var(--text-tertiary);
      }
      .funnel-label {
        font-size: 12px;
      }
      .funnel-arrow {
        align-self: center;
        font-size: 18px;
      }

      .health {
        padding: 16px 20px;
        margin-bottom: 24px;
      }
      .health-head {
        display: flex;
        justify-content: space-between;
        align-items: baseline;
      }
      .health-label {
        font-size: 13px;
        font-weight: 600;
      }
      .health-value {
        font-size: 20px;
        font-weight: 700;
      }
      .health-value small {
        font-size: 12px;
        font-weight: 500;
        color: var(--text-tertiary);
      }
      .health-bar {
        height: 6px;
        margin: 10px 0 8px;
        border-radius: 999px;
        background: var(--border-light);
        overflow: hidden;
      }
      .health-fill {
        height: 100%;
        background: var(--accent);
      }
      .health-note {
        margin: 0;
        font-size: 12px;
      }

      @media (max-width: 640px) {
        .next-action {
          flex-direction: column;
          align-items: flex-start;
          gap: 12px;
        }
      }

      .page {
        padding: 28px;
      }

      .content-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 20px;
      }

      .doc-list,
      .job-list {
        padding: 8px;
      }

      .doc-item {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 12px;
        border-radius: var(--radius);
        transition: background 0.15s;
        cursor: pointer;
      }

      .doc-item:hover {
        background: var(--bg-hover);
      }

      .doc-icon {
        width: 40px;
        height: 40px;
        border-radius: var(--radius);
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        font-size: 12px;
        flex-shrink: 0;
      }

      .doc-icon-cv {
        background: var(--info-light);
        color: var(--info);
      }
      .doc-icon-cover-letter {
        background: var(--accent-light);
        color: var(--accent);
      }
      .doc-icon-other {
        background: var(--warning-light);
        color: var(--warning);
      }

      .doc-info {
        flex: 1;
        min-width: 0;
      }

      .doc-name {
        display: block;
        font-weight: 500;
        font-size: 14px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .doc-date {
        display: block;
        font-size: 12px;
        color: var(--text-tertiary);
      }

      .job-item {
        padding: 14px 12px;
        border-radius: var(--radius);
        transition: background 0.15s;
        cursor: pointer;
      }

      .job-item:hover {
        background: var(--bg-hover);
      }

      .job-company {
        font-size: 12px;
        font-weight: 500;
        color: var(--accent);
        margin-bottom: 2px;
      }
      .job-title {
        font-weight: 600;
        font-size: 14px;
        display: block;
        margin-bottom: 6px;
      }
      .job-meta {
        display: flex;
        align-items: center;
        gap: 8px;
      }
      .job-empty {
        font-size: 13px;
        color: var(--text-tertiary);
        padding: 12px;
        margin: 0;
      }

      .job-location {
        font-size: 12px;
        color: var(--text-tertiary);
      }

      @media (max-width: 640px) {
        .page {
          padding: 16px;
        }
        .content-grid {
          grid-template-columns: 1fr;
        }
      }
    `,
  ],
})
export class DashboardComponent {
  dashboard = inject(DashboardService);
}
