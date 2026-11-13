import { Component, inject, input, signal } from '@angular/core';
import { rxResource } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { JobService } from '../../core/services/job.service';
import { Action } from '../../shared/action';
import { detailOf } from '../../shared/http-error';
import { CoverLetterDraftResponse } from '../../shared/models/api.model';
import { filenameOf, saveBlob } from '../../shared/save-file';

type FileFormat = 'docx' | 'pdf';

/**
 * The CV rendered for one posting, and a cover letter draft for it.
 *
 * The explanation comes before the document, deliberately: what makes a tailored CV
 * safe to send is seeing that every line came from the profile, and what the posting
 * wanted that the profile could not give.
 */
@Component({
  selector: 'app-tailored',
  imports: [FormsModule, RouterLink],
  template: `
    @if (cv.isLoading()) {
      <p class="muted"><span class="spinner"></span> Building…</p>
    } @else if (cv.error(); as error) {
      <p class="error" role="alert">{{ message(error) }}</p>
    } @else if (cv.hasValue() && cv.value(); as doc) {
      @if (doc.surfaced.length > 0) {
        <h4>Brought forward for this posting</h4>
        <ul class="facts">
          @for (item of doc.surfaced; track item.term) {
            <li>
              <strong>{{ item.skill }}</strong>
              @if (item.required) {
                <span class="term">required</span>
              }
              <span class="muted">
                &mdash; asked for as &ldquo;{{ item.term }}&rdquo;; evidenced by
                {{ item.evidence.join('; ') }}
              </span>
            </li>
          }
        </ul>
      } @else {
        <p class="hint">
          Nothing on your profile matched what this posting asks for, so this is your profile in
          full.
        </p>
      }

      @if (doc.substitutions.length > 0) {
        <h4>Your words, in the posting's spelling</h4>
        <ul class="facts">
          @for (swap of doc.substitutions; track swap.from_term) {
            <li>
              <strong>{{ swap.from_term }}</strong> &rarr; <strong>{{ swap.to_term }}</strong>
            </li>
          }
        </ul>
      }

      @if (doc.gaps.length > 0) {
        <h4>Asked for, and not on your profile</h4>
        <ul class="terms">
          @for (gap of doc.gaps; track gap.term) {
            <li class="term" [class.required]="gap.required">{{ gap.term }}</li>
          }
        </ul>
        <p class="hint">Named, never written in: a gap is yours to close or to leave.</p>
      }

      @if (doc.omitted_unevidenced.length > 0) {
        <p class="hint">
          Left out for having no role behind them: {{ doc.omitted_unevidenced.join(', ') }}. Cite a
          role on <a routerLink="/profile">your profile</a> and they will appear.
        </p>
      }

      <h4>
        The CV
        <span class="muted">
          parses {{ doc.parseability.score }}/100
          @if (doc.parseability.blocking.length > 0) {
            &middot; {{ doc.parseability.blocking.length }} blocking
          }
        </span>
        <span class="spacer"></span>
        <button type="button" class="link" (click)="copy(doc.markdown)">
          {{ copied() ? 'Copied' : 'Copy' }}
        </button>
        @for (format of formats; track format) {
          <button type="button" class="link" [disabled]="files.busy()" (click)="download(format)">
            .{{ format }}
          </button>
        }
      </h4>
      @if (files.error(); as message) {
        <p class="error" role="alert">{{ message }}</p>
      }
      <pre>{{ doc.markdown }}</pre>

      <h4>
        Cover letter
        <span class="spacer"></span>
        <button type="button" class="link" [disabled]="letters.busy()" (click)="draftLetter()">
          {{ letter() ? 'Rebuild draft' : 'Draft one' }}
        </button>
      </h4>
      @if (letters.error(); as message) {
        <p class="error" role="alert">{{ message }}</p>
      }
      @if (letter(); as draft) {
        @if (draft.needs_writing) {
          <p class="hint warn">
            A scaffold, not a letter: every fact in it is yours, and the paragraph in brackets is
            the part only you can write.
          </p>
        }
        @if (draft.similarity > 0) {
          <p class="hint" [class.warn]="draft.similarity_warning">
            {{ draft.similarity }}% the same as your other letters.
            @if (draft.similarity_warning) {
              Close enough to read as one letter sent twice.
            }
          </p>
        }
        <textarea rows="14" [(ngModel)]="letterBody" aria-label="Cover letter"></textarea>
        <div class="keep">
          <button type="button" class="link" [disabled]="letters.busy()" (click)="keepLetter()">
            {{ letters.busy() ? 'Saving…' : 'Keep this letter' }}
          </button>
          <span class="hint">Kept letters are what future drafts are compared with.</span>
        </div>
      }
    }
  `,
  styles: `
    :host {
      display: flex;
      flex-direction: column;
      gap: 8px;
      padding-top: 14px;
      border-top: 1px solid var(--border-light);
    }
    h4 {
      margin-top: 6px;
      font-size: 13px;
      display: flex;
      align-items: baseline;
      flex-wrap: wrap;
      gap: 10px;
    }
    h4 .muted {
      font-weight: 400;
    }
    .spacer {
      flex: 1;
    }
    .facts {
      list-style: none;
      display: flex;
      flex-direction: column;
      gap: 5px;
      font-size: 12px;
    }
    .warn {
      color: var(--warning);
    }
    pre,
    textarea {
      font-size: 12px;
      line-height: 1.5;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    }
    pre {
      padding: 14px;
      border-radius: var(--radius);
      background: var(--bg-secondary);
      border: 1px solid var(--border-light);
      white-space: pre-wrap;
      overflow-x: auto;
    }
    .keep {
      display: flex;
      align-items: baseline;
      gap: 12px;
    }
    .spinner {
      display: inline-block;
      vertical-align: -2px;
      margin-right: 6px;
    }
  `,
})
export class TailoredComponent {
  private readonly jobs = inject(JobService);

  readonly postingId = input.required<number>();

  protected readonly formats: FileFormat[] = ['docx', 'pdf'];
  protected readonly files = new Action();
  protected readonly letters = new Action();
  protected readonly copied = signal(false);

  /** Deterministic and model-free, so asking again always answers the same. */
  protected readonly cv = rxResource({
    params: () => this.postingId(),
    stream: ({ params }) => this.jobs.tailor(params),
  });

  protected readonly letter = signal<CoverLetterDraftResponse | null>(null);
  /** The editable text. Separate from `letter` so typing does not touch its scores. */
  protected readonly letterBody = signal('');

  protected message(error: unknown): string {
    return detailOf(error, 'That CV could not be built.');
  }

  protected download(format: FileFormat): void {
    this.files.run(
      this.jobs.tailorFile(this.postingId(), format),
      'That file could not be built.',
      (response) => {
        if (response.body) {
          saveBlob(response.body, filenameOf(response, `CV.${format}`));
        }
      },
    );
  }

  protected copy(markdown: string): void {
    // Refused on an insecure origin. Failing silently would look like a broken button,
    // and the text is on screen to select by hand anyway.
    navigator.clipboard.writeText(markdown).then(
      () => this.copied.set(true),
      () => this.files.error.set('Could not copy. Select the text below instead.'),
    );
  }

  protected draftLetter(): void {
    this.letters.run(
      this.jobs.coverLetter(this.postingId()),
      'That letter could not be drafted.',
      (draft) => {
        this.letter.set(draft);
        this.letterBody.set(draft.body);
      },
    );
  }

  /** Re-reads the similarity against what was saved — the text that would be sent. */
  protected keepLetter(): void {
    this.letters.run(
      this.jobs.saveCoverLetter(this.postingId(), this.letterBody()),
      'That letter could not be saved.',
      (draft) => this.letter.set(draft),
    );
  }
}
