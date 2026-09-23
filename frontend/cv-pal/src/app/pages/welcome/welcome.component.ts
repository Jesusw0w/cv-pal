import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, effect, inject, signal, viewChild } from '@angular/core';
import { Router } from '@angular/router';
import { Observable, forkJoin, of } from 'rxjs';

import { markWelcomeSeen } from '../../core/first-run';
import { AnalysisService, rejectUpload } from '../../core/services/analysis.service';
import { AuthService } from '../../core/services/auth.service';
import { CareerProfileService } from '../../core/services/career-profile.service';
import { GoalsService } from '../../core/services/goals.service';
import { CareerProfileUpdate, WorkRegime } from '../../shared/models/api.model';
import { ImportPanelComponent } from '../profile/import-panel.component';

const REGIMES: { value: WorkRegime; label: string }[] = [
  { value: 'remote', label: 'Remote' },
  { value: 'hybrid', label: 'Hybrid' },
  { value: 'on_site', label: 'On site' },
];

/** How many past titles to offer as roles to search for. Beyond this it is a CV, not a goal. */
const ROLE_SUGGESTIONS = 2;

/**
 * The first run: what this is, then the CV, then what the CV could not say, then goals.
 *
 * Every part of this already worked and nobody could find it — the upload lived on a
 * different screen from the import that reads it. Ordering them is the whole feature;
 * each step calls the existing screen's service.
 *
 * It can be left at any step, and nothing is written that the user did not press a
 * button for — the drafted summary included.
 */
@Component({
  selector: 'app-welcome',
  imports: [ImportPanelComponent],
  template: `
    <div class="wrap">
      <header class="head">
        <!-- The dots are decoration; the label is what a screen reader announces, and
             it is the only thing that says how much of this is left. -->
        <div class="progress">
          <div class="dots" aria-hidden="true">
            @for (index of steps; track index) {
              <span
                class="dot"
                [class.on]="index <= step()"
                [class.skipped]="skipped(index)"
              ></span>
            }
          </div>
          <span class="count" role="status">Step {{ step() + 1 }} of {{ steps.length }}</span>
        </div>
        <button type="button" class="skip" (click)="leave()">Skip setup</button>
      </header>

      @switch (step()) {
        @case (0) {
          <section class="card step">
            <h2>Welcome to CV Pal</h2>
            <p>
              CV Pal keeps one structured record of your career and writes every CV from it. That is
              what lets it tailor a CV to a posting without inventing anything — if a fact is not in
              your record, it will not appear in a document, it will be reported to you as a gap.
            </p>
            <p class="muted">
              Setting that record up takes about five minutes, and the fastest way is to let it read
              a CV you already have. Nothing is saved until you say so, and you can change any of it
              later.
            </p>
            <div class="actions">
              <button type="button" class="primary" (click)="step.set(1)">Get started</button>
            </div>
          </section>
        }

        @case (1) {
          <section class="card step">
            <h2>Start with a CV</h2>
            <p>
              Upload the CV you use now. It is read on your machine — parsing, the ATS check and
              keyword coverage all run without a language model.
            </p>

            <label
              class="drop"
              [class.over]="dragging()"
              (dragover)="onDragOver($event)"
              (dragleave)="dragging.set(false)"
              (drop)="onDrop($event)"
            >
              <input type="file" accept=".pdf,.docx" (change)="pick($event)" />
              <span>{{ fileName() ?? 'Drop a PDF or DOCX here, or choose one…' }}</span>
            </label>

            @if (error(); as message) {
              <p class="error" role="alert">{{ message }}</p>
            }

            <div class="actions">
              <button type="button" class="ghost" (click)="step.set(0)">Back</button>
              <button type="button" class="link" (click)="skipUpload()">
                I do not have one to hand
              </button>
              <button
                type="button"
                class="primary"
                [disabled]="file() === null || busy()"
                (click)="uploadAndRead()"
              >
                {{ busy() ? 'Uploading…' : 'Upload and read it' }}
              </button>
            </div>
          </section>
        }

        @case (2) {
          <section class="step">
            <h2>Keep what it read correctly</h2>
            <p class="lead">
              Extraction is a guess at a layout nobody controls, so nothing here is saved until you
              add it. Add the rows that are right and ignore the rest — you can add anything it
              missed by hand afterwards.
            </p>

            <app-import-panel [cvId]="uploadedId()" (added)="profile.reload()" />

            <div class="actions">
              <button type="button" class="ghost" (click)="step.set(1)">Back</button>
              <!-- Held while the CV is read: moving on early carries an empty read into
                   the next step, and the user never sees what was found. -->
              <button
                type="button"
                class="primary"
                [disabled]="importPanel()?.reading()"
                (click)="toAboutYou()"
              >
                {{ importPanel()?.reading() ? 'Reading…' : 'Next' }}
              </button>
            </div>
          </section>
        }

        @case (3) {
          <section class="card step">
            <h2>The parts a CV does not say plainly</h2>
            <p class="muted">
              A headline and a summary are the top of every CV this generates. Both are rewritten
              per posting later — these are the starting point.
            </p>

            <label class="field">
              <span>Your name</span>
              <input
                type="text"
                autocomplete="name"
                [value]="fullName()"
                (input)="fullName.set(value($event))"
                placeholder="Ana Silva"
              />
              <small class="help">
                The heading of every CV and cover letter this generates. Without it they are titled
                "Curriculum Vitae".
              </small>
            </label>

            <label class="field">
              <span>Headline</span>
              <input
                type="text"
                [value]="headline()"
                (input)="headline.set(value($event))"
                placeholder="Senior Backend Engineer"
              />
            </label>

            <label class="field">
              <span>Where you are based</span>
              <input
                type="text"
                [value]="location()"
                (input)="location.set(value($event))"
                placeholder="Lisbon, Portugal"
              />
            </label>

            <label class="field">
              <span>
                Summary
                <button
                  type="button"
                  class="link inline"
                  [disabled]="drafting()"
                  (click)="draftSummary()"
                >
                  {{ drafting() ? 'Writing…' : 'Draft one from my profile' }}
                </button>
              </span>
              <textarea
                rows="5"
                [value]="summary()"
                (input)="summary.set(value($event))"
                placeholder="Two or three sentences on what you do and what you are good at."
              ></textarea>
            </label>

            @if (drafted()) {
              <p class="note">
                Drafted from the roles and skills in your profile, and not saved yet. Read it before
                you keep it — it is your name on it.
              </p>
            }

            @if (error(); as message) {
              <p class="error" role="alert">{{ message }}</p>
            }

            <div class="actions">
              <button type="button" class="ghost" (click)="step.set(2)">Back</button>
              <button type="button" class="link" (click)="skipAboutYou()">
                Fill this in later
              </button>
              <button type="button" class="primary" [disabled]="busy()" (click)="saveAboutYou()">
                {{ busy() ? 'Saving…' : 'Save and continue' }}
              </button>
            </div>
          </section>
        }

        @case (4) {
          <section class="card step">
            <h2>What are you looking for?</h2>
            <p class="muted">
              This is what a posting is scored against. Without it every job scores the same, which
              is the same as not scoring them at all.
            </p>

            <label class="field">
              <span>Roles you want, one per line</span>
              <textarea
                rows="3"
                [value]="rolesText()"
                (input)="rolesText.set(value($event))"
                placeholder="Backend Engineer&#10;Platform Engineer"
              ></textarea>
            </label>

            <fieldset class="field">
              <legend>How you want to work</legend>
              <div class="chips">
                @for (regime of regimes; track regime.value) {
                  <button
                    type="button"
                    class="chip"
                    [class.on]="regimes_.has(regime.value)"
                    (click)="toggleRegime(regime.value)"
                  >
                    {{ regime.label }}
                  </button>
                }
              </div>
            </fieldset>

            <div class="row">
              <label class="field grow">
                <span>Lowest salary you would accept</span>
                <input
                  type="number"
                  min="0"
                  [value]="minSalary()"
                  (input)="minSalary.set(value($event))"
                  placeholder="55000"
                />
              </label>
              <label class="field currency">
                <span>Currency</span>
                <input
                  type="text"
                  maxlength="3"
                  [value]="currency()"
                  (input)="currency.set(value($event).toUpperCase())"
                  placeholder="EUR"
                />
              </label>
            </div>

            @if (error(); as message) {
              <p class="error" role="alert">{{ message }}</p>
            }

            <div class="actions">
              <button type="button" class="ghost" (click)="step.set(3)">Back</button>
              <button type="button" class="link" (click)="leave()">Fill this in later</button>
              <button type="button" class="primary" [disabled]="busy()" (click)="finish()">
                {{ busy() ? 'Saving…' : 'Finish' }}
              </button>
            </div>
          </section>
        }
      }
    </div>
  `,
  styles: [
    `
      .wrap {
        max-width: 720px;
        margin: 0 auto;
        padding: 12px 0 40px;
      }
      .head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 4px 2px 18px;
      }
      .progress {
        display: flex;
        align-items: center;
        gap: 10px;
      }
      .dots {
        display: flex;
        gap: 6px;
      }
      .dot {
        width: 26px;
        height: 4px;
        border-radius: 2px;
        background: var(--border-light);
      }
      .dot.on {
        background: var(--accent);
      }
      .dot.skipped {
        background: var(--border-light);
        outline: 1px solid var(--accent);
      }
      .count {
        font-size: 12px;
        color: var(--text-tertiary);
      }
      .skip {
        font-size: 12px;
        color: var(--text-tertiary);
      }
      .skip:hover {
        color: var(--text-primary);
      }

      .step {
        padding: 22px;
      }
      .step h2 {
        font-size: 20px;
        font-weight: 700;
        letter-spacing: -0.3px;
        margin: 0 0 10px;
      }
      .step p {
        font-size: 14px;
        line-height: 1.6;
        margin: 0 0 12px;
      }
      .muted {
        color: var(--text-tertiary);
      }
      .lead {
        color: var(--text-secondary);
      }

      .drop {
        display: block;
        padding: 22px;
        margin: 6px 0 4px;
        text-align: center;
        cursor: pointer;
        border: 1px dashed var(--border-light);
        border-radius: var(--radius);
        color: var(--text-secondary);
        font-size: 13px;
      }
      .drop:hover,
      .drop.over {
        border-color: var(--accent);
        color: var(--accent);
      }
      .drop.over {
        background: var(--accent-light);
      }
      .drop input {
        display: none;
      }

      .field {
        display: block;
        margin: 14px 0;
      }
      .field > span,
      .field legend {
        display: flex;
        align-items: baseline;
        gap: 10px;
        margin-bottom: 6px;
        font-size: 12px;
        font-weight: 600;
        color: var(--text-secondary);
      }
      .field input,
      .field textarea {
        width: 100%;
        padding: 9px 11px;
        font: inherit;
        font-size: 14px;
        border: 1px solid var(--border-light);
        border-radius: var(--radius);
        background: var(--bg-primary);
        color: var(--text-primary);
      }
      .field textarea {
        resize: vertical;
      }
      .help {
        display: block;
        margin-top: 5px;
        font-size: 11px;
        color: var(--text-tertiary);
      }
      fieldset.field {
        border: 0;
        padding: 0;
        margin: 14px 0;
      }

      .row {
        display: flex;
        gap: 12px;
        align-items: flex-end;
      }
      .grow {
        flex: 1;
      }
      .currency {
        width: 110px;
      }

      .chips {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }
      .chip {
        font-size: 13px;
        padding: 7px 14px;
        border-radius: 999px;
        border: 1px solid var(--border-light);
        color: var(--text-secondary);
      }
      .chip.on {
        border-color: var(--accent);
        background: var(--accent-light);
        color: var(--accent);
      }

      .note {
        font-size: 12px;
        color: var(--text-tertiary);
        border-left: 2px solid var(--accent);
        padding-left: 10px;
      }
      .error {
        font-size: 13px;
        color: var(--danger, #dc2626);
      }

      .actions {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-top: 20px;
      }
      .actions .primary {
        margin-left: auto;
        padding: 9px 18px;
        border-radius: var(--radius);
        background: var(--accent);
        color: #fff;
        font-size: 13px;
        font-weight: 600;
      }
      .actions .primary:disabled {
        opacity: 0.5;
      }
      .ghost {
        font-size: 13px;
        color: var(--text-secondary);
        padding: 9px 4px;
      }
      .link {
        font-size: 13px;
        font-weight: 600;
        color: var(--accent);
      }
      .link.inline {
        font-size: 11px;
      }
      .link:disabled {
        opacity: 0.5;
      }
    `,
  ],
})
export class WelcomeComponent {
  private readonly analysis = inject(AnalysisService);
  private readonly auth = inject(AuthService);
  private readonly goalsService = inject(GoalsService);
  private readonly router = inject(Router);

  readonly profile = inject(CareerProfileService);

  /** Step 2's panel, read on the way out so step 3 starts from what the CV said. */
  protected readonly importPanel = viewChild(ImportPanelComponent);

  readonly steps = [0, 1, 2, 3, 4];
  readonly regimes = REGIMES;
  readonly regimes_ = new Set<WorkRegime>();

  readonly step = signal(0);
  readonly busy = signal(false);
  readonly error = signal<string | null>(null);

  readonly file = signal<File | null>(null);
  readonly dragging = signal(false);
  readonly uploadedId = signal<number | null>(null);
  readonly fileName = computed(() => this.file()?.name ?? null);

  /**
   * Steps the user chose to pass over.
   *
   * Shown differently in the progress strip: a dot for a step that was skipped is not
   * the same as one for a step that was done, and the difference is what tells someone
   * halfway through what they still owe the profile.
   */
  private readonly skippedSteps = new Set<number>();

  readonly fullName = signal('');
  readonly headline = signal('');
  readonly location = signal('');
  readonly summary = signal('');
  readonly drafting = signal(false);
  readonly drafted = signal(false);

  readonly rolesText = signal('');
  readonly minSalary = signal('');
  readonly currency = signal('EUR');

  /**
   * The wizard can be re-entered, and both of its saves overwrite: the profile PATCH
   * sends whatever the fields hold, and the goals call is a PUT that replaces the
   * record. Starting from blank fields would therefore read as "the user cleared all of
   * this" and quietly wipe a profile and a set of goals that took real work to enter.
   *
   * Seeded once each, when the resource first answers — after that the fields belong to
   * the user and a reload must not overwrite what they are typing.
   */
  private seededProfile = false;
  private seededGoals = false;

  constructor() {
    effect(() => {
      const account = this.auth.fullName();
      const profile = this.profile.profile();
      if (this.seededProfile || profile.id === 0) {
        return;
      }
      this.seededProfile = true;
      this.fullName.set(account ?? '');
      this.headline.set(profile.headline ?? '');
      this.location.set(profile.location ?? '');
      this.summary.set(profile.summary ?? '');
    });

    effect(() => {
      const goals = this.goalsService.goals();
      if (this.seededGoals || goals.id === 0) {
        return;
      }
      this.seededGoals = true;
      this.rolesText.set(goals.target_roles.join('\n'));
      for (const regime of goals.work_regimes) {
        this.regimes_.add(regime);
      }
      this.minSalary.set(goals.min_salary?.toString() ?? '');
      this.currency.set(goals.salary_currency ?? 'EUR');
    });
  }

  /** Null when blank: `Number('')` is 0, and a floor of zero filters nothing. */
  readonly salaryFloor = computed(() => {
    const entered = this.minSalary().trim();
    const amount = Number(entered);
    return entered && Number.isFinite(amount) && amount > 0 ? amount : null;
  });

  value(event: Event): string {
    return (event.target as HTMLInputElement | HTMLTextAreaElement).value;
  }

  pick(event: Event): void {
    this.choose((event.target as HTMLInputElement).files?.[0] ?? null);
  }

  onDragOver(event: DragEvent): void {
    // Without this the browser navigates to the dropped file and the wizard is gone.
    event.preventDefault();
    this.dragging.set(true);
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    this.dragging.set(false);
    this.choose(event.dataTransfer?.files?.[0] ?? null);
  }

  private choose(chosen: File | null): void {
    this.error.set(chosen ? rejectUpload(chosen) : null);
    this.file.set(this.error() ? null : chosen);
  }

  /** Whether a step was passed over rather than completed, for the progress dots. */
  skipped(index: number): boolean {
    return this.skippedSteps.has(index);
  }

  /** No CV to read, so the import step has nothing to show. */
  skipUpload(): void {
    this.skippedSteps.add(1).add(2);
    this.step.set(3);
  }

  /** Move on without writing anything: these fields are all editable on the profile. */
  skipAboutYou(): void {
    this.skippedSteps.add(3);
    this.error.set(null);
    this.toGoals();
  }

  uploadAndRead(): void {
    const chosen = this.file();
    if (!chosen) {
      return;
    }
    this.busy.set(true);
    this.error.set(null);
    this.analysis.upload(chosen).subscribe({
      next: (cv) => {
        this.busy.set(false);
        this.analysis.reload();
        this.uploadedId.set(cv.id);
        this.step.set(2);
      },
      error: (error: unknown) => {
        this.busy.set(false);
        this.error.set(detailOf(error, 'That file could not be uploaded.'));
      },
    });
  }

  /**
   * Fill the next step from what the CV said, before asking the user to type it.
   *
   * The CV's own header is the better source and is tried first; the most recent role
   * is the fallback for a layout whose header did not survive extraction. Neither is
   * saved here — step 3 shows them for editing and its own button writes them.
   */
  toAboutYou(): void {
    const found = this.importPanel()?.proposal();
    const roles = this.profile.experiences();
    if (!this.headline()) {
      this.headline.set(found?.headline ?? roles[0]?.title ?? '');
    }
    if (!this.location()) {
      this.location.set(found?.location ?? roles[0]?.location ?? '');
    }
    if (!this.summary() && found?.summary) {
      this.summary.set(found.summary);
    }
    this.error.set(null);
    this.step.set(3);
  }

  /**
   * Seed the roles being searched for from the ones already held.
   *
   * The most recent titles are what almost everyone types here, and an empty goals
   * record is why every posting scores the same.
   */
  toGoals(): void {
    if (!this.rolesText()) {
      const titles = [...new Set(this.profile.experiences().map((role) => role.title))];
      this.rolesText.set(titles.slice(0, ROLE_SUGGESTIONS).join('\n'));
    }
    this.error.set(null);
    this.step.set(4);
  }

  draftSummary(): void {
    this.drafting.set(true);
    this.error.set(null);
    this.profile.generateSummary().subscribe({
      next: (result) => {
        this.drafting.set(false);
        this.drafted.set(true);
        this.summary.set(result.summary);
      },
      error: (error: unknown) => {
        this.drafting.set(false);
        this.error.set(
          detailOf(
            error,
            'No language model answered. Check Settings, or write the summary yourself.',
          ),
        );
      },
    });
  }

  saveAboutYou(): void {
    this.busy.set(true);
    this.error.set(null);

    // A blank field means "not now", never "clear it". Sending null would be a write,
    // and the one screen that should be able to erase a headline is the profile.
    const changes: CareerProfileUpdate = {};
    const headline = this.headline().trim();
    const location = this.location().trim();
    const summary = this.summary().trim();
    if (headline) {
      changes.headline = headline;
    }
    if (location) {
      changes.location = location;
    }
    if (summary) {
      changes.summary = summary;
    }

    // The name lives on the account rather than the profile, so it is a second call —
    // skipped entirely when it has not changed.
    const name = this.fullName().trim();
    const renaming: Observable<unknown> =
      name && name !== (this.auth.fullName() ?? '') ? this.auth.updateName(name) : of(null);

    forkJoin([this.profile.updateProfile(changes), renaming]).subscribe({
      next: () => {
        this.busy.set(false);
        this.profile.reload();
        this.toGoals();
      },
      error: (error: unknown) => {
        this.busy.set(false);
        this.error.set(detailOf(error, 'That could not be saved.'));
      },
    });
  }

  toggleRegime(regime: WorkRegime): void {
    if (this.regimes_.has(regime)) {
      this.regimes_.delete(regime);
    } else {
      this.regimes_.add(regime);
    }
  }

  finish(): void {
    const floor = this.salaryFloor();
    const regimes = [...this.regimes_];
    // A PUT replaces the record, and this wizard shows three of its seven fields. The
    // rest are carried through from what is stored so re-running setup cannot silently
    // undo an afternoon spent on the goals screen.
    const stored = this.goalsService.goals();
    this.busy.set(true);
    this.error.set(null);
    this.goalsService
      .save({
        target_roles: this.rolesText()
          .split('\n')
          .map((role) => role.trim())
          .filter(Boolean),
        work_regimes: regimes,
        // A non-negotiable with nothing behind it is rejected by the API, so each one
        // survives only while the preference it depends on still has a value.
        regime_non_negotiable: regimes.length > 0 && stored.regime_non_negotiable,
        work_locations: stored.work_locations,
        location_non_negotiable: stored.location_non_negotiable,
        min_salary: floor,
        salary_currency: floor === null ? null : this.currency().trim() || 'EUR',
        salary_non_negotiable: floor !== null && stored.salary_non_negotiable,
      })
      .subscribe({
        next: () => {
          this.busy.set(false);
          this.goalsService.reload();
          this.leave();
        },
        error: (error: unknown) => {
          this.busy.set(false);
          this.error.set(detailOf(error, 'Those goals could not be saved.'));
        },
      });
  }

  /** Mark the first run done and go to the dashboard, from any step. */
  leave(): void {
    const userId = this.auth.userId();
    if (userId !== null) {
      markWelcomeSeen(userId);
    }
    void this.router.navigate(['/dashboard']);
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
