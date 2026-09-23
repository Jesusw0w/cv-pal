import { DatePipe, NgTemplateOutlet } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { Observable } from 'rxjs';

import { ApplicationService } from '../../core/services/application.service';
import { PlatformService } from '../../core/services/platform.service';
import { detailOf } from '../../shared/http-error';
import {
  JobPlatformResponse,
  PlatformState,
  PlatformStats,
  PlatformStatus,
} from '../../shared/models/api.model';

const STATUS_LABELS: Record<PlatformStatus, string> = {
  up_to_date: 'Up to date',
  outdated: 'Behind your profile',
  unknown: 'Never marked',
};

/** Offered as suggestions, not a fixed list: the user types whatever they use. */
const SUGGESTIONS = [
  'LinkedIn',
  'Indeed',
  'Glassdoor',
  'Wellfound',
  'Welcome to the Jungle',
  'Otta',
  'Landing.jobs',
  'Himalayas',
  'Arc.dev',
  'Cord',
  'Remote OK',
  'We Work Remotely',
];

/** A platform being edited: every field as the form holds it. */
interface Draft {
  name: string;
  state: PlatformState;
  profile_url: string;
  profile_updated_on: string;
  notes: string;
}

const EMPTY_DRAFT: Draft = {
  name: '',
  state: 'active',
  profile_url: '',
  profile_updated_on: '',
  notes: '',
};

const STATES: { value: PlatformState; label: string }[] = [
  { value: 'active', label: 'Active' },
  { value: 'setting_up', label: 'Setting up' },
  { value: 'not_started', label: 'Not started' },
  { value: 'later', label: 'Later' },
  { value: 'paused', label: 'Paused' },
];

/**
 * Job platforms the user keeps a profile on. Entirely optional.
 *
 * Two questions, one screen: which platforms still show an older version of the
 * profile, and which ones produce replies. "Up to date" can only mean "updated on or
 * after the last change to the profile here" — nothing logs in to any platform.
 */
@Component({
  selector: 'app-platforms',
  imports: [DatePipe, FormsModule, NgTemplateOutlet, RouterLink],
  template: `
    <div class="page">
      <header class="intro">
        <h1>Platforms</h1>
        <p>
          Optional. List the job platforms where you keep a profile to see which ones still show an
          older version of it, and — once you record which platform each
          <a routerLink="/applications">application</a> went through — which ones get replies.
        </p>
      </header>

      @if (platforms.error()) {
        <p class="card notice" role="alert">Could not load your platforms.</p>
      }

      @if (platforms.platforms().length > 0) {
        <section class="card">
          <div class="card-header">
            <h3>Your platforms</h3>
            <span class="card-note">
              @if (platforms.outdated().length === 0) {
                None behind your profile
              } @else {
                {{ platforms.outdated().length }} behind your profile
              }
            </span>
          </div>
          <ul class="rows">
            @for (platform of platforms.platforms(); track platform.id) {
              <li class="row">
                @if (editing() === platform.id) {
                  <div class="form">
                    <ng-container
                      *ngTemplateOutlet="fields; context: { draft: edited }"
                    ></ng-container>
                    <div class="actions">
                      <button type="button" class="ghost" (click)="editing.set(null)">
                        Cancel
                      </button>
                      <button
                        type="button"
                        class="primary"
                        [disabled]="busy() || !edited.name.trim()"
                        (click)="save(platform)"
                      >
                        Save
                      </button>
                    </div>
                  </div>
                } @else {
                  <div class="row-main">
                    <span class="row-title">
                      @if (platform.profile_url) {
                        <a [href]="link(platform.profile_url)" target="_blank" rel="noopener">{{
                          platform.name
                        }}</a>
                      } @else {
                        {{ platform.name }}
                      }
                      @if (platform.state === 'active') {
                        <span class="status" [class]="platform.status">{{
                          label(platform.status)
                        }}</span>
                      } @else {
                        <span class="status">{{ stateLabel(platform.state) }}</span>
                      }
                    </span>
                    <span class="row-meta">
                      @if (platform.profile_updated_on) {
                        Updated {{ platform.profile_updated_on | date: 'd MMM y' }}
                      } @else {
                        No update date yet
                      }
                      @if (statsFor(platform); as stats) {
                        &middot; {{ stats.total }} sent &middot;
                        @if (stats.reply_rate === null) {
                          too early for a reply rate
                        } @else {
                          {{ stats.reply_rate }}% replied
                        }
                      }
                      @if (platform.notes) {
                        &middot; {{ platform.notes }}
                      }
                    </span>
                  </div>
                  @if (platform.state === 'active' && platform.status !== 'up_to_date') {
                    <button
                      type="button"
                      class="link"
                      [disabled]="busy()"
                      (click)="markUpdated(platform)"
                    >
                      Updated today
                    </button>
                  }
                  <button type="button" class="link quiet" (click)="edit(platform)">Edit</button>
                  <button
                    type="button"
                    class="link quiet remove"
                    [disabled]="busy()"
                    [attr.aria-label]="'Stop tracking ' + platform.name"
                    (click)="remove(platform)"
                  >
                    Remove
                  </button>
                }
              </li>
            }
          </ul>
        </section>
      }

      <section class="card">
        <div class="card-header"><h3>Add a platform</h3></div>
        <div class="form body">
          <ng-container *ngTemplateOutlet="fields; context: { draft: fresh }"></ng-container>
          @if (error(); as message) {
            <p class="error" role="alert">{{ message }}</p>
          }
          <div class="actions">
            <button
              type="button"
              class="primary"
              [disabled]="busy() || !fresh.name.trim()"
              (click)="add()"
            >
              Add platform
            </button>
          </div>
        </div>
      </section>

      <datalist id="platform-suggestions">
        @for (name of suggestions; track name) {
          <option [value]="name"></option>
        }
      </datalist>

      <ng-template #fields let-draft="draft">
        <label class="field">
          <span>Stage</span>
          <select [(ngModel)]="draft.state">
            @for (option of states; track option.value) {
              <option [value]="option.value">{{ option.label }}</option>
            }
          </select>
        </label>
        <label class="field">
          <span>Name</span>
          <input
            list="platform-suggestions"
            maxlength="64"
            placeholder="e.g. Wellfound"
            [(ngModel)]="draft.name"
          />
        </label>
        <label class="field">
          <span>Your profile there (optional)</span>
          <input
            type="url"
            placeholder="https://…"
            maxlength="512"
            [(ngModel)]="draft.profile_url"
          />
        </label>
        <label class="field">
          <span>Last brought up to date (optional)</span>
          <input type="date" [max]="today" [(ngModel)]="draft.profile_updated_on" />
        </label>
        <label class="field">
          <span>Notes (optional)</span>
          <input maxlength="200" [(ngModel)]="draft.notes" />
        </label>
      </ng-template>
    </div>
  `,
  styles: [
    `
      .rows {
        list-style: none;
        margin: 0;
        padding: 0 18px 8px;
      }
      .row {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 10px 0;
      }
      .row + .row {
        border-top: 1px solid var(--border-light);
      }
      .row-main {
        flex: 1;
        min-width: 0;
        display: flex;
        flex-direction: column;
        gap: 3px;
      }
      .row-title {
        font-size: 14px;
        font-weight: 600;
      }
      .row-meta {
        font-size: 12px;
        color: var(--text-tertiary);
      }
      .status {
        margin-left: 8px;
        padding: 1px 8px;
        border-radius: 999px;
        font-size: 11px;
        font-weight: 600;
        background: var(--bg-hover);
        color: var(--text-secondary);
      }
      .status.up_to_date {
        color: var(--success, #16a34a);
      }
      .status.outdated {
        color: #d97706;
      }
      .form {
        flex: 1;
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 10px;
      }
      .body {
        padding: 8px 18px 18px;
      }
      .field > span {
        display: block;
        margin-bottom: 4px;
        font-size: 12px;
        font-weight: 600;
        color: var(--text-secondary);
      }
      .field input {
        width: 100%;
        padding: 8px 10px;
        font: inherit;
        font-size: 14px;
        border: 1px solid var(--border-light);
        border-radius: var(--radius);
        background: var(--bg-primary);
        color: var(--text-primary);
      }
      .actions {
        grid-column: 1 / -1;
        display: flex;
        justify-content: flex-end;
        gap: 10px;
      }
      .link {
        flex: none;
        font-size: 13px;
        font-weight: 600;
        color: var(--accent);
      }
      .link.quiet {
        color: var(--text-tertiary);
      }
      .link:disabled {
        opacity: 0.5;
      }
      .error {
        grid-column: 1 / -1;
        margin: 0;
        font-size: 13px;
        color: var(--danger, #dc2626);
      }
      @media (max-width: 768px) {
        .row {
          flex-wrap: wrap;
        }
      }
    `,
  ],
})
export class PlatformsComponent {
  readonly platforms = inject(PlatformService);
  private readonly applications = inject(ApplicationService);

  readonly suggestions = SUGGESTIONS;
  readonly states = STATES;
  readonly today = isoToday();

  readonly busy = signal(false);
  readonly error = signal<string | null>(null);
  /** The platform whose row is open for editing. */
  readonly editing = signal<number | null>(null);

  fresh: Draft = { ...EMPTY_DRAFT };
  edited: Draft = { ...EMPTY_DRAFT };

  constructor() {
    // Statuses are computed against the profile, which may have changed since the list
    // was loaded elsewhere in this session.
    this.platforms.reload();
  }

  private readonly stats = computed(
    () =>
      new Map(
        this.applications
          .stats()
          .by_platform.filter((row) => row.platform_id !== null)
          .map((row) => [row.platform_id, row]),
      ),
  );

  label(status: PlatformStatus): string {
    return STATUS_LABELS[status];
  }

  stateLabel(state: PlatformState): string {
    return STATES.find((option) => option.value === state)?.label ?? state;
  }

  statsFor(platform: JobPlatformResponse): PlatformStats | undefined {
    return this.stats().get(platform.id);
  }

  /** Profile links are often typed without a scheme; the browser needs one. */
  link(url: string): string {
    return /^https?:\/\//i.test(url) ? url : `https://${url}`;
  }

  add(): void {
    this.run(this.platforms.add(toPayload(this.fresh)), () => {
      this.fresh = { ...EMPTY_DRAFT };
    });
  }

  edit(platform: JobPlatformResponse): void {
    this.edited = {
      name: platform.name,
      state: platform.state,
      profile_url: platform.profile_url ?? '',
      profile_updated_on: platform.profile_updated_on ?? '',
      notes: platform.notes ?? '',
    };
    this.editing.set(platform.id);
  }

  save(platform: JobPlatformResponse): void {
    this.run(this.platforms.update(platform.id, toPayload(this.edited)), () =>
      this.editing.set(null),
    );
  }

  markUpdated(platform: JobPlatformResponse): void {
    this.run(this.platforms.update(platform.id, { profile_updated_on: isoToday() }));
  }

  remove(platform: JobPlatformResponse): void {
    this.run(this.platforms.remove(platform.id));
  }

  private run(request: Observable<unknown>, onDone?: () => void): void {
    this.busy.set(true);
    this.error.set(null);
    request.subscribe({
      next: () => {
        this.busy.set(false);
        onDone?.();
      },
      error: (error: unknown) => {
        this.busy.set(false);
        this.error.set(detailOf(error, 'That could not be saved.'));
      },
    });
  }
}

/** Blank fields become null, so clearing a field clears it. */
function toPayload(draft: Draft) {
  return {
    name: draft.name.trim(),
    state: draft.state,
    profile_url: draft.profile_url.trim() || null,
    profile_updated_on: draft.profile_updated_on || null,
    notes: draft.notes.trim() || null,
  };
}

/** Today in the user's own time zone, as the date input and the API expect it. */
function isoToday(): string {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 10);
}
