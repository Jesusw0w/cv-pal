import { DatePipe } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { ApplicationService } from '../../core/services/application.service';
import { JobService } from '../../core/services/job.service';
import { Action } from '../../shared/action';
import { ConfirmButtonComponent } from '../../shared/confirm-button.component';
import { EmploymentType, ScoredPostingResponse } from '../../shared/models/api.model';
import { AddPostingComponent } from './add-posting.component';
import { TailoredComponent } from './tailored.component';

const CONTRACT_LABELS: Record<EmploymentType, string> = {
  full_time: 'Full-time',
  part_time: 'Part-time',
  contract: 'Contract',
  freelance: 'Freelance',
  internship: 'Internship',
  volunteer: 'Volunteer',
  other: 'Other',
};

/**
 * Saved postings, scored against the user's own goals.
 *
 * Two lists on purpose. A posting that broke a non-negotiable is filtered out of the
 * ranking rather than sorted to the bottom — mixing the two would make the order
 * meaningless — and still shown, because a filter the user cannot see is one they
 * cannot revisit.
 */
@Component({
  selector: 'app-jobs',
  imports: [
    DatePipe,
    FormsModule,
    RouterLink,
    AddPostingComponent,
    ConfirmButtonComponent,
    TailoredComponent,
  ],
  template: `
    <div class="page">
      <div class="toolbar">
        <input
          type="search"
          [(ngModel)]="query"
          placeholder="Filter by title, company or place"
          aria-label="Filter postings"
        />
        <label class="check">
          <input type="checkbox" [(ngModel)]="hideApplied" />
          Hide applied
        </label>
        <button type="button" class="primary" (click)="adding.set(!adding())">
          {{ adding() ? 'Close' : 'Add jobs' }}
        </button>
      </div>

      @if (adding()) {
        <app-add-posting />
      }

      @if (action.error(); as message) {
        <p class="error" role="alert">{{ message }}</p>
      }
      @if (jobs.error()) {
        <p class="card notice" role="alert">
          Could not load your jobs.
          <button type="button" class="link" (click)="jobs.reload()">Try again</button>
        </p>
      }

      @for (entry of visible(); track entry.posting.id) {
        @let posting = entry.posting;
        @let applied = applications.appliedPostingIds().has(posting.id);
        <article class="card job">
          <div class="job-head">
            <div>
              <h3>{{ posting.title }}</h3>
              <p class="muted">
                {{ posting.company ?? 'Unknown company' }}
                @if (posting.location) {
                  &middot; {{ posting.location }}
                }
                <!-- Absent when the source did not say: "full time" would be a guess. -->
                @if (posting.employment_type; as type) {
                  &middot; {{ contracts[type] }}
                }
                &middot; saved {{ posting.created_at | date: 'd MMM' }}
              </p>
            </div>
            <span class="score" [class]="tone(entry.match.score)">
              {{ entry.match.score }}<small>/100</small>
            </span>
          </div>

          <ul class="reasons">
            @for (reason of entry.match.reasons; track reason.label) {
              <li>
                <strong>{{ reason.label }}</strong> &mdash; {{ reason.detail }}
              </li>
            }
          </ul>

          @if (entry.match.missing_required.length > 0) {
            <ul class="terms" aria-label="Required, and not on your profile">
              <li class="muted">Required, not on your profile:</li>
              @for (term of entry.match.missing_required; track term) {
                <li class="term required">{{ term }}</li>
              }
            </ul>
          }

          <div class="actions">
            <button
              type="button"
              class="link"
              [attr.aria-expanded]="open() === posting.id"
              (click)="toggle(posting.id)"
            >
              {{ open() === posting.id ? 'Close' : 'Tailor my CV' }}
            </button>
            @if (posting.source_url; as link) {
              <a [href]="link" target="_blank" rel="noopener noreferrer" class="link"
                >Open posting</a
              >
            }
            @if (applied) {
              <a routerLink="/applications" class="muted">Applied &middot; track it</a>
            } @else {
              <button
                type="button"
                class="link"
                [disabled]="action.busy()"
                (click)="markApplied(posting.id)"
              >
                I applied
              </button>
            }
            <app-confirm-button
              class="end"
              [label]="'Remove ' + posting.title"
              [disabled]="action.busy()"
              (confirmed)="remove(posting.id)"
              >Remove</app-confirm-button
            >
          </div>

          <!-- One at a time: two documents on screen is how the wrong one gets sent. -->
          @if (open() === posting.id) {
            <app-tailored [postingId]="posting.id" />
          }
        </article>
      } @empty {
        @if (!jobs.isLoading()) {
          <p class="card notice">
            @if (jobs.matches().length > 0) {
              Nothing matches that filter.
            } @else {
              No postings yet. Press <strong>Add jobs</strong>, then set
              <a routerLink="/profile/goals">your goals</a> so the scores mean something.
            }
          </p>
        }
      }

      @if (jobs.blocked().length > 0) {
        <details class="card">
          <summary class="card-header">
            <h3>{{ jobs.blocked().length }} ruled out by your non-negotiables</h3>
            <span class="card-note">Show</span>
          </summary>
          <ul class="rows">
            @for (entry of jobs.blocked(); track entry.posting.id) {
              <li class="row">
                <div class="row-main">
                  <span class="row-title">{{ entry.posting.title }}</span>
                  <span class="row-meta">{{ entry.match.blocked_by }}</span>
                </div>
                <app-confirm-button
                  [label]="'Remove ' + entry.posting.title"
                  (confirmed)="remove(entry.posting.id)"
                  >Remove</app-confirm-button
                >
              </li>
            }
          </ul>
        </details>
      }
    </div>
  `,
  styles: `
    .toolbar {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 12px;
    }
    .toolbar input[type='search'] {
      flex: 1 1 220px;
    }
    .check {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 13px;
      color: var(--text-secondary);
    }

    .job {
      padding: 18px 20px;
      display: flex;
      flex-direction: column;
      gap: 10px;
    }
    .job-head {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 16px;
    }
    .job-head h3 {
      font-size: 16px;
    }

    .reasons {
      list-style: none;
      display: flex;
      flex-direction: column;
      gap: 4px;
      font-size: 12px;
      color: var(--text-secondary);
    }
    .reasons strong {
      color: var(--text-primary);
      font-weight: 600;
    }
    .terms {
      align-items: center;
    }

    .actions {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 14px;
    }
    .actions .muted {
      font-size: 13px;
    }
    .end {
      margin-left: auto;
    }

    summary {
      cursor: pointer;
      border-bottom: 0;
    }
  `,
})
export class JobsComponent {
  protected readonly jobs = inject(JobService);
  protected readonly applications = inject(ApplicationService);
  protected readonly action = new Action();
  protected readonly contracts = CONTRACT_LABELS;

  protected readonly query = signal('');
  protected readonly hideApplied = signal(false);
  protected readonly adding = signal(false);
  /** The posting whose tailored CV is open, or null. */
  protected readonly open = signal<number | null>(null);

  protected readonly visible = computed(() => {
    const query = this.query().trim().toLowerCase();
    const applied = this.hideApplied() ? this.applications.appliedPostingIds() : null;
    return this.jobs
      .matches()
      .filter((entry) => !applied?.has(entry.posting.id) && matchesQuery(entry, query));
  });

  protected tone(score: number): string {
    if (score >= 70) return 'good';
    return score >= 45 ? 'fair' : 'poor';
  }

  protected toggle(postingId: number): void {
    this.open.update((current) => (current === postingId ? null : postingId));
  }

  /** Record an application straight from the posting it is for. */
  protected markApplied(postingId: number): void {
    this.action.run(
      this.applications.record({ job_posting_id: postingId }),
      'That application could not be recorded.',
    );
  }

  protected remove(postingId: number): void {
    this.action.run(this.jobs.remove(postingId), 'That posting could not be removed.', () =>
      this.jobs.reload(),
    );
  }
}

function matchesQuery(entry: ScoredPostingResponse, query: string): boolean {
  const { title, company, location } = entry.posting;
  return [title, company, location].some((field) => field?.toLowerCase().includes(query));
}
