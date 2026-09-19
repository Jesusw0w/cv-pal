import { HttpErrorResponse } from '@angular/common/http';
import { Component, computed, effect, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { GoalsService } from '../../core/services/goals.service';
import { WorkRegime } from '../../shared/models/api.model';

const REGIMES: { value: WorkRegime; label: string }[] = [
  { value: 'remote', label: 'Remote' },
  { value: 'hybrid', label: 'Hybrid' },
  { value: 'on_site', label: 'On site' },
];

/**
 * Wordings remote feeds actually use for eligibility, offered as one-click additions.
 *
 * Not a taxonomy and not a containment map — picking `Europe` here asserts nothing
 * about where the user lives, it only saves them typing a term they might not have
 * thought a posting would use. The matching still compares strings and infers nothing.
 */
const COMMON_PLACES = [
  'Europe',
  'EU',
  'EMEA',
  'UK',
  'Americas',
  'North America',
  'LATAM',
  'APAC',
  'Asia',
  'Africa',
  'Oceania',
  'Middle East',
] as const;

/** Non-empty trimmed lines, in order. */
function linesOf(text: string): string[] {
  return text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);
}

/**
 * What the user is looking for — the input side of matching.
 *
 * The screen's whole job is to keep one distinction visible: a **non-negotiable filters**
 * a posting out entirely, a **preference scores** it. Collapsing the two is how a search
 * ends up returning nothing, or how a number ends up meaning nothing, so each one is a
 * separate control with the consequence spelled out next to it.
 */
@Component({
  selector: 'app-goals',
  imports: [FormsModule],
  template: `
    <div class="page">
      <header class="intro">
        <h1>What you are looking for</h1>
        <p>
          Job matches are scored against this, not against whatever a job board happened to return.
          Leave anything blank that you genuinely do not mind about.
        </p>
      </header>

      @if (goals.error()) {
        <p class="card notice" role="alert">
          Could not load your goals.
          <button type="button" class="link" (click)="goals.reload()">Try again</button>
        </p>
      }

      <form class="card panel" (ngSubmit)="save()">
        <section class="field">
          <h3>Target roles</h3>
          <p class="hint">
            One per line. A posting's title is compared against these, so "Backend Engineer" also
            matches "Senior Backend Engineer".
          </p>
          <textarea
            rows="4"
            [(ngModel)]="rolesText"
            name="roles"
            aria-label="Target roles, one per line"
            placeholder="Backend Engineer&#10;Platform Engineer"
          ></textarea>
        </section>

        <section class="field">
          <!-- "How" not "Where": the arrangement and the geography are independent
               questions, and the section below asks the other one. -->
          <h3>How you will work</h3>
          <p class="hint">Choose everything you would accept.</p>
          <div class="choices">
            @for (regime of regimes; track regime.value) {
              <label class="choice">
                <input
                  type="checkbox"
                  [checked]="chosenRegimes().includes(regime.value)"
                  (change)="toggleRegime(regime.value)"
                />
                {{ regime.label }}
              </label>
            }
          </div>
          <label class="strict">
            <input type="checkbox" [(ngModel)]="regimeStrict" name="regimeStrict" />
            <span>
              <strong>Non-negotiable.</strong>
              Postings that state a different arrangement are hidden, not just ranked lower. A
              posting that does not say is still shown.
            </span>
          </label>
          @if (regimeStrict && chosenRegimes().length === 0) {
            <p class="warn">Choose at least one arrangement, or nothing can ever match.</p>
          }
        </section>

        <section class="field">
          <h3>Where you can work</h3>
          <p class="hint">
            One per line. Remote does not mean unrestricted &mdash; most remote postings name a
            country or region you have to be in, and without this they are ranked as if you could
            take them.
          </p>
          <!-- Explicit write side: the suggestion chips and the warning read a signal,
               and a plain [(ngModel)] property would not notify them as you type. -->
          <textarea
            rows="4"
            [ngModel]="locationsText"
            (ngModelChange)="setLocations($event)"
            name="locations"
            aria-label="Places you can work from, one per line"
            placeholder="Portugal&#10;Europe&#10;EU&#10;EMEA"
          ></textarea>
          <!-- The app deliberately does not know that Portugal is in Europe. It has no
               authoritative containment data, and guessing would hide jobs silently —
               the same reasoning that limits the skills alias map. So list every term a
               posting might use for somewhere you can work. -->
          <p class="hint">
            List every wording that applies to you, including the wider regions: a posting saying
            <em>Europe</em> is only matched if you listed Europe. Postings open
            <em>worldwide</em> always match.
          </p>
          @if (suggestions().length > 0) {
            <p class="suggest">
              Add:
              @for (place of suggestions(); track place) {
                <button type="button" class="chip" (click)="addLocation(place)">
                  {{ place }}
                </button>
              }
            </p>
          }
          <label class="strict">
            <input type="checkbox" [(ngModel)]="locationStrict" name="locationStrict" />
            <span>
              <strong>Non-negotiable.</strong>
              Postings that name somewhere else are hidden, not just ranked lower. A posting that
              does not say where is still shown.
            </span>
          </label>
          @if (locationStrict && chosenLocations().length === 0) {
            <p class="warn">Add at least one place, or nothing can ever match.</p>
          }
        </section>

        <section class="field">
          <h3>Salary floor</h3>
          <p class="hint">Optional. A number without a currency cannot be compared.</p>
          <div class="salary">
            <input
              type="number"
              min="0"
              [(ngModel)]="minSalary"
              name="minSalary"
              placeholder="65000"
              aria-label="Minimum salary"
            />
            <input
              [(ngModel)]="currency"
              name="currency"
              maxlength="3"
              placeholder="EUR"
              aria-label="Currency"
              class="currency"
            />
          </div>
          <label class="strict">
            <input type="checkbox" [(ngModel)]="salaryStrict" name="salaryStrict" />
            <span><strong>Non-negotiable.</strong> Anything below is hidden.</span>
          </label>
        </section>

        @if (error(); as message) {
          <p class="error" role="alert">{{ message }}</p>
        }
        @if (saved()) {
          <p class="ok" role="status">Saved. New matches will be scored against this.</p>
        }

        <button type="submit" class="primary" [disabled]="saving()">
          {{ saving() ? 'Saving…' : 'Save' }}
        </button>
      </form>

      <p class="footnote">
        Deferred on purpose until something reads them: direction (step up, sideways, pivot),
        commute limits, contract types, company size, and the parts of a job you want more and less
        of.
      </p>
    </div>
  `,
  styles: [
    `
      .page {
        padding: 28px;
        display: flex;
        flex-direction: column;
        gap: 20px;
        max-width: 720px;
      }
      .intro h1 {
        font-size: 22px;
        margin: 0 0 6px;
      }
      .intro p {
        margin: 0;
        font-size: 14px;
        color: var(--text-secondary);
        max-width: 70ch;
      }

      .panel {
        display: flex;
        flex-direction: column;
        gap: 22px;
        padding: 22px;
      }
      .field {
        display: flex;
        flex-direction: column;
        gap: 8px;
      }
      .field h3 {
        font-size: 14px;
        margin: 0;
      }
      .hint {
        margin: 0;
        font-size: 12px;
        color: var(--text-tertiary);
        max-width: 65ch;
      }

      textarea,
      input {
        padding: 9px 11px;
        border: 1px solid var(--border-light);
        border-radius: var(--radius);
        background: var(--bg-primary);
        color: var(--text-primary);
        font-size: 13px;
        font-family: inherit;
      }
      textarea {
        resize: vertical;
      }

      .choices {
        display: flex;
        flex-wrap: wrap;
        gap: 14px;
      }
      .choice {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 13px;
      }

      .strict {
        display: flex;
        gap: 8px;
        align-items: flex-start;
        font-size: 12px;
        color: var(--text-tertiary);
      }
      .strict input {
        margin-top: 2px;
      }
      .strict strong {
        color: var(--text-secondary);
      }

      .salary {
        display: flex;
        gap: 8px;
      }
      .salary input {
        width: 140px;
      }
      .currency {
        width: 70px;
        text-transform: uppercase;
      }

      .warn {
        margin: 0;
        font-size: 12px;
        color: #d97706;
      }
      .error {
        margin: 0;
        font-size: 13px;
        color: var(--danger, #dc2626);
      }
      .ok {
        margin: 0;
        font-size: 13px;
        color: #16a34a;
      }
      .link {
        color: var(--accent);
        font-weight: 600;
      }
      .notice {
        margin: 0;
        padding: 14px 18px;
        font-size: 13px;
      }

      .primary {
        align-self: flex-start;
        padding: 9px 18px;
        border-radius: var(--radius);
        background: var(--accent);
        color: #fff;
        font-size: 14px;
        font-weight: 600;
      }
      .primary:disabled {
        opacity: 0.5;
      }

      .footnote {
        margin: 0;
        font-size: 12px;
        color: var(--text-tertiary);
        max-width: 70ch;
      }

      .suggest {
        margin: 0;
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 6px;
        font-size: 12px;
        color: var(--text-tertiary);
      }
      .chip {
        font-size: 12px;
        padding: 2px 9px;
        border-radius: 999px;
        border: 1px solid var(--border-light);
        color: var(--text-secondary);
      }
      .chip:hover {
        border-color: var(--accent);
        color: var(--accent);
      }

      @media (max-width: 768px) {
        .page {
          padding: 16px;
        }
      }
    `,
  ],
})
export class GoalsComponent {
  readonly goals = inject(GoalsService);
  readonly regimes = REGIMES;

  readonly chosenRegimes = signal<WorkRegime[]>([]);
  readonly saving = signal(false);
  readonly saved = signal(false);
  readonly error = signal<string | null>(null);

  rolesText = '';
  regimeStrict = false;
  locationsText = '';
  locationStrict = false;
  minSalary: number | null = null;
  currency = '';
  salaryStrict = false;

  /** The places currently typed, so the warning and the suggestions agree with the box. */
  readonly chosenLocations = signal<string[]>([]);

  /**
   * Common wordings the user has not listed yet.
   *
   * A prompt, not an inference: the app still does not claim Portugal is in Europe, it
   * only offers the terms feeds actually use so the user does not have to remember
   * that "EMEA" is a thing postings say.
   */
  readonly suggestions = computed(() => {
    const listed = new Set(this.chosenLocations().map((p) => p.toLowerCase()));
    return COMMON_PLACES.filter((place) => !listed.has(place.toLowerCase()));
  });

  constructor() {
    // Fill the form once the record arrives, without clobbering edits in progress.
    effect(() => {
      const loaded = this.goals.goals();
      if (loaded.id !== 0 && !this.saving() && !this.rolesText) {
        this.rolesText = loaded.target_roles.join('\n');
        this.chosenRegimes.set([...loaded.work_regimes]);
        this.regimeStrict = loaded.regime_non_negotiable;
        this.locationsText = loaded.work_locations.join('\n');
        this.locationStrict = loaded.location_non_negotiable;
        this.minSalary = loaded.min_salary;
        this.currency = loaded.salary_currency ?? '';
        this.salaryStrict = loaded.salary_non_negotiable;
        this.chosenLocations.set(linesOf(this.locationsText));
      }
    });
  }

  setLocations(text: string): void {
    this.locationsText = text;
    this.chosenLocations.set(linesOf(text));
  }

  addLocation(place: string): void {
    this.setLocations([...linesOf(this.locationsText), place].join('\n'));
  }

  toggleRegime(regime: WorkRegime): void {
    // Order is the preference, so a re-added choice goes to the end rather than back to
    // wherever it was.
    this.chosenRegimes.update((chosen) =>
      chosen.includes(regime) ? chosen.filter((r) => r !== regime) : [...chosen, regime],
    );
  }

  save(): void {
    this.saving.set(true);
    this.error.set(null);
    this.saved.set(false);

    this.goals
      .save({
        target_roles: this.rolesText
          .split('\n')
          .map((line) => line.trim())
          .filter(Boolean),
        work_regimes: this.chosenRegimes(),
        regime_non_negotiable: this.regimeStrict,
        work_locations: linesOf(this.locationsText),
        location_non_negotiable: this.locationStrict,
        min_salary: this.minSalary === null || Number.isNaN(this.minSalary) ? null : this.minSalary,
        salary_currency: this.currency.trim().toUpperCase() || null,
        salary_non_negotiable: this.salaryStrict,
      })
      .subscribe({
        next: () => {
          this.saving.set(false);
          this.saved.set(true);
          this.goals.reload();
        },
        error: (error: unknown) => {
          this.saving.set(false);
          this.error.set(messageFor(error));
        },
      });
  }
}

/**
 * The API's own message.
 *
 * These validations are the useful ones — "choose an arrangement before making it a
 * non-negotiable" is guidance, not a failure — so showing the server's wording matters
 * more here than on most screens.
 */
function messageFor(error: unknown): string {
  if (error instanceof HttpErrorResponse) {
    const detail = (error.error as { detail?: unknown } | null)?.detail;
    if (typeof detail === 'string') {
      return detail;
    }
    if (Array.isArray(detail)) {
      const first = (detail[0] as { msg?: unknown } | undefined)?.msg;
      if (typeof first === 'string') {
        return first.replace(/^Value error, /, '');
      }
    }
  }
  return 'Could not save your goals.';
}
