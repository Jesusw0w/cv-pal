import { HttpErrorResponse } from '@angular/common/http';
import { DatePipe } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { ApplicationService } from '../../core/services/application.service';
import { AnalysisService } from '../../core/services/analysis.service';
import { ApplicationResponse, ApplicationStatus } from '../../shared/models/api.model';

const STATUS_LABELS: Record<ApplicationStatus, string> = {
  applied: 'Applied',
  interviewing: 'Interviewing',
  offer: 'Offer',
  rejected: 'Rejected',
  withdrawn: 'Withdrawn',
};

/** The order a status list should read in: open first, closed last. */
const STATUSES: ApplicationStatus[] = ['applied', 'interviewing', 'offer', 'rejected', 'withdrawn'];

/**
 * What was sent, and what came back.
 *
 * The screen the product was missing. Everything before it prepares an application;
 * nothing recorded whether one was made, which is why the dashboard's "funnel" was
 * three counts that only ever grew.
 */
@Component({
  selector: 'app-applications',
  imports: [DatePipe, FormsModule, RouterLink],
  template: `
    <div class="page">
      <header class="intro">
        <h1>Applications</h1>
        <p>
          What you sent and what came back. Nothing here is submitted for you — this is the record
          of applications you made yourself.
        </p>
      </header>

      @if (applications.error()) {
        <p class="card notice" role="alert">
          Could not load your applications.
          <button type="button" class="retry" (click)="applications.reload()">Try again</button>
        </p>
      }

      <!-- A real funnel: every application passes between these, and the numbers can
           go down as well as up. -->
      <section class="card funnel" aria-label="Application pipeline">
        @for (status of pipeline; track status; let last = $last) {
          <div class="funnel-stage">
            <span class="funnel-count">{{ applications.stats().by_status[status] }}</span>
            <span class="funnel-label">{{ label(status) }}</span>
          </div>
          @if (!last) {
            <span class="funnel-arrow" aria-hidden="true">&rsaquo;</span>
          }
        }
        <div class="funnel-stage muted">
          <span class="funnel-count">{{ applications.stats().by_status['rejected'] }}</span>
          <span class="funnel-label">Rejected</span>
        </div>
      </section>

      <section class="card rate">
        <div class="rate-figure">
          <span class="rate-value">
            @if (applications.stats().reply_rate; as rate) {
              {{ rate }}<small>%</small>
            } @else {
              &mdash;
            }
          </span>
          <span class="rate-label">reply rate</span>
        </div>
        <p class="rate-note">
          @if (applications.stats().answerable === 0) {
            Nothing has been out long enough to expect an answer yet. A rate before then would only
            be measuring how recently you applied.
          } @else {
            {{ applications.stats().replied }} of {{ applications.stats().answerable }} applications
            old enough to have been answered got a reply.
          }
        </p>
      </section>

      @if (applications.needsChasing().length > 0) {
        <section class="card chase">
          <div class="card-header">
            <h3>Worth chasing</h3>
            <span class="card-note">Quiet for over two weeks</span>
          </div>
          <div class="rows">
            @for (application of applications.needsChasing(); track application.id) {
              <div class="chase-row">
                <span class="chase-title">{{ application.posting.title }}</span>
                <span class="chase-org">{{
                  application.posting.company ?? 'Unknown company'
                }}</span>
                <span class="chase-age">{{ application.days_since_applied }} days</span>
              </div>
            }
          </div>
        </section>
      }

      <!-- Recording an application is the whole point, so it is one click from a saved
           posting rather than a form asking you to retype the role. -->
      <section class="card">
        <div class="card-header">
          <h3>Record an application</h3>
          <span class="card-note"
            >{{ applications.unapplied().length }} saved posting(s) not applied for</span
          >
        </div>
        @if (applications.unapplied().length === 0) {
          <p class="body muted">
            Nothing left to record. <a routerLink="/job-search">Save a posting</a> first —
            applications are recorded against one.
          </p>
        } @else {
          <div class="rows">
            @for (posting of applications.unapplied(); track posting.id) {
              <div class="chase-row">
                <span class="chase-title">{{ posting.title }}</span>
                <span class="chase-org">{{ posting.company ?? 'Unknown company' }}</span>
                <button type="button" class="link" [disabled]="busy()" (click)="record(posting.id)">
                  I applied
                </button>
              </div>
            }
          </div>
        }
        @if (error(); as message) {
          <p class="error" role="alert">{{ message }}</p>
        }
      </section>

      <section class="card">
        <div class="card-header">
          <h3>All applications</h3>
        </div>
        @if (applications.applications().length === 0) {
          <p class="body muted">
            Nothing recorded yet. Every number above is computed from this list, so it stays empty
            until you record the first one.
          </p>
        }
        <div class="rows">
          @for (application of applications.applications(); track application.id) {
            <div class="entry" [class.closed]="isClosed(application)">
              <div class="entry-main">
                <span class="entry-title">{{ application.posting.title }}</span>
                <span class="entry-meta">
                  {{ application.posting.company ?? 'Unknown company' }}
                  &middot; sent {{ application.applied_at | date: 'd MMM y' }}
                  @if (application.cv_id) {
                    &middot; {{ cvName(application.cv_id) }}
                  } @else {
                    &middot; <span class="muted">no CV recorded</span>
                  }
                  @if (application.needs_chasing) {
                    &middot;
                    <span class="warn">quiet {{ application.days_since_applied }} days</span>
                  }
                </span>
              </div>
              <select
                [ngModel]="application.status"
                (ngModelChange)="setStatus(application, $event)"
                [disabled]="busy()"
                [attr.aria-label]="'Status for ' + application.posting.title"
              >
                @for (status of statuses; track status) {
                  <option [value]="status">{{ label(status) }}</option>
                }
              </select>
              <button
                type="button"
                class="remove"
                [disabled]="busy()"
                [attr.aria-label]="'Remove the record of applying to ' + application.posting.title"
                (click)="remove(application.id)"
              >
                Remove
              </button>
            </div>
          }
        </div>
      </section>
    </div>
  `,
  styles: [
    `
      /* .card, .card-header and .badge come from styles.css. */
      .page {
        padding: 28px;
        display: flex;
        flex-direction: column;
        gap: 20px;
      }
      .intro h1 {
        margin: 0 0 4px;
        font-size: 22px;
      }
      .intro p {
        margin: 0;
        font-size: 14px;
        color: var(--text-tertiary);
        max-width: 70ch;
      }

      .funnel {
        display: flex;
        gap: 4px;
        padding: 12px 8px;
        overflow-x: auto;
      }
      .funnel-stage {
        flex: 1 1 0;
        min-width: 88px;
        padding: 10px 8px;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 2px;
      }
      .funnel-stage.muted .funnel-count {
        color: var(--text-tertiary);
      }
      .funnel-count {
        font-size: 22px;
        font-weight: 700;
        line-height: 1;
      }
      .funnel-label {
        font-size: 12px;
        color: var(--text-tertiary);
      }
      .funnel-arrow {
        align-self: center;
        font-size: 18px;
        color: var(--text-tertiary);
      }

      .rate {
        display: flex;
        align-items: center;
        gap: 20px;
        padding: 16px 20px;
      }
      .rate-figure {
        display: flex;
        flex-direction: column;
        align-items: center;
        min-width: 90px;
      }
      .rate-value {
        font-size: 28px;
        font-weight: 700;
        line-height: 1;
      }
      .rate-value small {
        font-size: 14px;
        font-weight: 500;
        color: var(--text-tertiary);
      }
      .rate-label {
        font-size: 12px;
        color: var(--text-tertiary);
      }
      .rate-note {
        margin: 0;
        font-size: 13px;
        color: var(--text-secondary);
        max-width: 62ch;
      }

      .rows {
        padding: 4px 18px 16px;
        display: flex;
        flex-direction: column;
      }
      .body {
        padding: 4px 18px 16px;
        font-size: 13px;
      }
      .muted {
        color: var(--text-tertiary);
      }
      .warn {
        color: #d97706;
      }
      .error {
        margin: 0;
        padding: 0 18px 14px;
        font-size: 13px;
        color: var(--danger, #dc2626);
      }

      .chase-row,
      .entry {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 9px 0;
        border-top: 1px solid var(--border-light);
      }
      .chase-row:first-child,
      .entry:first-child {
        border-top: 0;
      }
      .chase-title,
      .entry-title {
        font-size: 14px;
        font-weight: 600;
      }
      .chase-org {
        flex: 1;
        font-size: 12px;
        color: var(--text-tertiary);
      }
      .chase-age {
        font-size: 12px;
        color: #d97706;
      }

      .entry-main {
        flex: 1;
        min-width: 0;
        display: flex;
        flex-direction: column;
        gap: 2px;
      }
      .entry-meta {
        font-size: 12px;
        color: var(--text-tertiary);
      }
      .entry.closed .entry-title {
        color: var(--text-tertiary);
      }
      .entry select {
        flex: none;
        padding: 6px 8px;
        font-size: 13px;
        border: 1px solid var(--border-light);
        border-radius: var(--radius);
        background: var(--bg-primary);
        color: var(--text-primary);
      }
      .remove {
        flex: none;
        font-size: 12px;
        color: var(--text-tertiary);
      }
      .remove:hover:not(:disabled) {
        color: var(--danger, #dc2626);
      }
      .link {
        font-size: 13px;
        font-weight: 600;
        color: var(--accent);
      }
      .link:disabled,
      .remove:disabled {
        opacity: 0.5;
      }
      .retry {
        font-size: 13px;
        font-weight: 600;
        color: var(--accent);
      }

      @media (max-width: 768px) {
        .entry {
          flex-wrap: wrap;
        }
      }
    `,
  ],
})
export class ApplicationsComponent {
  readonly applications = inject(ApplicationService);
  private readonly documents = inject(AnalysisService);

  readonly statuses = STATUSES;
  readonly pipeline: ApplicationStatus[] = ['applied', 'interviewing', 'offer'];

  readonly busy = signal(false);
  readonly error = signal<string | null>(null);

  private readonly cvNames = computed(
    () => new Map(this.documents.documents().map((cv) => [cv.id, cv.filename])),
  );

  label(status: ApplicationStatus): string {
    return STATUS_LABELS[status];
  }

  cvName(cvId: number): string {
    // The CV may have been deleted since; the row survives it, so the label has to.
    return this.cvNames().get(cvId) ?? 'a CV since deleted';
  }

  isClosed(application: ApplicationResponse): boolean {
    return ['rejected', 'withdrawn'].includes(application.status);
  }

  record(postingId: number): void {
    this.run(this.applications.record({ job_posting_id: postingId }));
  }

  setStatus(application: ApplicationResponse, status: ApplicationStatus): void {
    if (status === application.status) {
      return;
    }
    this.run(this.applications.update(application.id, { status }));
  }

  remove(id: number): void {
    this.run(this.applications.remove(id));
  }

  private run(request: { subscribe: (o: object) => void }): void {
    this.busy.set(true);
    this.error.set(null);
    request.subscribe({
      next: () => this.busy.set(false),
      error: (error: unknown) => {
        this.busy.set(false);
        this.error.set(detailOf(error, 'That could not be saved.'));
      },
    });
  }
}

function detailOf(error: unknown, fallback: string): string {
  if (error instanceof HttpErrorResponse) {
    const detail = (error.error as { detail?: unknown } | null)?.detail;
    if (typeof detail === 'string') {
      return detail;
    }
  }
  return fallback;
}
