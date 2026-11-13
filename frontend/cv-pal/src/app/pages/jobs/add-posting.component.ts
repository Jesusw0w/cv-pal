import { DatePipe } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { Observable } from 'rxjs';

import { GoalsService } from '../../core/services/goals.service';
import { JobService } from '../../core/services/job.service';
import { Action } from '../../shared/action';
import { ConfirmButtonComponent } from '../../shared/confirm-button.component';
import { SyncResultResponse } from '../../shared/models/api.model';

/** The sources that can be watched. `manual` is a paste, so there is nothing to sync. */
type WatchableSource = 'remotive' | 'greenhouse' | 'lever';

/**
 * Remotive's categories. A select rather than a text field because an unknown slug is
 * indistinguishable from a category that is quiet today: it would sync, save nothing,
 * and look like a bug.
 */
const REMOTIVE_CATEGORIES = [
  { slug: 'software-development', name: 'Software Development' },
  { slug: 'devops', name: 'DevOps' },
  { slug: 'information-technology', name: 'Information Technology' },
  { slug: 'data', name: 'Data and Analytics' },
  { slug: 'artificial-intelligence', name: 'Artificial Intelligence' },
  { slug: 'qa', name: 'Quality Assurance' },
  { slug: 'product', name: 'Product Management' },
  { slug: 'project-management', name: 'Project Management' },
  { slug: 'design', name: 'Design' },
  { slug: 'engineering', name: 'Engineering' },
] as const;

/** What each source covers, said before the user commits to watching it. */
const SOURCE_HINTS: Record<WatchableSource, string> = {
  remotive:
    'Remote roles from every company on Remotive. The feed rotates daily, so a quiet category is normal.',
  greenhouse:
    "One company's open roles. The slug is the end of its board URL: boards.greenhouse.io/acme. Contract type is not published.",
  lever:
    "One company's open roles. The slug is the end of its board URL: jobs.lever.co/acme. Contract type is not published.",
};

type Mode = 'link' | 'paste' | 'watch';

/** Every way a posting gets in: a recognised link, a paste, or a board watched for new ones. */
@Component({
  selector: 'app-add-posting',
  imports: [DatePipe, FormsModule, RouterLink, ConfirmButtonComponent],
  template: `
    <section class="card">
      <div class="card-header">
        <div class="tabs" role="tablist">
          @for (tab of modes; track tab.mode) {
            <button
              type="button"
              role="tab"
              [class.active]="mode() === tab.mode"
              [attr.aria-selected]="mode() === tab.mode"
              (click)="mode.set(tab.mode)"
            >
              {{ tab.label }}
            </button>
          }
        </div>
      </div>

      @switch (mode()) {
        @case ('link') {
          <form class="body form" (ngSubmit)="importUrl()">
            <input
              [(ngModel)]="url"
              name="url"
              type="url"
              placeholder="A Remotive, Greenhouse or Lever link"
              aria-label="Job posting link"
            />
            <p class="hint">
              Those three are read through their own APIs. CV Pal does not fetch arbitrary pages —
              for LinkedIn or a careers page, paste the posting instead.
            </p>
            <button type="submit" class="primary" [disabled]="action.busy() || !url().trim()">
              {{ action.busy() ? 'Reading…' : 'Add from link' }}
            </button>
          </form>
        }
        @case ('paste') {
          <form class="body form" (ngSubmit)="paste()">
            <div class="fields">
              <input
                [(ngModel)]="title"
                name="title"
                placeholder="Job title"
                aria-label="Job title"
              />
              <input
                [(ngModel)]="company"
                name="company"
                placeholder="Company"
                aria-label="Company"
              />
              <input
                [(ngModel)]="location"
                name="location"
                placeholder="Location"
                aria-label="Location"
              />
            </div>
            <textarea
              rows="7"
              [(ngModel)]="description"
              name="description"
              placeholder="Paste the full posting, including the requirements list."
              aria-label="Job description"
            ></textarea>
            <button type="submit" class="primary" [disabled]="action.busy() || !canPaste()">
              {{ action.busy() ? 'Saving…' : 'Save posting' }}
            </button>
          </form>
        }
        @case ('watch') {
          <form class="body form" (ngSubmit)="watch()">
            <div class="fields">
              <!-- Changing source clears the identifier: a company slug is meaningless
                   as a Remotive category. -->
              <select
                [ngModel]="source()"
                (ngModelChange)="source.set($event); identifier.set('')"
                name="source"
                aria-label="Source"
              >
                <option value="remotive">Remotive — remote roles, any company</option>
                <option value="greenhouse">Greenhouse — one company's board</option>
                <option value="lever">Lever — one company's board</option>
              </select>
              @if (source() === 'remotive') {
                <select [(ngModel)]="identifier" name="identifier" aria-label="Category">
                  <option value="" disabled>Choose a category…</option>
                  @for (category of categories; track category.slug) {
                    <option [value]="category.slug">{{ category.name }}</option>
                  }
                </select>
              } @else {
                <input
                  [(ngModel)]="identifier"
                  name="identifier"
                  placeholder="company slug, e.g. acme"
                  aria-label="Company slug"
                />
              }
            </div>
            <p class="hint">{{ hint() }}</p>
            <!-- Opt-in: a sync that silently drops postings is worse than a noisy one. -->
            <label class="check">
              <input type="checkbox" [(ngModel)]="onlyTargetRoles" name="filter" />
              <span>
                Only save postings matching my
                <a routerLink="/profile/goals">target roles</a>
                @if (goals.goals().target_roles.length === 0) {
                  (none set yet, so everything is saved)
                }
              </span>
            </label>
            <button
              type="submit"
              class="primary"
              [disabled]="action.busy() || !identifier().trim()"
            >
              Watch
            </button>
          </form>

          @if (jobs.sources().length > 0) {
            <ul class="rows">
              @for (source of jobs.sources(); track source.id) {
                <li class="row">
                  <div class="row-main">
                    <span class="row-title">{{ source.label }}</span>
                    <span class="row-meta">
                      {{ source.source }}
                      @if (source.filter_by_goals) {
                        &middot; target roles only
                      }
                      @if (source.last_error) {
                        &middot; last sync failed
                      } @else if (source.last_synced_at) {
                        &middot; synced {{ source.last_synced_at | date: 'd MMM HH:mm' }}
                      } @else {
                        &middot; never synced
                      }
                    </span>
                  </div>
                  <button
                    type="button"
                    class="link"
                    [disabled]="action.busy()"
                    (click)="sync(source.id)"
                  >
                    Sync
                  </button>
                  <app-confirm-button
                    [label]="'Stop watching ' + source.label"
                    (confirmed)="unwatch(source.id)"
                    >Remove</app-confirm-button
                  >
                </li>
              }
            </ul>
            <div class="body sync-all">
              <button type="button" class="link" [disabled]="action.busy()" (click)="syncAll()">
                {{ action.busy() ? 'Syncing…' : 'Sync all' }}
              </button>
              @if (syncNote(); as note) {
                <span class="muted" role="status">{{ note }}</span>
              }
            </div>
          }
        }
      }

      @if (action.error(); as message) {
        <p class="error body" role="alert">{{ message }}</p>
      }
    </section>
  `,
  styles: `
    .form {
      display: flex;
      flex-direction: column;
      align-items: flex-start;
      gap: 10px;
    }
    .form > input {
      width: 100%;
    }
    .fields {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      width: 100%;
    }
    .fields > * {
      flex: 1 1 160px;
    }
    .check {
      display: flex;
      align-items: baseline;
      gap: 8px;
      font-size: 13px;
      color: var(--text-secondary);
    }
    .sync-all {
      display: flex;
      align-items: baseline;
      gap: 12px;
      padding-top: 0;
    }
  `,
})
export class AddPostingComponent {
  protected readonly jobs = inject(JobService);
  /** Read only to say whether the filter would currently have anything to match on. */
  protected readonly goals = inject(GoalsService);
  protected readonly action = new Action();

  protected readonly modes: { mode: Mode; label: string }[] = [
    { mode: 'link', label: 'From a link' },
    { mode: 'paste', label: 'Paste' },
    { mode: 'watch', label: 'Watch a board' },
  ];
  protected readonly categories = REMOTIVE_CATEGORIES;

  protected readonly mode = signal<Mode>('link');

  protected readonly url = signal('');

  protected readonly title = signal('');
  protected readonly company = signal('');
  protected readonly location = signal('');
  protected readonly description = signal('');
  /** Mirrors the API's own minimum, so the button explains itself instead of 422-ing. */
  protected readonly canPaste = computed(
    () => this.title().trim().length > 0 && this.description().trim().length >= 50,
  );

  /** Remotive first: it is the only source that answers "what is open at all". */
  protected readonly source = signal<WatchableSource>('remotive');
  protected readonly identifier = signal('');
  protected readonly onlyTargetRoles = signal(false);
  protected readonly hint = computed(() => SOURCE_HINTS[this.source()]);
  protected readonly syncNote = signal<string | null>(null);

  protected importUrl(): void {
    this.run(this.jobs.importUrl(this.url().trim()), () => this.url.set(''));
  }

  protected paste(): void {
    this.run(
      this.jobs.paste({
        title: this.title().trim(),
        company: this.company().trim() || null,
        location: this.location().trim() || null,
        description: this.description().trim(),
      }),
      () => [this.title, this.company, this.location, this.description].forEach((f) => f.set('')),
    );
  }

  protected watch(): void {
    this.run(
      this.jobs.watchBoard(this.source(), this.identifier().trim(), this.onlyTargetRoles()),
      () => this.identifier.set(''),
    );
  }

  protected unwatch(connectionId: number): void {
    this.run(this.jobs.unwatch(connectionId));
  }

  protected sync(connectionId: number): void {
    this.run(this.jobs.sync(connectionId), (result) => this.syncNote.set(summarise([result])));
  }

  protected syncAll(): void {
    this.run(this.jobs.syncAll(), (results) => this.syncNote.set(summarise(results)));
  }

  private run<T>(request: Observable<T>, onDone?: (value: T) => void): void {
    this.action.run(request, 'That did not work.', (value) => {
      onDone?.(value);
      this.jobs.reload();
    });
  }
}

/**
 * "Found 12, added 0" is the normal outcome of a repeat sync, and saying so stops it
 * reading as a failure. Failures are counted too: a sweep where nothing could be read
 * would otherwise also say "added 0".
 */
function summarise(results: SyncResultResponse[]): string {
  const sum = (pick: (result: SyncResultResponse) => number) =>
    results.reduce((total, result) => total + pick(result), 0);
  const failed = results.filter((result) => result.error !== null);
  if (results.length === 1 && failed.length === 1) {
    return failed[0].error ?? '';
  }
  const skipped = sum((result) => result.skipped);
  return (
    `Found ${sum((result) => result.found)}, added ${sum((result) => result.added)} new` +
    (skipped > 0 ? `, skipped ${skipped} outside your target roles` : '') +
    (failed.length > 0 ? ` — ${failed.length} source(s) could not be read.` : '.')
  );
}
