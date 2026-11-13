import { DatePipe } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { Observable } from 'rxjs';

import { ApplicationService, PIPELINE } from '../../core/services/application.service';
import { AnalysisService } from '../../core/services/analysis.service';
import { Action } from '../../shared/action';
import { ConfirmButtonComponent } from '../../shared/confirm-button.component';
import { PlatformService } from '../../core/services/platform.service';
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
 * What was sent, and what came back. Nothing here is submitted for the user: it is the
 * record of applications they made themselves.
 */
@Component({
  selector: 'app-applications',
  imports: [DatePipe, FormsModule, RouterLink, ConfirmButtonComponent],
  template: `
    <div class="page">
      @if (applications.error()) {
        <p class="card notice" role="alert">
          Could not load your applications.
          <button type="button" class="link" (click)="applications.reload()">Try again</button>
        </p>
      }

      <!-- A real funnel: every application passes between these, and the numbers can
           go down as well as up. -->
      @let stats = applications.stats();
      <section class="card stats" aria-label="Application pipeline">
        @for (status of pipeline; track status) {
          <div class="stat">
            <span class="stat-value">{{ stats.by_status[status] }}</span>
            <span class="muted">{{ label(status) }}</span>
          </div>
          <span class="muted arrow" aria-hidden="true">&rsaquo;</span>
        }
        <div class="stat">
          <span class="stat-value quiet">{{ stats.by_status['rejected'] }}</span>
          <span class="muted">Rejected</span>
        </div>
        <div class="stat rate">
          <!-- A dash, not 0%: "no rate yet" and "nobody replied" are different claims. -->
          <span class="stat-value rate-value">
            @if (stats.reply_rate !== null) {
              {{ stats.reply_rate }}%
            } @else {
              &mdash;
            }
          </span>
          <span class="muted">
            @if (stats.answerable === 0) {
              reply rate &middot; nothing has been out long enough yet
            } @else {
              reply rate &middot; {{ stats.replied }} of {{ stats.answerable }} old enough to answer
            }
          </span>
        </div>
      </section>

      @if (applications.needsChasing().length > 0) {
        <section class="card">
          <div class="card-header">
            <h3>Worth chasing</h3>
            <span class="card-note">Quiet for over two weeks</span>
          </div>
          <ul class="rows">
            @for (application of applications.needsChasing(); track application.id) {
              <li class="row">
                <div class="row-main">
                  <span class="row-title">{{ application.posting.title }}</span>
                  <span class="row-meta">{{
                    application.posting.company ?? 'Unknown company'
                  }}</span>
                </div>
                <span class="warn">{{ application.days_since_applied }} days</span>
              </li>
            }
          </ul>
        </section>
      }

      <section class="card">
        <div class="card-header">
          <h3>Record an application</h3>
          @if (platforms.platforms().length > 0) {
            <!-- Kept for the next click: several in a row usually go through one place. -->
            <label class="card-note through">
              Applied through
              <select [(ngModel)]="through" aria-label="Platform the application went through">
                <option [ngValue]="null">Not recorded</option>
                @for (platform of platforms.platforms(); track platform.id) {
                  <option [ngValue]="platform.id">{{ platform.name }}</option>
                }
              </select>
            </label>
          }
        </div>
        <ul class="rows">
          @for (posting of applications.unapplied(); track posting.id) {
            <li class="row">
              <div class="row-main">
                <span class="row-title">{{ posting.title }}</span>
                <span class="row-meta">{{ posting.company ?? 'Unknown company' }}</span>
              </div>
              <button
                type="button"
                class="link"
                [disabled]="action.busy()"
                (click)="record(posting.id)"
              >
                I applied
              </button>
            </li>
          } @empty {
            <li class="empty">
              Every <a routerLink="/jobs">saved posting</a> has been applied for.
            </li>
          }
        </ul>
        <!-- A recruiter's call or a referral often leaves no posting to save. -->
        <details class="body">
          <summary>Applied without a saved posting?</summary>
          <form class="inline-form" (ngSubmit)="recordRole()">
            <input
              name="title"
              placeholder="Role"
              aria-label="Role"
              maxlength="255"
              [(ngModel)]="manual.title"
            />
            <input
              name="company"
              placeholder="Company"
              aria-label="Company"
              [(ngModel)]="manual.company"
            />
            <input name="url" placeholder="Link" aria-label="Link" [(ngModel)]="manual.url" />
            <input
              name="salary"
              placeholder="Salary offered"
              aria-label="Salary offered"
              [(ngModel)]="manual.salary"
            />
            <input
              name="next"
              placeholder="Next step"
              aria-label="Next step"
              [(ngModel)]="manual.next"
            />
            <button
              type="submit"
              class="primary"
              [disabled]="action.busy() || !manual.title.trim()"
            >
              Record it
            </button>
          </form>
        </details>
        @if (action.error(); as message) {
          <p class="error body" role="alert">{{ message }}</p>
        }
      </section>

      <section class="card">
        <div class="card-header"><h3>All applications</h3></div>
        <ul class="rows">
          @for (application of applications.applications(); track application.id) {
            <li class="row" [class.closed]="isClosed(application)">
              <div class="row-main">
                <span class="row-title">{{ application.posting.title }}</span>
                <span class="row-meta">
                  {{ application.posting.company ?? 'Unknown company' }}
                  &middot; sent {{ application.applied_at | date: 'd MMM y' }}
                  @if (application.cv_id) {
                    &middot; {{ cvName(application.cv_id) }}
                  }
                  @if (application.salary) {
                    &middot; {{ application.salary }}
                  }
                  @if (application.needs_chasing) {
                    &middot;
                    <span class="warn">quiet {{ application.days_since_applied }} days</span>
                  }
                </span>
                @if (application.next_step) {
                  <span class="row-meta">Next: {{ application.next_step }}</span>
                }
                @if (application.notes) {
                  <span class="row-meta">{{ application.notes }}</span>
                }
                @if (editing() === application.id) {
                  <form class="inline-form" (ngSubmit)="saveDetails(application)">
                    <input
                      name="salary"
                      placeholder="Salary offered"
                      aria-label="Salary offered"
                      [(ngModel)]="details.salary"
                    />
                    <input
                      name="next"
                      placeholder="Next step"
                      aria-label="Next step"
                      [(ngModel)]="details.next"
                    />
                    <input
                      name="notes"
                      placeholder="Notes"
                      aria-label="Notes"
                      [(ngModel)]="details.notes"
                    />
                    @if (platforms.platforms().length > 0) {
                      <select name="platform" aria-label="Platform" [(ngModel)]="details.platform">
                        <option [ngValue]="null">No platform</option>
                        @for (platform of platforms.platforms(); track platform.id) {
                          <option [ngValue]="platform.id">{{ platform.name }}</option>
                        }
                      </select>
                    }
                    <button type="submit" class="primary" [disabled]="action.busy()">Save</button>
                    <button type="button" class="link" (click)="editing.set(null)">Cancel</button>
                  </form>
                }
              </div>
              <select
                [ngModel]="application.status"
                (ngModelChange)="setStatus(application, $event)"
                [disabled]="action.busy()"
                [attr.aria-label]="'Status for ' + application.posting.title"
              >
                @for (status of statuses; track status) {
                  <option [value]="status">{{ label(status) }}</option>
                }
              </select>
              <button type="button" class="link" (click)="editDetails(application)">Edit</button>
              <app-confirm-button
                [label]="'Remove the record of applying to ' + application.posting.title"
                [disabled]="action.busy()"
                (confirmed)="remove(application.id)"
                >Remove</app-confirm-button
              >
            </li>
          } @empty {
            <li class="empty">
              Nothing recorded yet. The numbers above are computed from this list.
            </li>
          }
        </ul>
      </section>
    </div>
  `,
  styles: `
    .stats {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px 16px;
      padding: 16px 20px;
    }
    .stat {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 2px;
      min-width: 72px;
    }
    .stat-value {
      font-size: 22px;
      font-weight: 700;
      line-height: 1;
    }
    .quiet {
      color: var(--text-tertiary);
    }
    .arrow {
      font-size: 18px;
    }
    .rate {
      align-items: flex-start;
      margin-left: auto;
      padding-left: 20px;
      border-left: 1px solid var(--border-light);
    }

    .warn {
      font-size: 12px;
      color: var(--warning);
    }
    .through {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .closed .row-title {
      color: var(--text-tertiary);
    }
    summary {
      cursor: pointer;
      font-size: 13px;
      color: var(--text-secondary);
    }
    .inline-form {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px;
      padding-top: 10px;
    }
    select,
    .inline-form input {
      padding: 6px 8px;
      font-size: 13px;
    }
  `,
})
export class ApplicationsComponent {
  readonly applications = inject(ApplicationService);
  readonly platforms = inject(PlatformService);
  private readonly documents = inject(AnalysisService);

  /** The platform the next "I applied" is recorded against. */
  through: number | null = null;

  /** An application recorded from the role alone, with no saved posting. */
  manual = { title: '', company: '', url: '', salary: '', next: '' };

  /** The application whose salary, next step and notes are open for editing. */
  readonly editing = signal<number | null>(null);
  details: { salary: string; next: string; notes: string; platform: number | null } = {
    salary: '',
    next: '',
    notes: '',
    platform: null,
  };

  readonly statuses = STATUSES;
  readonly pipeline = PIPELINE;

  protected readonly action = new Action();

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
    this.run(this.applications.record({ job_posting_id: postingId, platform_id: this.through }));
  }

  recordRole(): void {
    const form = this.manual;
    this.run(
      this.applications.record({
        role: {
          title: form.title.trim(),
          company: form.company.trim() || null,
          source_url: form.url.trim() || null,
        },
        platform_id: this.through,
        salary: form.salary.trim() || null,
        next_step: form.next.trim() || null,
      }),
      () => (this.manual = { title: '', company: '', url: '', salary: '', next: '' }),
    );
  }

  editDetails(application: ApplicationResponse): void {
    this.details = {
      salary: application.salary ?? '',
      next: application.next_step ?? '',
      notes: application.notes ?? '',
      platform: application.platform_id,
    };
    this.editing.set(application.id);
  }

  saveDetails(application: ApplicationResponse): void {
    this.run(
      this.applications.update(application.id, {
        salary: this.details.salary.trim() || null,
        next_step: this.details.next.trim() || null,
        notes: this.details.notes.trim() || null,
        platform_id: this.details.platform,
      }),
      () => this.editing.set(null),
    );
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

  private run<T>(request: Observable<T>, onDone?: () => void): void {
    this.action.run(request, 'That could not be saved.', onDone);
  }
}
