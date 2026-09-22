import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, input, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { CareerProfileService } from '../../core/services/career-profile.service';
import { ExperienceResponse } from '../../shared/models/api.model';

/**
 * Write the bullet points for one role from what the user remembers about it.
 *
 * Same contract as the rest of the AI on this screen: the endpoint proposes, the draft
 * lands in an editable box, and it reaches the role only when the user presses Keep.
 * The notes are the only source the model gets, so vague notes give vague bullets —
 * which is the honest outcome, and the one that shows what is still worth writing down.
 */
@Component({
  selector: 'app-role-highlights',
  imports: [FormsModule],
  template: `
    @if (!open()) {
      <button type="button" class="link start" (click)="start()">
        {{ role().description ? 'Rewrite as bullet points' : 'Describe this role' }}
      </button>
    } @else {
      <div class="drafter">
        @if (draft() === null) {
          <label class="notes-label">
            What did you do there?
            <textarea
              name="notes"
              rows="4"
              [(ngModel)]="notes"
              [disabled]="working()"
              placeholder="Rough notes are fine. What you owned, what you built, what changed because of you, which tools. Anything you remember."
            ></textarea>
          </label>
          <p class="note">
            Only what you write here is used. Nothing is looked up about
            {{ role().organisation }}, and no numbers are invented.
          </p>
          <div class="actions">
            <button
              type="button"
              class="primary"
              [disabled]="working() || notes.trim().length === 0"
              (click)="write()"
            >
              {{ working() ? 'Writing…' : 'Write the bullets' }}
            </button>
            <button type="button" class="link" [disabled]="working()" (click)="cancel()">
              Cancel
            </button>
          </div>
        } @else {
          <label class="notes-label">
            Drafted — edit anything that is not right, one bullet per line.
            <textarea name="draft" rows="6" [(ngModel)]="edited" [disabled]="working()"></textarea>
          </label>
          <div class="actions">
            <button
              type="button"
              class="primary"
              [disabled]="working() || edited.trim().length === 0"
              (click)="keep()"
            >
              {{ working() ? 'Saving…' : 'Keep them' }}
            </button>
            <button type="button" class="link" [disabled]="working()" (click)="again()">
              Back to the notes
            </button>
            <button type="button" class="link" [disabled]="working()" (click)="cancel()">
              Discard
            </button>
          </div>
        }

        @if (error(); as message) {
          <p class="error" role="alert">{{ message }}</p>
        }
      </div>
    }
  `,
  styles: [
    `
      .start {
        margin-top: 6px;
        font-size: 12px;
      }
      .drafter {
        margin-top: 8px;
        padding: 10px 12px;
        border: 1px solid var(--border-light);
        border-radius: var(--radius);
        background: var(--bg-secondary, transparent);
        max-width: 80ch;
      }
      .notes-label {
        display: flex;
        flex-direction: column;
        gap: 4px;
        font-size: 12px;
        font-weight: 600;
        color: var(--text-secondary);
      }
      textarea {
        width: 100%;
        padding: 8px 10px;
        border: 1px solid var(--border-light);
        border-radius: var(--radius);
        background: var(--bg-primary);
        color: var(--text-primary);
        font: inherit;
        font-size: 13px;
        font-weight: 400;
        resize: vertical;
      }
      .note {
        margin: 6px 0 0;
        font-size: 12px;
        color: var(--text-tertiary);
      }
      .actions {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 10px;
        margin-top: 8px;
      }
      .primary {
        padding: 6px 14px;
        border-radius: var(--radius);
        background: var(--accent);
        color: #fff;
        font-size: 13px;
        font-weight: 600;
      }
      .primary:disabled {
        opacity: 0.5;
      }
      .link:disabled {
        opacity: 0.5;
      }
      .error {
        margin: 8px 0 0;
        font-size: 12px;
        color: var(--danger, #dc2626);
      }
    `,
  ],
})
export class RoleHighlightsComponent {
  private readonly career = inject(CareerProfileService);

  readonly role = input.required<ExperienceResponse>();

  /** The role was updated, so the page should reload the profile. */
  readonly saved = output<void>();

  readonly open = signal(false);
  readonly working = signal(false);
  readonly error = signal<string | null>(null);
  readonly draft = signal<string[] | null>(null);

  notes = '';
  edited = '';

  start(): void {
    this.notes = this.role().description ?? '';
    this.draft.set(null);
    this.error.set(null);
    this.open.set(true);
  }

  cancel(): void {
    this.open.set(false);
    this.draft.set(null);
    this.error.set(null);
  }

  again(): void {
    this.draft.set(null);
    this.error.set(null);
  }

  write(): void {
    this.working.set(true);
    this.error.set(null);
    this.career.draftHighlights(this.role().id, this.notes.trim()).subscribe({
      next: (response) => {
        this.working.set(false);
        this.draft.set(response.highlights);
        this.edited = response.highlights.join('\n');
      },
      error: (error: unknown) => {
        this.working.set(false);
        this.error.set(
          detailOf(
            error,
            'Could not draft those bullets. This is the one step that needs a model configured.',
          ),
        );
      },
    });
  }

  keep(): void {
    this.working.set(true);
    this.error.set(null);
    this.career.updateExperience(this.role().id, { description: this.tidy() }).subscribe({
      next: () => {
        this.working.set(false);
        this.cancel();
        this.saved.emit();
      },
      error: (error: unknown) => {
        this.working.set(false);
        this.error.set(detailOf(error, 'Could not save those bullets.'));
      },
    });
  }

  /** Blank lines the user left while editing are not bullets. */
  private tidy(): string {
    return this.edited
      .split('\n')
      .map((line) => line.trim())
      .filter((line) => line.length > 0)
      .join('\n');
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
