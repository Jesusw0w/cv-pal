import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { AnalysisService, rejectUpload } from '../../core/services/analysis.service';
import { CvResponse } from '../../shared/models/api.model';

/**
 * The CV library: every file the user has uploaded.
 *
 * Shows only what `/cvs` actually has. An earlier version invented descriptions, tags
 * and statuses the API does not carry, and implied a cover-letter feature that did
 * not exist.
 *
 * Uploading is deliberately available here *and* on the analysis screen: this is where
 * a user looks for their files, and making them go elsewhere to add one is the kind of
 * friction that reads as a missing feature.
 */
@Component({
  selector: 'app-documents',
  imports: [DatePipe, RouterLink],
  template: `
    <div class="page">
      <header class="intro">
        <h1>Documents</h1>
        <p>
          The CVs you have uploaded. Each one can be checked against a posting on the
          <a routerLink="/analysis">analysis screen</a>, or reviewed by a language model under
          <a routerLink="/ai-tools">AI review</a>.
        </p>
      </header>

      <section class="card">
        <div class="card-header">
          <h3>Your CVs</h3>
          <label class="upload">
            <input
              type="file"
              accept=".pdf,.docx"
              (change)="onFileChosen($event)"
              [disabled]="uploading()"
            />
            {{ uploading() ? 'Uploading…' : 'Upload a CV' }}
          </label>
        </div>

        @if (error(); as message) {
          <p class="error" role="alert">{{ message }}</p>
        }

        @if (analysis.error()) {
          <p class="error" role="alert">
            Could not load your documents.
            <button type="button" class="link" (click)="analysis.reload()">Try again</button>
          </p>
        } @else if (analysis.isLoading()) {
          <p class="muted">Loading…</p>
        }

        <ul class="docs">
          @for (cv of analysis.documents(); track cv.id) {
            <li class="doc">
              <div class="doc-info">
                <span class="doc-name">{{ cv.filename }}</span>
                <span class="doc-meta">
                  version {{ cv.version }} &middot; uploaded {{ cv.created_at | date: 'd MMM y' }}
                </span>
              </div>
              <div class="doc-actions">
                <a routerLink="/analysis" class="link">Analyse</a>
                <a routerLink="/ai-tools" class="link">Review</a>
                <button
                  type="button"
                  class="remove"
                  [attr.aria-label]="'Delete ' + cv.filename"
                  (click)="remove(cv)"
                >
                  Delete
                </button>
              </div>
            </li>
          } @empty {
            @if (!analysis.isLoading()) {
              <li class="empty">Nothing uploaded yet. A PDF or DOCX under 10 MB.</li>
            }
          }
        </ul>
      </section>

      <p class="footnote">
        Generated CVs and cover letters are not built yet — this lists the files you uploaded, not
        documents CV Pal produced.
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
        max-width: 820px;
      }
      .intro h1 {
        font-size: 22px;
        margin: 0 0 6px;
      }
      .intro p {
        margin: 0;
        font-size: 14px;
        color: var(--text-secondary);
        max-width: 72ch;
      }
      .intro a,
      .link {
        color: var(--accent);
        font-weight: 600;
      }

      .upload {
        font-size: 13px;
        font-weight: 600;
        color: var(--accent);
        cursor: pointer;
      }
      .upload input {
        display: none;
      }

      .docs {
        list-style: none;
        margin: 0;
        padding: 8px;
        display: flex;
        flex-direction: column;
        gap: 2px;
      }
      .doc {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 16px;
        padding: 10px 10px;
        border-radius: var(--radius);
      }
      .doc:hover {
        background: var(--bg-hover);
      }
      .doc + .doc {
        border-top: 1px solid var(--border-light);
      }
      .doc-info {
        display: flex;
        flex-direction: column;
        gap: 2px;
        min-width: 0;
      }
      .doc-name {
        font-size: 14px;
        font-weight: 500;
      }
      .doc-meta {
        font-size: 12px;
        color: var(--text-tertiary);
      }
      .doc-actions {
        display: flex;
        align-items: center;
        gap: 14px;
        flex: none;
        font-size: 12px;
      }
      .remove {
        font-size: 12px;
        color: var(--text-tertiary);
      }
      .remove:hover {
        color: var(--danger, #dc2626);
      }

      .empty,
      .muted {
        padding: 12px;
        font-size: 13px;
        color: var(--text-tertiary);
        margin: 0;
      }
      .error {
        margin: 0;
        padding: 4px 18px 10px;
        font-size: 13px;
        color: var(--danger, #dc2626);
      }
      .footnote {
        margin: 0;
        font-size: 12px;
        color: var(--text-tertiary);
      }

      @media (max-width: 768px) {
        .page {
          padding: 16px;
        }
        .doc {
          flex-direction: column;
          align-items: flex-start;
          gap: 8px;
        }
      }
    `,
  ],
})
export class DocumentsComponent {
  readonly analysis = inject(AnalysisService);

  readonly uploading = signal(false);
  readonly error = signal<string | null>(null);

  onFileChosen(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) {
      return;
    }
    input.value = '';

    const rejection = rejectUpload(file);
    if (rejection !== null) {
      this.error.set(rejection);
      return;
    }

    this.uploading.set(true);
    this.error.set(null);
    this.analysis.upload(file).subscribe({
      next: () => {
        this.uploading.set(false);
        this.analysis.reload();
      },
      error: (error: unknown) => {
        this.uploading.set(false);
        this.error.set(messageFor(error, 'Could not upload that file.'));
      },
    });
  }

  remove(cv: CvResponse): void {
    this.analysis.delete(cv.id).subscribe({
      next: () => this.analysis.reload(),
      error: (error: unknown) => this.error.set(messageFor(error, 'Could not delete that file.')),
    });
  }
}

function messageFor(error: unknown, fallback: string): string {
  if (error instanceof HttpErrorResponse) {
    const detail = (error.error as { detail?: unknown } | null)?.detail;
    if (typeof detail === 'string') {
      return detail;
    }
  }
  return fallback;
}
