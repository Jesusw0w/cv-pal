import { HttpErrorResponse } from '@angular/common/http';
import { DatePipe } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { ApplicationService } from '../../core/services/application.service';
import { GoalsService } from '../../core/services/goals.service';
import { JobService } from '../../core/services/job.service';
import {
  CoverLetterDraftResponse,
  EmploymentType,
  ScoredPostingResponse,
  TailoredCvResponse,
} from '../../shared/models/api.model';

/** One open tailoring result, tagged with the posting it belongs to. */
interface TailoredState {
  id: number;
  cv: TailoredCvResponse | null;
  error: string | null;
}

/** One open cover letter draft, tagged the same way. */
interface LetterState {
  id: number;
  draft: CoverLetterDraftResponse | null;
  error: string | null;
}

/**
 * The filename the server chose, from `Content-Disposition`.
 *
 * Falls back rather than composing one: the server sanitises the company and title
 * before putting them in that header, and rebuilding the name here would duplicate
 * logic that exists for a security reason.
 */
function filenameFrom(header: string | null, format: 'docx' | 'pdf'): string {
  const match = /filename="([^"]+)"/.exec(header ?? '');
  return match ? match[1] : `CV.${format}`;
}

/** The sources that can be watched. `manual` is a paste, so there is nothing to sync. */
type WatchableSource = 'remotive' | 'greenhouse' | 'lever';

interface SourceFacts {
  /** What the source can answer, in the user's terms rather than the vendor's. */
  covers: string;
  /**
   * Which contracts the source actually states.
   *
   * Worth its own line rather than a footnote: it is the difference between a list you
   * can filter and one you have to open every posting to understand — and it is the
   * field the two ATS boards genuinely do not carry, so promising it uniformly would
   * be a lie about two thirds of the sources.
   */
  contracts: string;
  hint: string;
  /** Present when the identifier is a fixed taxonomy rather than a company slug. */
  categories?: readonly { slug: string; name: string }[];
}

/**
 * Remotive's categories, IT-relevant subset.
 *
 * The slugs are theirs and appear in every posting URL, which is what the backend
 * filters on. A select rather than a text field because an unknown slug is
 * indistinguishable from a category that is simply quiet today — it would sync
 * successfully, save nothing, and look like a bug for as long as the user kept it.
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

const SOURCES: Record<WatchableSource, SourceFacts> = {
  remotive: {
    covers: 'Remote-only roles across every company on Remotive, by category.',
    contracts: 'Full-time, contract, freelance, part-time and internship — stated per posting.',
    hint:
      'Remotive publishes a rotating feed of what is currently open, delayed 24 hours, ' +
      'so a sync finds different roles each day and a quiet category is normal.',
    categories: REMOTIVE_CATEGORIES,
  },
  greenhouse: {
    covers: "One company's open roles. You need to know the company first.",
    contracts: 'Not stated — Greenhouse does not publish the contract as a field.',
    hint: 'The slug is the last part of the board URL, the acme in boards.greenhouse.io/acme.',
  },
  lever: {
    covers: "One company's open roles. You need to know the company first.",
    contracts: 'Not stated — Lever does not publish the contract as a field.',
    hint: 'The slug is the last part of the board URL, the acme in jobs.lever.co/acme.',
  },
};

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
 * Two lists on purpose, not one sorted list. A **blocked** posting broke a
 * non-negotiable, so it is filtered out of the ranking entirely rather than sorted to
 * the bottom — mixing the two would make the ordering meaningless. It is still shown,
 * with the reason, because a filter the user cannot see is one they cannot revisit.
 */
@Component({
  selector: 'app-job-search',
  imports: [DatePipe, FormsModule, RouterLink],
  template: `
    <div class="page">
      <header class="intro">
        <h1>Jobs</h1>
        <p>
          Scored against <a routerLink="/goals">your goals</a> and the evidenced parts of
          <a routerLink="/profile">your profile</a>. Nothing here is applied for.
        </p>
      </header>

      <section class="card">
        <div class="card-header">
          <h3>Add a posting</h3>
          <div class="tabs">
            <button type="button" [class.on]="mode() === 'url'" (click)="mode.set('url')">
              Link
            </button>
            <button type="button" [class.on]="mode() === 'paste'" (click)="mode.set('paste')">
              Paste
            </button>
          </div>
        </div>

        @if (mode() === 'url') {
          <form class="body" (ngSubmit)="importUrl()">
            <input
              [(ngModel)]="url"
              name="url"
              placeholder="https://remotive.com/remote-jobs/… or a Greenhouse or Lever link"
              aria-label="Job posting link"
            />
            <p class="hint">
              Remotive, Greenhouse and Lever links are read through their own APIs. Anything else —
              LinkedIn, a company careers page — needs the Paste tab: CV Pal does not fetch
              arbitrary pages.
            </p>
            <button type="submit" class="primary" [disabled]="busy() || !url.trim()">
              {{ busy() ? 'Reading…' : 'Add from link' }}
            </button>
          </form>
        } @else {
          <form class="body" (ngSubmit)="paste()">
            <div class="row">
              <input
                [(ngModel)]="draft.title"
                name="title"
                placeholder="Job title"
                aria-label="Job title"
              />
              <input
                [(ngModel)]="draft.company"
                name="company"
                placeholder="Company"
                aria-label="Company"
              />
              <input
                [(ngModel)]="draft.location"
                name="location"
                placeholder="Location"
                aria-label="Location"
              />
            </div>
            <textarea
              rows="7"
              [(ngModel)]="draft.description"
              name="description"
              placeholder="Paste the full posting, including the requirements list."
              aria-label="Job description"
            ></textarea>
            <p class="hint">This route always works — no board to be down, no page to change.</p>
            <button type="submit" class="primary" [disabled]="busy() || !canPaste()">
              {{ busy() ? 'Saving…' : 'Save posting' }}
            </button>
          </form>
        }

        @if (error(); as message) {
          <p class="error" role="alert">{{ message }}</p>
        }
      </section>

      <section class="card">
        <div class="card-header">
          <h3>Watched sources</h3>
          @if (jobs.sources().length > 0) {
            <button type="button" class="link" [disabled]="busy()" (click)="syncAll()">
              {{ busy() ? 'Syncing…' : 'Sync all' }}
            </button>
          } @else {
            <span class="card-note">Sync saves what is new, and scores it</span>
          }
        </div>
        <form class="body watch" (ngSubmit)="watch()">
          <!-- Not [(ngModel)]: the target is a signal, so the write side is explicit.
               Changing source clears the identifier — a company slug is meaningless as
               a Remotive category, and carrying it over would submit nonsense. -->
          <select
            [ngModel]="watchSource()"
            (ngModelChange)="chooseSource($event)"
            name="watchSource"
            aria-label="Source"
          >
            <option value="remotive">Remotive — remote roles, any company</option>
            <option value="greenhouse">Greenhouse — one company's board</option>
            <option value="lever">Lever — one company's board</option>
          </select>
          @if (source().categories; as categories) {
            <select [(ngModel)]="watchId" name="watchId" aria-label="Category">
              <option value="" disabled>Choose a category…</option>
              @for (category of categories; track category.slug) {
                <option [value]="category.slug">{{ category.name }}</option>
              }
            </select>
          } @else {
            <input
              [(ngModel)]="watchId"
              name="watchId"
              placeholder="company slug, e.g. acme"
              aria-label="Company slug"
            />
          }
          <button type="submit" class="primary" [disabled]="busy() || !watchId.trim()">
            Watch
          </button>
          <!-- Opt-in. A company board is every open role it has, and for most searches
               that is mostly noise — but a sync that silently drops postings is worse,
               so this is asked for rather than assumed. -->
          <label class="watch-filter">
            <input type="checkbox" [(ngModel)]="watchFilterByGoals" name="watchFilter" />
            <span>
              Only save postings matching my
              <a routerLink="/goals">target roles</a>
              @if (goals.goals().target_roles.length === 0) {
                <em>&mdash; none set yet, so this saves everything until you set some</em>
              }
            </span>
          </label>
        </form>

        <!-- What this source can and cannot tell you, before you commit to watching it.
             The contract line is the one that changes which postings are worth opening,
             and it is the field the two ATS boards genuinely do not carry. -->
        <dl class="source-facts">
          <div>
            <dt>Covers</dt>
            <dd>{{ source().covers }}</dd>
          </div>
          <div>
            <dt>Contract types</dt>
            <dd>{{ source().contracts }}</dd>
          </div>
        </dl>
        <p class="hint watch-hint">
          {{ source().hint }} Syncing saves everything new and nothing you already have, so a cron
          entry hitting it nightly is safe.
        </p>
        @for (source of jobs.sources(); track source.id) {
          <div class="blocked">
            <div>
              <span class="blocked-title">{{ source.label }}</span>
              <span class="blocked-why">
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
            <div class="job-actions">
              <button type="button" class="link" [disabled]="busy()" (click)="sync(source.id)">
                Sync now
              </button>
              <button type="button" class="remove" (click)="unwatch(source.id)">Remove</button>
            </div>
          </div>
        }
        @if (syncNote(); as note) {
          <p class="hint watch-hint">{{ note }}</p>
        }
      </section>

      @if (jobs.error()) {
        <p class="card notice" role="alert">
          Could not load your jobs.
          <button type="button" class="link" (click)="jobs.reload()">Try again</button>
        </p>
      } @else if (jobs.isLoading()) {
        <p class="card notice">Loading…</p>
      }

      @for (entry of jobs.matches(); track entry.posting.id) {
        <article class="card job">
          <div class="job-head">
            <div>
              <h3>{{ entry.posting.title }}</h3>
              <p class="job-meta">
                {{ entry.posting.company ?? 'Unknown company' }}
                @if (entry.posting.location) {
                  &middot; {{ entry.posting.location }}
                }
                &middot; saved {{ entry.posting.created_at | date: 'd MMM' }}
                @if (entry.posting.source !== 'manual') {
                  &middot; via {{ entry.posting.source }}
                }
              </p>
              <!-- Absent when the source did not say. Nothing is shown then, because
                   "full time" is a guess and this is the field people filter on. -->
              @if (contractOf(entry.posting.employment_type); as contract) {
                <span class="contract">{{ contract }}</span>
              }
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
            <p class="missing">
              <span class="missing-label">Required, and not on your profile:</span>
              @for (term of entry.match.missing_required; track term) {
                <span class="term">{{ term }}</span>
              }
            </p>
          }

          <div class="job-actions">
            @if (entry.posting.source_url; as link) {
              <a [href]="link" target="_blank" rel="noopener noreferrer" class="link"
                >Open posting</a
              >
            }
            <button
              type="button"
              class="link"
              [disabled]="tailoring() === entry.posting.id"
              (click)="tailorFor(entry.posting.id)"
            >
              {{ tailoring() === entry.posting.id ? 'Building…' : 'Tailor my CV' }}
            </button>
            <!-- The step the product used to have no record of. One click from the
                 posting, because a form asking you to retype the role is a form nobody
                 fills in. -->
            @if (applications.appliedPostingIds().has(entry.posting.id)) {
              <a routerLink="/applications" class="applied-note">Applied &middot; track it</a>
            } @else {
              <button
                type="button"
                class="link"
                [disabled]="busy()"
                (click)="markApplied(entry.posting.id)"
              >
                I applied
              </button>
            }
            <button type="button" class="remove" (click)="remove(entry)">Remove</button>
          </div>

          @if (tailored()?.id === entry.posting.id) {
            @if (tailored()!.cv; as cv) {
              <section class="tailored">
                <!-- The explanation comes first, deliberately. The document is the easy
                     part to trust and the wrong part to trust blindly; what makes it
                     safe to send is being able to see that every line came from the
                     profile, and what the posting wanted that it could not. -->
                @if (cv.surfaced.length > 0) {
                  <h4>Brought forward for this posting</h4>
                  <ul class="surfaced">
                    @for (item of cv.surfaced; track item.term) {
                      <li>
                        <strong>{{ item.skill }}</strong>
                        @if (item.required) {
                          <span class="req">required</span>
                        }
                        <span class="why">
                          &mdash; the posting asks for &ldquo;{{ item.term }}&rdquo;; evidenced by
                          {{ item.evidence.join('; ') }}
                        </span>
                      </li>
                    }
                  </ul>
                } @else {
                  <p class="none">
                    Nothing on your profile matched what this posting asks for. The CV below is your
                    profile in full &mdash; nothing was added to fit it.
                  </p>
                }

                @if (cv.gaps.length > 0) {
                  <h4>Asked for, and not on your profile</h4>
                  <p class="gaps">
                    @for (gap of cv.gaps; track gap.term) {
                      <span class="term" [class.req-term]="gap.required">{{ gap.term }}</span>
                    }
                  </p>
                  <p class="note">
                    Named, never written in. Adding a skill you cannot evidence is the thing you
                    would have to defend in the interview.
                  </p>
                }

                @if (cv.omitted_unevidenced.length > 0) {
                  <p class="note">
                    Left out for having no role behind them:
                    {{ cv.omitted_unevidenced.join(', ') }}. Cite a role on
                    <a routerLink="/profile">your profile</a> and they will appear.
                  </p>
                }

                @if (cv.substitutions.length > 0) {
                  <h4>Your words, in the posting's spelling</h4>
                  <ul class="surfaced">
                    @for (swap of cv.substitutions; track swap.from_term) {
                      <li>
                        <strong>{{ swap.from_term }}</strong> &rarr;
                        <strong>{{ swap.to_term }}</strong>
                        <span class="why">
                          &mdash; the same thing, so the document uses theirs
                        </span>
                      </li>
                    }
                  </ul>
                  <p class="note">
                    The only text here that is not literally yours. It happens only where the alias
                    map states two spellings mean one thing, which is why it never fires on terms
                    outside software.
                  </p>
                }

                <h4>
                  The CV
                  <span class="parse">
                    parses {{ cv.parseability.score }}/100
                    @if (cv.parseability.blocking.length === 0) {
                      &middot; nothing blocking
                    }
                  </span>
                  <button type="button" class="link copy" (click)="copy(cv.markdown)">
                    {{ copied() ? 'Copied' : 'Copy' }}
                  </button>
                  <button
                    type="button"
                    class="link"
                    [disabled]="downloading() !== null"
                    (click)="download(entry.posting.id, 'docx')"
                  >
                    {{ downloading() === 'docx' ? 'Building…' : '.docx' }}
                  </button>
                  <button
                    type="button"
                    class="link"
                    [disabled]="downloading() !== null"
                    (click)="download(entry.posting.id, 'pdf')"
                  >
                    {{ downloading() === 'pdf' ? 'Building…' : '.pdf' }}
                  </button>
                </h4>
                <pre class="doc">{{ cv.markdown }}</pre>

                <!-- The letter is a separate act from the CV: one is assembled from
                     facts and finished, the other is assembled from facts and is not. -->
                <h4>
                  Cover letter
                  <button
                    type="button"
                    class="link copy"
                    [disabled]="lettering()"
                    (click)="draftLetter(entry.posting.id)"
                  >
                    {{ letter()?.id === entry.posting.id ? 'Rebuild draft' : 'Draft one' }}
                  </button>
                </h4>

                @if (letter()?.id === entry.posting.id) {
                  @if (letter()!.draft; as draft) {
                    @if (draft.needs_writing) {
                      <p class="note warn-note">
                        This is a <strong>scaffold, not a letter</strong>. Every fact in it is yours
                        and verified; the paragraph in brackets is the part nothing can assemble for
                        you, and a reader can tell when it is missing.
                      </p>
                    }
                    <p class="note" [class.warn-note]="draft.similarity_warning">
                      Repeats your other letters: <strong>{{ draft.similarity }}%</strong>.
                      @if (draft.similarity_warning) {
                        Close enough to read as the same letter sent twice. Nothing here lowers that
                        except writing something true about this job.
                      } @else if (draft.similarity === 0) {
                        Nothing to compare against yet.
                      }
                    </p>
                    <textarea
                      class="letter"
                      rows="14"
                      [ngModel]="letterBody()"
                      (ngModelChange)="letterBody.set($event)"
                      name="letterBody"
                      aria-label="Cover letter"
                    ></textarea>
                    <div class="job-actions">
                      <button
                        type="button"
                        class="link"
                        [disabled]="lettering()"
                        (click)="keepLetter(entry.posting.id)"
                      >
                        {{ lettering() ? 'Saving…' : 'Keep this letter' }}
                      </button>
                      <span class="note">
                        Keeping it is what future drafts get measured against.
                      </span>
                    </div>
                  } @else {
                    <p class="error" role="alert">{{ letter()!.error }}</p>
                  }
                }
              </section>
            } @else {
              <p class="error" role="alert">{{ tailored()!.error }}</p>
            }
          }
        </article>
      } @empty {
        @if (!jobs.isLoading() && jobs.blocked().length === 0) {
          <p class="card notice">
            No postings yet. Add one above &mdash; then set
            <a routerLink="/goals">your goals</a> so the scores mean something.
          </p>
        }
      }

      @if (jobs.blocked().length > 0) {
        <section class="card">
          <div class="card-header">
            <h3>Ruled out by your non-negotiables</h3>
            <span class="card-note">Shown so you can change your mind, not ranked</span>
          </div>
          @for (entry of jobs.blocked(); track entry.posting.id) {
            <div class="blocked">
              <div>
                <span class="blocked-title">{{ entry.posting.title }}</span>
                <span class="blocked-why">{{ entry.match.blocked_by }}</span>
              </div>
              <button type="button" class="remove" (click)="remove(entry)">Remove</button>
            </div>
          }
        </section>
      }
    </div>
  `,
  styles: [
    `
      .page {
        padding: 28px;
        display: flex;
        flex-direction: column;
        gap: 20px;
        max-width: 860px;
      }
      .intro h1 {
        font-size: 22px;
        margin: 0 0 6px;
      }
      .intro p {
        margin: 0;
        font-size: 14px;
        color: var(--text-secondary);
      }
      .intro a,
      .link {
        color: var(--accent);
        font-weight: 600;
      }

      .tabs {
        display: flex;
        gap: 4px;
      }
      .tabs button {
        font-size: 12px;
        font-weight: 600;
        padding: 4px 10px;
        border-radius: 999px;
        color: var(--text-tertiary);
        border: 1px solid transparent;
      }
      .tabs button.on {
        color: var(--accent);
        border-color: var(--accent);
      }

      .body {
        display: flex;
        flex-direction: column;
        gap: 10px;
        padding: 12px 18px 18px;
      }
      .row {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }
      .row input {
        flex: 1 1 160px;
      }
      input,
      textarea {
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
      .hint {
        margin: 0;
        font-size: 12px;
        color: var(--text-tertiary);
        max-width: 70ch;
      }
      .primary {
        align-self: flex-start;
        padding: 9px 18px;
        border-radius: var(--radius);
        background: var(--accent);
        color: #fff;
        font-size: 13px;
        font-weight: 600;
      }
      .primary:disabled {
        opacity: 0.5;
      }
      .error {
        margin: 0;
        padding: 0 18px 14px;
        font-size: 13px;
        color: var(--danger, #dc2626);
      }
      .notice {
        margin: 0;
        padding: 16px 18px;
        font-size: 13px;
        color: var(--text-secondary);
      }
      .card-note {
        font-size: 12px;
        color: var(--text-tertiary);
      }

      .job {
        padding: 18px;
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
        margin: 0;
        font-size: 16px;
      }
      .job-meta {
        margin: 3px 0 0;
        font-size: 12px;
        color: var(--text-tertiary);
      }
      .score {
        font-size: 24px;
        font-weight: 700;
        flex: none;
      }
      .score small {
        font-size: 12px;
        font-weight: 500;
        color: var(--text-tertiary);
      }
      .score.good {
        color: #16a34a;
      }
      .score.fair {
        color: #d97706;
      }
      .score.poor {
        color: var(--danger, #dc2626);
      }

      .reasons {
        list-style: none;
        margin: 0;
        padding: 0;
        display: flex;
        flex-direction: column;
        gap: 4px;
      }
      .reasons li {
        font-size: 12px;
        color: var(--text-secondary);
      }
      .reasons strong {
        color: var(--text-primary);
        font-weight: 600;
      }

      .missing {
        margin: 0;
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 6px;
      }
      .missing-label {
        font-size: 12px;
        color: var(--text-tertiary);
      }
      .term {
        font-size: 12px;
        padding: 2px 8px;
        border-radius: 999px;
        border: 1px solid color-mix(in srgb, var(--danger, #dc2626) 45%, transparent);
        color: var(--danger, #dc2626);
      }

      .contract {
        display: inline-block;
        margin-top: 6px;
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.02em;
        padding: 2px 8px;
        border-radius: 999px;
        border: 1px solid var(--border-light);
        color: var(--text-secondary);
      }

      .source-facts {
        margin: 0;
        padding: 0 18px 4px;
        display: grid;
        gap: 6px;
      }
      .source-facts > div {
        display: flex;
        gap: 8px;
        font-size: 12px;
      }
      .source-facts dt {
        flex: 0 0 96px;
        font-weight: 600;
        color: var(--text-secondary);
      }
      .source-facts dd {
        margin: 0;
        color: var(--text-tertiary);
        max-width: 60ch;
      }

      .tailored {
        margin-top: 4px;
        padding-top: 14px;
        border-top: 1px solid var(--border-light);
        display: flex;
        flex-direction: column;
        gap: 8px;
      }
      .tailored h4 {
        margin: 6px 0 0;
        font-size: 13px;
        display: flex;
        align-items: baseline;
        gap: 10px;
        flex-wrap: wrap;
      }
      .parse {
        font-size: 12px;
        font-weight: 400;
        color: var(--text-tertiary);
      }
      .copy {
        margin-left: auto;
        font-size: 12px;
      }

      .surfaced {
        list-style: none;
        margin: 0;
        padding: 0;
        display: flex;
        flex-direction: column;
        gap: 5px;
      }
      .surfaced li {
        font-size: 12px;
        color: var(--text-secondary);
      }
      .surfaced strong {
        color: var(--text-primary);
      }
      .why {
        color: var(--text-tertiary);
      }
      .req {
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        padding: 1px 6px;
        border-radius: 999px;
        margin-left: 4px;
        border: 1px solid var(--border-light);
        color: var(--text-tertiary);
      }
      .none,
      .note {
        margin: 0;
        font-size: 12px;
        color: var(--text-tertiary);
        max-width: 70ch;
      }
      .gaps {
        margin: 0;
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
      }
      .gaps .term {
        border-color: var(--border-light);
        color: var(--text-tertiary);
      }
      .gaps .req-term {
        border-color: color-mix(in srgb, var(--danger, #dc2626) 45%, transparent);
        color: var(--danger, #dc2626);
      }

      .letter {
        width: 100%;
        min-height: 220px;
        resize: vertical;
        font-size: 12px;
        line-height: 1.5;
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      }
      .warn-note {
        color: #d97706;
      }

      .doc {
        margin: 0;
        padding: 14px;
        border-radius: var(--radius);
        background: var(--bg-hover);
        border: 1px solid var(--border-light);
        font-size: 12px;
        line-height: 1.5;
        white-space: pre-wrap;
        overflow-x: auto;
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      }

      .job-actions {
        display: flex;
        align-items: center;
        gap: 14px;
      }
      .remove {
        font-size: 12px;
        color: var(--text-tertiary);
      }
      .remove:hover {
        color: var(--danger, #dc2626);
      }

      .blocked {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 16px;
        padding: 10px 18px;
      }
      .blocked + .blocked {
        border-top: 1px solid var(--border-light);
      }
      .blocked-title {
        font-size: 14px;
        font-weight: 500;
        margin-right: 8px;
      }
      .blocked-why {
        font-size: 12px;
        color: var(--text-tertiary);
      }
      .watch {
        flex-direction: row;
        flex-wrap: wrap;
        align-items: center;
      }
      .watch select,
      .watch input {
        flex: 0 1 auto;
      }
      .watch-hint {
        padding: 0 18px 14px;
      }
      .watch-filter {
        flex: 1 0 100%;
        display: flex;
        align-items: baseline;
        gap: 8px;
        font-size: 12px;
        color: var(--text-secondary);
      }
      .watch-filter input {
        flex: none;
      }
      .watch-filter em {
        color: var(--text-tertiary);
        font-style: normal;
      }
      .applied-note {
        font-size: 13px;
        font-weight: 600;
        color: var(--accent);
        text-decoration: none;
      }

      @media (max-width: 768px) {
        .page {
          padding: 16px;
        }
      }
    `,
  ],
})
export class JobSearchComponent {
  readonly jobs = inject(JobService);
  /** Read only to say whether the filter would currently have anything to match on. */
  readonly goals = inject(GoalsService);
  readonly applications = inject(ApplicationService);

  readonly mode = signal<'url' | 'paste'>('url');
  readonly busy = signal(false);
  readonly error = signal<string | null>(null);

  url = '';
  draft = { title: '', company: '', location: '', description: '' };
  /** Remotive first: it is the only source that answers "what is open at all". */
  readonly watchSource = signal<WatchableSource>('remotive');
  /** Whether a newly watched board should save only postings matching the goals. */
  watchFilterByGoals = false;
  watchId = '';

  readonly syncNote = signal<string | null>(null);

  /** The posting currently being tailored for, or null. */
  readonly tailoring = signal<number | null>(null);
  /** The one open result, tagged with its posting so it cannot be read against another. */
  readonly tailored = signal<TailoredState | null>(null);
  readonly copied = signal(false);
  /** Which format is being built, so only that button says so. */
  readonly downloading = signal<'docx' | 'pdf' | null>(null);
  readonly lettering = signal(false);
  /** The one open letter, tagged with its posting for the same reason the CV is. */
  readonly letter = signal<LetterState | null>(null);
  /** The editable text. Separate from `letter` so typing does not re-read the score. */
  readonly letterBody = signal('');

  /** What the chosen source covers and states, shown before the user commits to it. */
  readonly source = computed(() => SOURCES[this.watchSource()]);

  /** The display name of a contract type, or null when the source did not state one. */
  contractOf(type: EmploymentType | null): string | null {
    return type === null ? null : CONTRACT_LABELS[type];
  }

  chooseSource(source: WatchableSource): void {
    this.watchSource.set(source);
    this.watchId = '';
  }

  /** Mirrors the API's own minimum, so the button explains itself instead of 422-ing. */
  canPaste(): boolean {
    return this.draft.title.trim().length > 0 && this.draft.description.trim().length >= 50;
  }

  tone(score: number): string {
    if (score >= 70) return 'good';
    return score >= 45 ? 'fair' : 'poor';
  }

  importUrl(): void {
    this.run(this.jobs.importUrl(this.url.trim()), () => (this.url = ''));
  }

  paste(): void {
    this.run(
      this.jobs.paste({
        title: this.draft.title.trim(),
        company: this.draft.company.trim() || null,
        location: this.draft.location.trim() || null,
        description: this.draft.description.trim(),
      }),
      () => (this.draft = { title: '', company: '', location: '', description: '' }),
    );
  }

  watch(): void {
    this.run(
      this.jobs.watchBoard(this.watchSource(), this.watchId.trim(), this.watchFilterByGoals),
      () => {
        this.watchId = '';
      },
    );
  }

  sync(connectionId: number): void {
    this.busy.set(true);
    this.error.set(null);
    this.jobs.sync(connectionId).subscribe({
      next: (result) => {
        this.busy.set(false);
        // "Found 12, added 0" is the normal outcome of a repeat sync, and saying so
        // stops it reading as a failure.
        this.syncNote.set(
          result.error ??
            `Found ${result.found} posting(s), added ${result.added} new` +
              (result.skipped > 0
                ? `, skipped ${result.skipped} that did not match your target roles.`
                : '.'),
        );
        this.jobs.reload();
      },
      error: (error: unknown) => {
        this.busy.set(false);
        this.error.set(messageFor(error));
      },
    });
  }

  /**
   * Build a CV for one posting.
   *
   * Held per posting rather than globally so opening a second one replaces the first
   * — two documents on screen with no label saying which posting each is for is how
   * someone sends the wrong one.
   */
  tailorFor(postingId: number): void {
    this.tailoring.set(postingId);
    this.tailored.set(null);
    this.letter.set(null);
    this.copied.set(false);
    this.jobs.tailor(postingId).subscribe({
      next: (cv) => {
        this.tailoring.set(null);
        this.tailored.set({ id: postingId, cv, error: null });
      },
      error: (error: unknown) => {
        this.tailoring.set(null);
        this.tailored.set({ id: postingId, cv: null, error: messageFor(error) });
      },
    });
  }

  /**
   * Save the file the API built.
   *
   * The filename comes from the server's `Content-Disposition` rather than being
   * rebuilt here: it is sanitised there, and two places composing it is two places to
   * disagree about which job a downloaded file is for.
   */
  download(postingId: number, format: 'docx' | 'pdf'): void {
    this.downloading.set(format);
    this.error.set(null);
    const request =
      format === 'docx' ? this.jobs.tailorDocx(postingId) : this.jobs.tailorPdf(postingId);
    request.subscribe({
      next: (response) => {
        this.downloading.set(null);
        const blob = response.body;
        if (!blob) {
          this.error.set('The download came back empty.');
          return;
        }
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filenameFrom(response.headers.get('content-disposition'), format);
        link.click();
        // Without this the blob is held for the lifetime of the document, and a user
        // downloading a CV per posting accumulates every one of them in memory.
        URL.revokeObjectURL(url);
      },
      error: (error: unknown) => {
        this.downloading.set(null);
        this.error.set(messageFor(error));
      },
    });
  }

  draftLetter(postingId: number): void {
    this.lettering.set(true);
    this.error.set(null);
    this.jobs.coverLetter(postingId).subscribe({
      next: (draft) => {
        this.lettering.set(false);
        this.letter.set({ id: postingId, draft, error: null });
        this.letterBody.set(draft.body);
      },
      error: (error: unknown) => {
        this.lettering.set(false);
        this.letter.set({ id: postingId, draft: null, error: messageFor(error) });
      },
    });
  }

  keepLetter(postingId: number): void {
    this.lettering.set(true);
    this.error.set(null);
    this.jobs.saveCoverLetter(postingId, this.letterBody()).subscribe({
      next: (draft) => {
        this.lettering.set(false);
        // Re-reads the similarity against what was actually saved, which is the text
        // that would be sent — not the draft the user started from.
        this.letter.set({ id: postingId, draft, error: null });
      },
      error: (error: unknown) => {
        this.lettering.set(false);
        this.error.set(messageFor(error));
      },
    });
  }

  copy(markdown: string): void {
    // Refused on an insecure origin. Failing silently would look like a broken button,
    // and the text is on screen to select by hand anyway.
    void navigator.clipboard
      .writeText(markdown)
      .then(() => this.copied.set(true))
      .catch(() => this.error.set('Could not copy. Select the text above instead.'));
  }

  /** Record an application straight from the posting it is for. */
  markApplied(postingId: number): void {
    this.run(this.applications.record({ job_posting_id: postingId }), () => undefined);
  }

  syncAll(): void {
    this.busy.set(true);
    this.error.set(null);
    this.jobs.syncAll().subscribe({
      next: (results) => {
        this.busy.set(false);
        // Failures are reported per source, so a summary that only counted additions
        // would show "added 0" for a sweep where nothing could be read at all.
        const failed = results.filter((result) => result.error !== null).length;
        const added = results.reduce((total, result) => total + result.added, 0);
        const skipped = results.reduce((total, result) => total + result.skipped, 0);
        this.syncNote.set(
          `Synced ${results.length} source(s), added ${added} new posting(s)` +
            (skipped > 0 ? `, skipped ${skipped} outside your target roles` : '') +
            (failed > 0 ? ` — ${failed} could not be read.` : '.'),
        );
        this.jobs.reload();
      },
      error: (error: unknown) => {
        this.busy.set(false);
        this.error.set(messageFor(error));
      },
    });
  }

  unwatch(connectionId: number): void {
    this.run(this.jobs.unwatch(connectionId), () => undefined);
  }

  remove(entry: ScoredPostingResponse): void {
    this.run(this.jobs.remove(entry.posting.id), () => undefined);
  }

  private run(request: { subscribe: (o: object) => void }, onDone: () => void): void {
    this.busy.set(true);
    this.error.set(null);
    request.subscribe({
      next: () => {
        this.busy.set(false);
        onDone();
        this.jobs.reload();
      },
      error: (error: unknown) => {
        this.busy.set(false);
        this.error.set(messageFor(error));
      },
    });
  }
}

/**
 * The API's own message.
 *
 * It matters more here than on most screens: the refusal for an unsupported link is
 * guidance ("paste it instead"), not a failure, and replacing it with a generic string
 * would leave the user with no idea what to do next.
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
  return 'That did not work.';
}
