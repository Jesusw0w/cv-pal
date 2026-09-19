import { HttpErrorResponse } from '@angular/common/http';
import { Component, effect, inject, input, output, signal } from '@angular/core';
import { Observable, forkJoin } from 'rxjs';

import { AnalysisService } from '../../core/services/analysis.service';
import { CareerProfileService } from '../../core/services/career-profile.service';
import { CvExtractionResponse, ExtractedEntryResponse } from '../../shared/models/api.model';

/** A value read from the CV that the profile does not have yet. */
interface ProposedField {
  label: string;
  field: 'linkedin_url' | 'website_url' | 'headline' | 'summary' | 'location' | 'phone';
  value: string;
}

/**
 * Review what a CV extraction proposed, and keep the parts that are right.
 *
 * The endpoint stores nothing: every record reaches the profile only by the user
 * pressing Add, which is the whole reason extraction is allowed to guess. Added rows
 * disappear, so what is left is what is outstanding.
 */
@Component({
  selector: 'app-import-panel',
  template: `
    <section class="card">
      <div class="card-header">
        <h3>Import from a CV</h3>
        <span class="card-note">Reads a CV you uploaded. Nothing is saved until you add it.</span>
      </div>

      @if (cvId() === null) {
        <div class="picker">
          <select [value]="selectedId() ?? ''" (change)="onPick($event)" aria-label="CV to read">
            <option value="" disabled>Choose a CV…</option>
            @for (cv of analysis.documents(); track cv.id) {
              <option [value]="cv.id">{{ cv.filename }}</option>
            }
          </select>
          <button
            type="button"
            class="primary"
            [disabled]="selectedId() === null || reading()"
            (click)="read()"
          >
            {{ reading() ? 'Reading…' : 'Read it' }}
          </button>
          @if (analysis.documents().length === 0 && !analysis.isLoading()) {
            <span class="muted">Upload one on the Documents screen first.</span>
          }
        </div>
      } @else if (reading()) {
        <p class="muted body">Reading the file…</p>
      }

      @if (error(); as message) {
        <p class="error" role="alert">{{ message }}</p>
      }

      @if (proposal(); as found) {
        @if (isEmpty(found)) {
          <p class="muted body">
            Nothing could be read from that file. That usually means a scanned image, or a layout
            that does not survive text extraction — the analysis screen's parseability check will
            say which.
          </p>
        } @else {
          <p class="muted body">
            Read from the file, not yet saved. Add what is right; edit anything that is close but
            wrong after adding.
          </p>
        }

        <!-- Read from the CV and previously discarded. No email row: the account's
             address is the one a generated CV carries. -->
        @if (proposedFields(found); as fields) {
          @if (fields.length > 0) {
            <div class="group">
              <h4>About you</h4>
              @for (field of fields; track field.field) {
                <div class="row">
                  <div class="row-info">
                    <span class="row-title">{{ field.label }}</span>
                    <span class="row-meta">{{ field.value }}</span>
                  </div>
                  <button type="button" class="add" [disabled]="busy()" (click)="addField(field)">
                    Add
                  </button>
                </div>
              }
              @if (fields.length > 1) {
                <div class="bulk">
                  <button
                    type="button"
                    class="add"
                    [disabled]="busy()"
                    (click)="addAllFields(fields)"
                  >
                    Add all {{ fields.length }}
                  </button>
                </div>
              }
            </div>
          }
        }

        @if (found.experiences.length > 0) {
          <div class="group">
            <h4>
              Roles
              @if (found.experiences.length > 1) {
                <button
                  type="button"
                  class="add"
                  [disabled]="busy()"
                  (click)="addAllRoles(found.experiences)"
                >
                  Add all {{ found.experiences.length }}
                </button>
              }
            </h4>
            @for (entry of found.experiences; track entry.organisation + entry.title) {
              <div class="row">
                <div class="row-info">
                  <span class="row-title">{{ entry.title }}</span>
                  <span class="row-meta">
                    {{ entry.organisation }}
                    @if (entry.location) {
                      &middot; {{ entry.location }}
                    }
                    @if (entry.start_date) {
                      &middot; {{ entry.start_date }} &ndash; {{ entry.end_date ?? 'present' }}
                    } @else {
                      &middot; <span class="warn">no dates found</span>
                    }
                  </span>
                </div>
                <button type="button" class="add" [disabled]="busy()" (click)="addRole(entry)">
                  Add
                </button>
              </div>
            }
          </div>
        }

        @if (found.educations.length > 0) {
          <div class="group">
            <h4>
              Education
              @if (found.educations.length > 1) {
                <button
                  type="button"
                  class="add"
                  [disabled]="busy()"
                  (click)="addAllCourses(found.educations)"
                >
                  Add all {{ found.educations.length }}
                </button>
              }
            </h4>
            @for (entry of found.educations; track entry.organisation + entry.title) {
              <div class="row">
                <div class="row-info">
                  <span class="row-title">{{ entry.title }}</span>
                  <span class="row-meta">{{ entry.organisation }}</span>
                </div>
                <button type="button" class="add" [disabled]="busy()" (click)="addCourse(entry)">
                  Add
                </button>
              </div>
            }
          </div>
        }

        @if (found.skills.length > 0) {
          <div class="group">
            <h4>
              Skills
              @if (found.skills.length > 1) {
                <button
                  type="button"
                  class="add"
                  [disabled]="busy()"
                  (click)="addAllSkills(found.skills)"
                >
                  Add all {{ found.skills.length }}
                </button>
              }
            </h4>
            <p class="group-note">
              Added without evidence. Link each one to a role afterwards, or a generated CV will not
              claim it.
            </p>
            <div class="chips">
              @for (name of found.skills; track name) {
                <button type="button" class="chip" [disabled]="busy()" (click)="addSkill(name)">
                  {{ name }} <span aria-hidden="true">+</span>
                </button>
              }
            </div>
          </div>
        }
      }
    </section>
  `,
  styles: [
    `
      .picker {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 10px;
        padding: 8px 18px 4px;
      }
      select {
        padding: 8px 10px;
        border: 1px solid var(--border-light);
        border-radius: var(--radius);
        background: var(--bg-primary);
        color: var(--text-primary);
        font-size: 13px;
        min-width: 220px;
      }
      .primary {
        padding: 8px 16px;
        border-radius: var(--radius);
        background: var(--accent);
        color: #fff;
        font-size: 13px;
        font-weight: 600;
      }
      .primary:disabled {
        opacity: 0.5;
      }

      .body {
        padding: 6px 18px 0;
      }
      .muted {
        font-size: 13px;
        color: var(--text-tertiary);
        margin: 0;
      }
      .error {
        margin: 0;
        padding: 6px 18px;
        font-size: 13px;
        color: var(--danger, #dc2626);
      }

      .group {
        padding: 10px 18px 4px;
      }
      .group h4 {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: 12px;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--text-tertiary);
        margin: 10px 0 6px;
      }
      .group h4 .add {
        text-transform: none;
        letter-spacing: 0;
        font-size: 12px;
        padding: 2px 0;
      }
      .bulk {
        display: flex;
        justify-content: flex-end;
        padding-top: 6px;
      }
      .group-note {
        margin: 0 0 8px;
        font-size: 12px;
        color: var(--text-tertiary);
      }

      .row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 16px;
        padding: 8px 0;
      }
      .row + .row {
        border-top: 1px solid var(--border-light);
      }
      .row-info {
        display: flex;
        flex-direction: column;
        gap: 2px;
        min-width: 0;
      }
      .row-title {
        font-size: 14px;
        font-weight: 600;
      }
      .row-meta {
        font-size: 12px;
        color: var(--text-tertiary);
      }
      .warn {
        color: #d97706;
      }

      .add {
        flex: none;
        font-size: 13px;
        font-weight: 600;
        color: var(--accent);
        padding: 6px 10px;
      }
      .add:disabled {
        opacity: 0.5;
      }

      .chips {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        padding-bottom: 6px;
      }
      .chip {
        font-size: 12px;
        padding: 4px 10px;
        border-radius: 999px;
        border: 1px solid var(--border-light);
        color: var(--text-secondary);
      }
      .chip:hover:not(:disabled) {
        border-color: var(--accent);
        color: var(--accent);
      }
    `,
  ],
})
export class ImportPanelComponent {
  readonly analysis = inject(AnalysisService);
  private readonly career = inject(CareerProfileService);

  /** Read this CV straight away — the first run has just watched it being uploaded. */
  readonly cvId = input<number | null>(null);

  /** Something was added, so the page should reload the profile. */
  readonly added = output<void>();

  readonly selectedId = signal<number | null>(null);
  readonly reading = signal(false);
  readonly busy = signal(false);
  readonly error = signal<string | null>(null);
  readonly proposal = signal<CvExtractionResponse | null>(null);

  constructor() {
    effect(() => {
      const given = this.cvId();
      if (given !== null && given !== this.selectedId()) {
        this.selectedId.set(given);
        this.read();
      }
    });
  }

  isEmpty(found: CvExtractionResponse): boolean {
    return (
      found.experiences.length === 0 &&
      found.educations.length === 0 &&
      found.skills.length === 0 &&
      this.proposedFields(found).length === 0
    );
  }

  onPick(event: Event): void {
    const value = (event.target as HTMLSelectElement).value;
    this.selectedId.set(value ? Number(value) : null);
    this.proposal.set(null);
  }

  read(): void {
    const cvId = this.selectedId();
    if (cvId === null) {
      return;
    }
    this.reading.set(true);
    this.error.set(null);
    this.career.importFromCv(cvId).subscribe({
      next: (found) => {
        this.proposal.set(found);
        this.reading.set(false);
      },
      error: (error: unknown) => {
        this.reading.set(false);
        this.error.set(detailOf(error, 'Could not read that CV.'));
      },
    });
  }

  /**
   * The single-value fields extraction found that the profile does not already hold.
   *
   * A field the profile already has is left out rather than offered as an overwrite:
   * the CV is the older record of the two, and silently replacing an edited headline
   * with the one from a two-year-old PDF is not an import, it is a regression.
   */
  proposedFields(found: CvExtractionResponse): ProposedField[] {
    const profile = this.career.profile();
    const candidates: [ProposedField['field'], string, string | null][] = [
      ['headline', 'Headline', found.headline],
      ['location', 'Location', found.location],
      ['phone', 'Phone', found.contact.phone],
      ['summary', 'Summary', found.summary],
      ['linkedin_url', 'LinkedIn', found.contact.linkedin_url],
      ['website_url', 'Website', found.contact.website_url],
    ];
    return candidates
      .filter(([field, , value]) => value && !profile[field])
      .map(([field, label, value]) => ({ field, label, value: value as string }));
  }

  addField(proposed: ProposedField): void {
    // Nothing to drop: proposedFields() filters out whatever the reloaded profile holds.
    this.run(this.career.updateProfile({ [proposed.field]: proposed.value }), () => undefined);
  }

  /** One request, because these are all fields of the same PATCH. */
  addAllFields(fields: ProposedField[]): void {
    const changes = Object.fromEntries(fields.map((proposed) => [proposed.field, proposed.value]));
    this.run(this.career.updateProfile(changes), () => undefined);
  }

  addRole(entry: ExtractedEntryResponse): void {
    const request = this.roleRequest(entry);
    if (request === null) {
      // The API requires a start date; proposing the row is still useful, but it has to
      // be added by hand rather than silently given a made-up date.
      this.error.set(
        `No dates were found for "${entry.title}". Add that role manually with its dates.`,
      );
      return;
    }
    this.run(request, () => this.drop('experiences', entry));
  }

  /**
   * Add every role that can be added.
   *
   * A CV with five roles and twenty skills was twenty-five separate confirmations, all
   * of them during a first run — enough friction that the import was the step people
   * abandoned. Undated roles are still refused, and counted rather than silently lost.
   */
  addAllRoles(entries: ExtractedEntryResponse[]): void {
    const datable = entries.filter((entry) => entry.start_date !== null);
    const undated = entries.length - datable.length;
    this.runAll(
      datable.map((entry) => this.roleRequest(entry)).filter((request) => request !== null),
      () => {
        this.proposal.update((found) =>
          found
            ? { ...found, experiences: found.experiences.filter((e) => !datable.includes(e)) }
            : found,
        );
        if (undated > 0) {
          this.error.set(
            `${undated} role(s) had no readable dates and were left for you to add by hand.`,
          );
        }
      },
    );
  }

  addCourse(entry: ExtractedEntryResponse): void {
    this.run(this.courseRequest(entry), () => this.drop('educations', entry));
  }

  addAllCourses(entries: ExtractedEntryResponse[]): void {
    this.runAll(
      entries.map((entry) => this.courseRequest(entry)),
      () => this.proposal.update((found) => (found ? { ...found, educations: [] } : found)),
    );
  }

  addSkill(name: string): void {
    this.run(this.career.addSkill({ name }), () => {
      this.proposal.update((found) =>
        found ? { ...found, skills: found.skills.filter((s) => s !== name) } : found,
      );
    });
  }

  addAllSkills(names: string[]): void {
    this.runAll(
      names.map((name) => this.career.addSkill({ name })),
      () => this.proposal.update((found) => (found ? { ...found, skills: [] } : found)),
    );
  }

  private roleRequest(entry: ExtractedEntryResponse): Observable<unknown> | null {
    if (!entry.start_date) {
      return null;
    }
    return this.career.addExperience({
      organisation: entry.organisation,
      title: entry.title,
      location: entry.location,
      start_date: entry.start_date,
      end_date: entry.end_date,
      description: entry.description,
    });
  }

  private courseRequest(entry: ExtractedEntryResponse): Observable<unknown> {
    return this.career.addEducation({
      institution: entry.organisation,
      qualification: entry.title,
      start_date: entry.start_date,
      end_date: entry.end_date,
    });
  }

  private run(request: Observable<unknown>, onDone: () => void): void {
    this.runAll([request], onDone);
  }

  /**
   * Run a batch and report the outcome once.
   *
   * `forkJoin` fails the whole batch on the first error, which is the right trade here:
   * the rows that did save stay saved, and the panel reloads from the profile, so a
   * partial failure is visible as the rows still sitting in the list.
   */
  private runAll(requests: Observable<unknown>[], onDone: () => void): void {
    if (requests.length === 0) {
      return;
    }
    this.busy.set(true);
    this.error.set(null);
    forkJoin(requests).subscribe({
      next: () => {
        this.busy.set(false);
        onDone();
        this.added.emit();
      },
      error: (error: unknown) => {
        this.busy.set(false);
        this.added.emit();
        this.error.set(detailOf(error, 'Could not add that.'));
      },
    });
  }

  /** Added rows leave the proposal, so what remains is what is still outstanding. */
  private drop(key: 'experiences' | 'educations', entry: ExtractedEntryResponse): void {
    const found = this.proposal();
    if (found) {
      this.proposal.set({ ...found, [key]: found[key].filter((e) => e !== entry) });
    }
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
