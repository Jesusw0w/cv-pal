import { DatePipe } from '@angular/common';
import { Component, computed, inject, linkedSignal } from '@angular/core';

import { AnalysisService, rejectUpload } from '../../core/services/analysis.service';
import { Action } from '../../shared/action';
import { ConfirmButtonComponent } from '../../shared/confirm-button.component';
import { CvCheckComponent } from './cv-check.component';
import { CvReviewComponent } from './cv-review.component';

/**
 * The CVs the user uploaded, and everything that can be asked of one: whether an ATS
 * can read it, how it answers a posting, and what a language model would change.
 *
 * One screen rather than three because all three start with "choose a CV". The newest
 * is chosen already, so the common case — check the file just uploaded — is no clicks.
 */
@Component({
  selector: 'app-cvs',
  imports: [DatePipe, ConfirmButtonComponent, CvCheckComponent, CvReviewComponent],
  template: `
    <div class="page">
      <section class="card">
        <div class="card-header">
          <h3>Your CVs</h3>
          <label class="upload">
            <input
              type="file"
              accept=".pdf,.docx"
              [disabled]="action.busy()"
              (change)="onFileChosen($event)"
            />
            {{ action.busy() ? 'Working…' : 'Upload a CV' }}
          </label>
        </div>

        @if (action.error(); as message) {
          <p class="error body" role="alert">{{ message }}</p>
        }
        @if (analysis.error()) {
          <p class="error body" role="alert">
            Could not load your CVs.
            <button type="button" class="link" (click)="analysis.reload()">Try again</button>
          </p>
        }

        <ul class="rows">
          @for (cv of analysis.documents(); track cv.id) {
            <li class="row" [class.selected]="cv.id === selectedId()">
              <button
                type="button"
                class="row-main pick"
                [attr.aria-pressed]="cv.id === selectedId()"
                (click)="selectedId.set(cv.id)"
              >
                <span class="row-title">{{ cv.filename }}</span>
                <span class="row-meta">
                  version {{ cv.version }} &middot; uploaded {{ cv.created_at | date: 'd MMM y' }}
                </span>
              </button>
              <app-confirm-button
                [label]="'Delete ' + cv.filename"
                [disabled]="action.busy()"
                (confirmed)="remove(cv.id)"
              />
            </li>
          } @empty {
            @if (!analysis.isLoading()) {
              <li class="empty">Nothing uploaded yet. A PDF or DOCX under 10 MB.</li>
            }
          }
        </ul>
      </section>

      @if (selected(); as cv) {
        <app-cv-check [cvId]="cv.id" />
        <app-cv-review [cvId]="cv.id" />
      }
    </div>
  `,
  styles: `
    .pick {
      text-align: left;
    }
    .selected .row-title {
      color: var(--accent);
    }
  `,
})
export class CvsComponent {
  protected readonly analysis = inject(AnalysisService);
  protected readonly action = new Action();

  /** The chosen CV: kept while it exists, otherwise the newest. */
  protected readonly selectedId = linkedSignal<number[], number | null>({
    source: () => this.analysis.documents().map((cv) => cv.id),
    computation: (ids, previous) =>
      previous?.value != null && ids.includes(previous.value) ? previous.value : (ids[0] ?? null),
  });

  protected readonly selected = computed(
    () => this.analysis.documents().find((cv) => cv.id === this.selectedId()) ?? null,
  );

  protected onFileChosen(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    // Let the same file be chosen again after a failure.
    input.value = '';
    if (!file) {
      return;
    }

    const rejection = rejectUpload(file);
    if (rejection !== null) {
      this.action.error.set(rejection);
      return;
    }

    this.action.run(this.analysis.upload(file), 'Could not upload that file.', (cv) => {
      this.analysis.reload();
      this.selectedId.set(cv.id);
    });
  }

  protected remove(cvId: number): void {
    this.action.run(this.analysis.delete(cvId), 'Could not delete that CV.', () =>
      this.analysis.reload(),
    );
  }
}
