import { HttpErrorResponse } from '@angular/common/http';
import { Component, effect, inject, signal, untracked } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';

import { CareerProfileService } from '../../core/services/career-profile.service';
import {
  EducationCreate,
  EducationResponse,
  EvidenceSuggestionResponse,
  ExperienceResponse,
  SkillResponse,
} from '../../shared/models/api.model';
import { ImportPanelComponent } from './import-panel.component';

@Component({
  selector: 'app-profile',
  imports: [DatePipe, FormsModule, ImportPanelComponent],
  template: `
    <div class="page">
      <!-- Without this a failed request is indistinguishable from an empty profile,
           which is the one wrong message to send about someone's career history. -->
      @if (career.error()) {
        <p class="card notice" role="alert">
          Could not load your profile.
          <button type="button" class="retry" (click)="career.reload()">Try again</button>
        </p>
      } @else if (career.isLoading()) {
        <p class="card notice">Loading your profile…</p>
      }

      <header class="card identity">
        @if (editing()) {
          <form class="identity-main edit-form" (ngSubmit)="saveProfile()">
            <label
              >Headline
              <input
                name="headline"
                [(ngModel)]="draft.headline"
                placeholder="Senior Backend Engineer"
              />
            </label>
            <label
              >Location
              <input name="location" [(ngModel)]="draft.location" placeholder="Porto, Portugal" />
            </label>
            <label
              >Phone
              <input
                name="phone"
                type="tel"
                [(ngModel)]="draft.phone"
                placeholder="+351 912 345 678"
              />
            </label>
            <label
              >Summary
              <textarea name="summary" rows="3" [(ngModel)]="draft.summary"></textarea>
            </label>
            <label
              >LinkedIn
              <input
                name="linkedin"
                [(ngModel)]="draft.linkedin_url"
                placeholder="linkedin.com/in/you"
              />
            </label>
            <label
              >Website
              <input name="website" [(ngModel)]="draft.website_url" placeholder="github.com/you" />
            </label>
            @if (saveError(); as message) {
              <p class="error" role="alert">{{ message }}</p>
            }
            <div class="form-actions">
              <button type="submit" class="primary" [disabled]="saving()">
                {{ saving() ? 'Saving…' : 'Save' }}
              </button>
              <button type="button" class="link" (click)="editing.set(false)">Cancel</button>
            </div>
          </form>
        } @else {
          <div class="identity-main">
            <h1>{{ career.profile().headline ?? 'Add a headline' }}</h1>
            <p class="identity-meta">
              {{ career.profile().location ?? 'Location not set' }}
              &middot; {{ career.experiences().length }} roles &middot;
              {{ career.profile().skills.length }} skills
            </p>
            @if (career.profile().summary; as summary) {
              <p class="identity-summary">{{ summary }}</p>
            }
            <button type="button" class="link edit-link" (click)="startEditing()">
              Edit details
            </button>
          </div>
        }

        <div class="readiness">
          <span class="readiness-value">{{ career.completeness() }}<small>%</small></span>
          <span class="readiness-label">ready to tailor</span>
          <div
            class="readiness-bar"
            role="progressbar"
            [attr.aria-valuenow]="career.completeness()"
            aria-valuemin="0"
            aria-valuemax="100"
            aria-label="Profile readiness"
          >
            <div class="readiness-fill" [style.width.%]="career.completeness()"></div>
          </div>
        </div>
      </header>

      <!-- Tasks, not a count. Everything downstream is blocked on these. -->
      @if (career.gaps().length > 0) {
        <section class="card gaps" aria-label="What this profile still needs">
          <div class="card-header">
            <h3>Before a CV can be tailored from this</h3>
          </div>
          <ul class="gap-list">
            @for (gap of career.gaps(); track gap.label) {
              <li class="gap">
                <span class="gap-label">{{ gap.label }}</span>
                <span class="gap-detail">{{ gap.detail }}</span>
              </li>
            }
          </ul>
        </section>
      }

      <app-import-panel (added)="career.reload()" />

      <section class="card">
        <div class="card-header">
          <h3>Experience</h3>
          <button type="button" class="card-link" (click)="addingRole.set(!addingRole())">
            {{ addingRole() ? 'Cancel' : 'Add a role' }}
          </button>
        </div>

        @if (addingRole()) {
          <form class="add-form" (ngSubmit)="addRole()">
            <div class="add-row">
              <label
                >Employer<input name="org" [(ngModel)]="roleDraft.organisation" required
              /></label>
              <label>Title<input name="title" [(ngModel)]="roleDraft.title" required /></label>
            </div>
            <div class="add-row">
              <label
                >Started<input name="start" type="date" [(ngModel)]="roleDraft.start_date" required
              /></label>
              <label>Ended<input name="end" type="date" [(ngModel)]="roleDraft.end_date" /></label>
              <label>Location<input name="loc" [(ngModel)]="roleDraft.location" /></label>
            </div>
            <label
              >What you did<textarea
                name="desc"
                rows="2"
                [(ngModel)]="roleDraft.description"
              ></textarea>
            </label>
            <p class="add-note">Leave <em>Ended</em> empty for a role you are still in.</p>
            <button type="submit" class="primary" [disabled]="busy()">Add role</button>
          </form>
        }
        <ol class="timeline">
          @for (role of career.experiences(); track role.id) {
            <li class="entry">
              @if (editingRole() === role.id) {
                <form class="add-form inline-edit" (ngSubmit)="saveRole(role.id)">
                  <div class="add-row">
                    <label
                      >Employer<input name="org" [(ngModel)]="roleEdit.organisation" required
                    /></label>
                    <label>Title<input name="title" [(ngModel)]="roleEdit.title" required /></label>
                  </div>
                  <div class="add-row">
                    <label
                      >Started<input
                        name="start"
                        type="date"
                        [(ngModel)]="roleEdit.start_date"
                        required
                    /></label>
                    <label
                      >Ended<input name="end" type="date" [(ngModel)]="roleEdit.end_date"
                    /></label>
                    <label>Location<input name="loc" [(ngModel)]="roleEdit.location" /></label>
                  </div>
                  <label
                    >What you did<textarea
                      name="desc"
                      rows="2"
                      [(ngModel)]="roleEdit.description"
                    ></textarea>
                  </label>
                  <div class="form-actions">
                    <button type="submit" class="primary" [disabled]="busy()">Save</button>
                    <button type="button" class="link" (click)="editingRole.set(null)">
                      Cancel
                    </button>
                  </div>
                </form>
              } @else {
                <div class="entry-head">
                  <span class="entry-title">{{ role.title }}</span>
                  @if (role.is_current) {
                    <span class="badge badge-green">Current</span>
                  }
                  <button
                    type="button"
                    class="edit"
                    [attr.aria-label]="'Edit ' + role.title"
                    (click)="startRoleEdit(role)"
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    class="remove"
                    [attr.aria-label]="'Remove ' + role.title"
                    (click)="removeRole(role.id)"
                  >
                    Remove
                  </button>
                </div>
                <span class="entry-org">{{ role.organisation }}</span>
                <span class="entry-dates">
                  {{ role.start_date | date: 'MMM y' }} &ndash;
                  {{ role.end_date ? (role.end_date | date: 'MMM y') : 'present' }}
                  @if (role.location) {
                    &middot; {{ role.location }}
                  }
                </span>
                @if (role.description) {
                  <p class="entry-body">{{ role.description }}</p>
                }
              }
            </li>
          } @empty {
            <li class="entry empty">No roles yet. Nothing can be tailored without them.</li>
          }
        </ol>
      </section>

      <section class="card">
        <div class="card-header">
          <h3>Skills</h3>
          <form class="inline-add" (ngSubmit)="addSkill()">
            <input
              name="skill"
              [(ngModel)]="skillDraft"
              placeholder="Add a skill"
              aria-label="Skill name"
            />
            <button type="submit" class="link" [disabled]="busy() || !skillDraft.trim()">
              Add
            </button>
          </form>
          <span class="card-note">
            {{ career.ungroundedSkills().length }} of {{ career.profile().skills.length }}
            unevidenced
          </span>
        </div>
        <!-- The citations are usually already in the descriptions. Offering them beats
             asking the user to re-read their own CV twenty times. -->
        @if (suggestions().length > 0) {
          <div class="suggested">
            <div class="suggested-head">
              <p class="add-note">
                {{ suggestions().length }} skill(s) are named in roles you have already described.
                Applying a suggestion cites those roles as evidence.
              </p>
              <button type="button" class="link" [disabled]="busy()" (click)="applyAllEvidence()">
                Apply all
              </button>
            </div>
            @for (suggestion of suggestions(); track suggestion.skill_id) {
              <div class="suggested-row">
                <span class="suggested-skill">{{ suggestion.skill_name }}</span>
                <span class="suggested-roles">{{ suggestion.experience_labels.join(' · ') }}</span>
                <button
                  type="button"
                  class="cite"
                  [disabled]="busy()"
                  (click)="applyEvidence(suggestion)"
                >
                  Apply
                </button>
              </div>
            }
          </div>
        }

        <div class="skill-groups">
          @for (group of career.skillsByCategory(); track group.category) {
            <div class="skill-group">
              <h4>{{ group.category }}</h4>
              <ul class="skill-list">
                @for (skill of group.skills; track skill.id) {
                  <li class="skill" [class.unevidenced]="!skill.is_evidenced">
                    <span class="skill-name">{{ skill.name }}</span>
                    @if (skill.years) {
                      <span class="skill-years">{{ skill.years }}y</span>
                    }
                    <button
                      type="button"
                      class="cite"
                      [attr.aria-expanded]="evidencing() === skill.id"
                      [attr.aria-label]="'Cite roles for ' + skill.name"
                      (click)="toggleEvidencing(skill.id)"
                    >
                      @if (skill.is_evidenced) {
                        {{ skill.evidence_experience_ids.length }} role{{
                          skill.evidence_experience_ids.length > 1 ? 's' : ''
                        }}
                      } @else {
                        <span class="badge badge-amber">cite a role</span>
                      }
                    </button>
                    <button
                      type="button"
                      class="remove"
                      [attr.aria-label]="'Remove ' + skill.name"
                      (click)="removeSkill(skill.id)"
                    >
                      &times;
                    </button>
                  </li>

                  @if (evidencing() === skill.id) {
                    <li class="evidence-picker">
                      @if (career.experiences().length === 0) {
                        <p class="add-note">
                          Add a role first — evidence is a role that shows you used this.
                        </p>
                      } @else {
                        <p class="add-note">
                          Which roles did you use {{ skill.name }} in? A generated CV only claims
                          skills with a role behind them.
                        </p>
                        @for (role of career.experiences(); track role.id) {
                          <label class="cite-row">
                            <input
                              type="checkbox"
                              [checked]="skill.evidence_experience_ids.includes(role.id)"
                              [disabled]="busy()"
                              (change)="toggleEvidence(skill, role.id)"
                            />
                            <span>{{ role.title }} &middot; {{ role.organisation }}</span>
                          </label>
                        }
                      }
                    </li>
                  }
                }
              </ul>
            </div>
          }
        </div>
      </section>

      <section class="card">
        <div class="card-header">
          <h3>Education</h3>
          <button type="button" class="card-link" (click)="addingCourse.set(!addingCourse())">
            {{ addingCourse() ? 'Cancel' : 'Add a qualification' }}
          </button>
        </div>

        @if (addingCourse()) {
          <form class="add-form" (ngSubmit)="addCourse()">
            <div class="add-row">
              <label
                >Institution<input name="inst" [(ngModel)]="courseDraft.institution" required
              /></label>
              <label
                >Qualification<input name="qual" [(ngModel)]="courseDraft.qualification" required
              /></label>
            </div>
            <div class="add-row">
              <label>Field<input name="field" [(ngModel)]="courseDraft.field_of_study" /></label>
              <label
                >Started<input name="cstart" type="date" [(ngModel)]="courseDraft.start_date"
              /></label>
              <label
                >Ended<input name="cend" type="date" [(ngModel)]="courseDraft.end_date"
              /></label>
            </div>
            <button type="submit" class="primary" [disabled]="busy()">Add qualification</button>
          </form>
        }

        <ol class="timeline">
          @for (course of career.educations(); track course.id) {
            <li class="entry">
              @if (editingCourse() === course.id) {
                <form class="add-form inline-edit" (ngSubmit)="saveCourse(course.id)">
                  <div class="add-row">
                    <label
                      >Institution<input name="inst" [(ngModel)]="courseEdit.institution" required
                    /></label>
                    <label
                      >Qualification<input
                        name="qual"
                        [(ngModel)]="courseEdit.qualification"
                        required
                    /></label>
                  </div>
                  <div class="add-row">
                    <label
                      >Field<input name="field" [(ngModel)]="courseEdit.field_of_study"
                    /></label>
                    <label
                      >Started<input name="cstart" type="date" [(ngModel)]="courseEdit.start_date"
                    /></label>
                    <label
                      >Ended<input name="cend" type="date" [(ngModel)]="courseEdit.end_date"
                    /></label>
                  </div>
                  <div class="form-actions">
                    <button type="submit" class="primary" [disabled]="busy()">Save</button>
                    <button type="button" class="link" (click)="editingCourse.set(null)">
                      Cancel
                    </button>
                  </div>
                </form>
              } @else {
                <div class="entry-head">
                  <span class="entry-title"
                    >{{ course.qualification }}
                    @if (course.field_of_study) {
                      &mdash; {{ course.field_of_study }}
                    }
                  </span>
                  <button
                    type="button"
                    class="edit"
                    [attr.aria-label]="'Edit ' + course.qualification"
                    (click)="startCourseEdit(course)"
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    class="remove"
                    [attr.aria-label]="'Remove ' + course.qualification"
                    (click)="removeCourse(course.id)"
                  >
                    Remove
                  </button>
                </div>
                <span class="entry-org">{{ course.institution }}</span>
                <span class="entry-dates">
                  {{ course.start_date ? (course.start_date | date: 'y') : '?' }} &ndash;
                  {{ course.end_date ? (course.end_date | date: 'y') : 'present' }}
                  @if (course.grade) {
                    &middot; {{ course.grade }}
                  }
                </span>
              }
            </li>
          } @empty {
            <li class="entry empty">No education recorded.</li>
          }
        </ol>
      </section>
    </div>
  `,
  styles: [
    `
      /* .card, .card-header and .badge come from styles.css. Only layout here. */
      .page {
        padding: 28px;
        display: flex;
        flex-direction: column;
        gap: 20px;
      }

      .identity {
        display: flex;
        gap: 24px;
        justify-content: space-between;
        padding: 24px;
      }
      .identity h1 {
        font-size: 22px;
        line-height: 1.25;
        margin: 0 0 4px;
      }
      .identity-meta {
        margin: 0;
        font-size: 13px;
        color: var(--text-tertiary);
      }
      .identity-summary {
        margin: 12px 0 0;
        font-size: 14px;
        color: var(--text-secondary);
        max-width: 70ch;
      }

      .readiness {
        display: flex;
        flex-direction: column;
        align-items: flex-end;
        min-width: 140px;
      }
      .readiness-value {
        font-size: 28px;
        font-weight: 700;
        line-height: 1;
      }
      .readiness-value small {
        font-size: 14px;
        font-weight: 500;
        color: var(--text-tertiary);
      }
      .readiness-label {
        font-size: 12px;
        color: var(--text-tertiary);
      }
      .readiness-bar {
        width: 100%;
        height: 6px;
        margin-top: 10px;
        border-radius: 999px;
        background: var(--border-light);
        overflow: hidden;
      }
      .readiness-fill {
        height: 100%;
        background: var(--accent);
      }

      .edit-form,
      .add-form {
        display: flex;
        flex-direction: column;
        gap: 10px;
        flex: 1;
      }
      .add-form {
        padding: 12px 18px;
        border-bottom: 1px solid var(--border-light);
      }
      .add-row {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
      }
      .add-row label {
        flex: 1 1 160px;
      }
      .edit-form label,
      .add-form label {
        display: flex;
        flex-direction: column;
        gap: 4px;
        font-size: 12px;
        color: var(--text-tertiary);
      }
      .edit-form input,
      .edit-form textarea,
      .add-form input,
      .add-form textarea,
      .inline-add input {
        padding: 8px 10px;
        border: 1px solid var(--border-light);
        border-radius: var(--radius);
        background: var(--bg-primary);
        color: var(--text-primary);
        font-size: 13px;
        font-family: inherit;
      }
      .add-note {
        margin: 0;
        font-size: 12px;
        color: var(--text-tertiary);
      }
      .form-actions {
        display: flex;
        align-items: center;
        gap: 12px;
      }
      .primary {
        align-self: flex-start;
        padding: 8px 16px;
        border-radius: var(--radius);
        background: var(--accent);
        color: #fff;
        font-size: 13px;
        font-weight: 600;
      }
      .link {
        font-size: 13px;
        font-weight: 600;
        color: var(--accent);
      }
      .edit-link {
        align-self: flex-start;
        margin-top: 10px;
      }
      .error {
        margin: 0;
        font-size: 13px;
        color: var(--danger, #dc2626);
      }

      .inline-add {
        display: flex;
        gap: 6px;
        align-items: center;
      }
      .inline-add input {
        font-size: 12px;
        padding: 4px 8px;
        width: 130px;
      }

      .remove {
        margin-left: auto;
        font-size: 12px;
        color: var(--text-tertiary);
        padding: 2px 6px;
      }

      .notice {
        margin: 0;
        padding: 14px 18px;
        font-size: 13px;
        color: var(--text-secondary);
      }
      .retry {
        margin-left: 8px;
        color: var(--accent);
        font-weight: 600;
      }

      .gap-list {
        list-style: none;
        margin: 0;
        padding: 8px;
      }
      .gap {
        display: flex;
        flex-direction: column;
        gap: 2px;
        padding: 10px 12px;
        border-radius: var(--radius);
      }
      .gap:hover {
        background: var(--bg-hover);
      }
      .gap-label {
        font-size: 14px;
        font-weight: 600;
      }
      .gap-detail {
        font-size: 12px;
        color: var(--text-tertiary);
      }

      .timeline {
        list-style: none;
        margin: 0;
        padding: 8px;
      }
      .entry {
        display: flex;
        flex-direction: column;
        gap: 2px;
        padding: 12px;
        border-radius: var(--radius);
      }
      .entry + .entry {
        border-top: 1px solid var(--border-light);
      }
      .entry-head {
        display: flex;
        align-items: center;
        gap: 8px;
      }
      .entry-title {
        font-size: 14px;
        font-weight: 600;
      }
      .entry-org {
        font-size: 13px;
        color: var(--accent);
      }
      .entry-dates {
        font-size: 12px;
        color: var(--text-tertiary);
      }
      .entry-body {
        margin: 6px 0 0;
        font-size: 13px;
        color: var(--text-secondary);
        max-width: 80ch;
      }
      .empty {
        color: var(--text-tertiary);
        font-size: 13px;
      }

      .suggested {
        margin: 0 18px 4px;
        padding: 10px 12px;
        border: 1px solid var(--border-light);
        border-left: 2px solid var(--accent);
        border-radius: var(--radius);
      }
      .suggested-head {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: 12px;
      }
      .suggested-head .add-note {
        margin: 0;
      }
      .suggested-row {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 6px 0;
        border-top: 1px solid var(--border-light);
      }
      .suggested-skill {
        font-size: 13px;
        font-weight: 600;
      }
      .suggested-roles {
        flex: 1;
        min-width: 0;
        font-size: 12px;
        color: var(--text-tertiary);
      }

      .skill-groups {
        padding: 12px;
        display: grid;
        gap: 16px;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      }
      .skill-group h4 {
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--text-tertiary);
        margin: 0 0 8px;
      }
      .skill-list {
        list-style: none;
        margin: 0;
        padding: 0;
        display: flex;
        flex-direction: column;
        gap: 6px;
      }
      .skill {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 14px;
      }
      .skill.unevidenced .skill-name {
        color: var(--text-secondary);
      }
      .skill-years {
        font-size: 12px;
        color: var(--text-tertiary);
      }

      .cite {
        margin-left: auto;
        font-size: 12px;
        color: var(--text-tertiary);
      }
      .cite:hover {
        color: var(--accent);
      }
      .evidence-picker {
        margin: 2px 0 8px;
        padding: 10px 12px;
        border: 1px solid var(--border-light);
        border-radius: var(--radius);
        background: var(--bg-hover);
      }
      .cite-row {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 4px 0;
        font-size: 13px;
        color: var(--text-secondary);
        cursor: pointer;
      }
      .cite-row input {
        accent-color: var(--accent);
      }
      .edit {
        font-size: 12px;
        color: var(--text-tertiary);
      }
      .edit:hover {
        color: var(--accent);
      }
      .inline-edit {
        padding: 4px 0 12px;
        border: 0;
      }

      @media (max-width: 768px) {
        .identity {
          flex-direction: column;
          gap: 16px;
        }
        .readiness {
          align-items: flex-start;
        }
      }
    `,
  ],
})
export class ProfileComponent {
  career = inject(CareerProfileService);

  readonly editing = signal(false);
  readonly addingRole = signal(false);
  readonly addingCourse = signal(false);
  readonly editingRole = signal<number | null>(null);
  readonly editingCourse = signal<number | null>(null);
  readonly evidencing = signal<number | null>(null);
  readonly saving = signal(false);
  readonly busy = signal(false);
  readonly saveError = signal<string | null>(null);

  /** Citations the roles' own descriptions already support. Refreshed after each write. */
  readonly suggestions = signal<EvidenceSuggestionResponse[]>([]);

  constructor() {
    // Once the profile has both skills and roles there is something to compare; before
    // that the endpoint can only answer "nothing", so it is not worth asking.
    effect(() => {
      const profile = this.career.profile();
      if (profile.skills.length > 0 && profile.experiences.length > 0) {
        untracked(() => this.loadSuggestions());
      }
    });
  }

  draft = {
    headline: '',
    location: '',
    phone: '',
    summary: '',
    linkedin_url: '',
    website_url: '',
  };
  roleDraft = emptyRole();
  roleEdit = emptyRole();
  courseDraft = emptyCourse();
  courseEdit = emptyCourse();
  skillDraft = '';

  startEditing(): void {
    const profile = this.career.profile();
    this.draft = {
      headline: profile.headline ?? '',
      location: profile.location ?? '',
      phone: profile.phone ?? '',
      summary: profile.summary ?? '',
      linkedin_url: profile.linkedin_url ?? '',
      website_url: profile.website_url ?? '',
    };
    this.saveError.set(null);
    this.editing.set(true);
  }

  saveProfile(): void {
    this.saving.set(true);
    this.saveError.set(null);
    // Empty means cleared, not unchanged — PATCH takes null to clear a field, and an
    // empty string would store a blank headline that reads as set but shows nothing.
    this.career
      .updateProfile({
        headline: this.draft.headline.trim() || null,
        location: this.draft.location.trim() || null,
        phone: this.draft.phone.trim() || null,
        summary: this.draft.summary.trim() || null,
        linkedin_url: this.draft.linkedin_url.trim() || null,
        website_url: this.draft.website_url.trim() || null,
      })
      .subscribe({
        next: () => {
          this.saving.set(false);
          this.editing.set(false);
          this.career.reload();
        },
        error: (error: unknown) => {
          this.saving.set(false);
          this.saveError.set(detailOf(error, 'Could not save those details.'));
        },
      });
  }

  addRole(): void {
    const draft = this.roleDraft;
    if (!draft.organisation.trim() || !draft.title.trim() || !draft.start_date) {
      return;
    }
    this.run(
      this.career.addExperience({
        organisation: draft.organisation.trim(),
        title: draft.title.trim(),
        location: draft.location.trim() || null,
        start_date: draft.start_date,
        end_date: draft.end_date || null,
        description: draft.description.trim() || null,
      }),
      () => {
        this.roleDraft = emptyRole();
        this.addingRole.set(false);
      },
    );
  }

  startRoleEdit(role: ExperienceResponse): void {
    this.roleEdit = {
      organisation: role.organisation,
      title: role.title,
      location: role.location ?? '',
      start_date: role.start_date,
      end_date: role.end_date ?? '',
      description: role.description ?? '',
    };
    this.editingRole.set(role.id);
  }

  saveRole(id: number): void {
    const edit = this.roleEdit;
    if (!edit.organisation.trim() || !edit.title.trim() || !edit.start_date) {
      return;
    }
    this.run(
      this.career.updateExperience(id, {
        organisation: edit.organisation.trim(),
        title: edit.title.trim(),
        location: edit.location.trim() || null,
        start_date: edit.start_date,
        end_date: edit.end_date || null,
        description: edit.description.trim() || null,
      }),
      () => this.editingRole.set(null),
    );
  }

  addCourse(): void {
    const draft = this.courseDraft;
    if (!draft.institution.trim() || !draft.qualification.trim()) {
      return;
    }
    this.run(this.career.addEducation(coursePayload(draft)), () => {
      this.courseDraft = emptyCourse();
      this.addingCourse.set(false);
    });
  }

  startCourseEdit(course: EducationResponse): void {
    this.courseEdit = {
      institution: course.institution,
      qualification: course.qualification,
      field_of_study: course.field_of_study ?? '',
      start_date: course.start_date ?? '',
      end_date: course.end_date ?? '',
    };
    this.editingCourse.set(course.id);
  }

  saveCourse(id: number): void {
    const edit = this.courseEdit;
    if (!edit.institution.trim() || !edit.qualification.trim()) {
      return;
    }
    this.run(this.career.updateEducation(id, coursePayload(edit)), () =>
      this.editingCourse.set(null),
    );
  }

  addSkill(): void {
    const name = this.skillDraft.trim();
    if (!name) {
      return;
    }
    this.run(this.career.addSkill({ name }), () => (this.skillDraft = ''));
  }

  toggleEvidencing(skillId: number): void {
    this.evidencing.set(this.evidencing() === skillId ? null : skillId);
  }

  /**
   * Cite or un-cite one role for a skill.
   *
   * The API replaces the whole list, so the new one is computed here from what the
   * skill currently holds.
   */
  toggleEvidence(skill: SkillResponse, experienceId: number): void {
    const cited = skill.evidence_experience_ids;
    const next = cited.includes(experienceId)
      ? cited.filter((id) => id !== experienceId)
      : [...cited, experienceId];
    this.run(this.career.updateSkill(skill.id, { evidence_experience_ids: next }), () => undefined);
  }

  /**
   * Cite the roles a suggestion names, keeping any citation the skill already had.
   *
   * The API replaces the list rather than appending to it, so applying a suggestion
   * has to union it with what is there or it would quietly drop existing evidence.
   */
  applyEvidence(suggestion: EvidenceSuggestionResponse): void {
    const skill = this.career
      .profile()
      .skills.find((candidate) => candidate.id === suggestion.skill_id);
    if (!skill) {
      return;
    }
    const cited = [...new Set([...skill.evidence_experience_ids, ...suggestion.experience_ids])];
    this.run(this.career.updateSkill(skill.id, { evidence_experience_ids: cited }), () =>
      this.loadSuggestions(),
    );
  }

  applyAllEvidence(): void {
    for (const suggestion of this.suggestions()) {
      this.applyEvidence(suggestion);
    }
  }

  /**
   * Refresh the proposals.
   *
   * Failure is silent on purpose: this is an optional convenience layered over a
   * profile that works without it, and an error banner for a suggestion nobody asked
   * for would be worse than simply having none.
   */
  private loadSuggestions(): void {
    this.career.evidenceSuggestions().subscribe({
      next: (found) => this.suggestions.set(found),
      error: () => this.suggestions.set([]),
    });
  }

  removeRole(id: number): void {
    this.run(this.career.deleteExperience(id), () => undefined);
  }

  removeCourse(id: number): void {
    this.run(this.career.deleteEducation(id), () => undefined);
  }

  removeSkill(id: number): void {
    this.run(this.career.deleteSkill(id), () => undefined);
  }

  private run(request: { subscribe: (o: object) => void }, onDone: () => void): void {
    this.busy.set(true);
    this.saveError.set(null);
    request.subscribe({
      next: () => {
        this.busy.set(false);
        onDone();
        this.career.reload();
      },
      error: (error: unknown) => {
        this.busy.set(false);
        this.saveError.set(detailOf(error, 'That did not work.'));
      },
    });
  }
}

function emptyRole() {
  return {
    organisation: '',
    title: '',
    location: '',
    start_date: '',
    end_date: '',
    description: '',
  };
}

function emptyCourse() {
  return {
    institution: '',
    qualification: '',
    field_of_study: '',
    start_date: '',
    end_date: '',
  };
}

function coursePayload(draft: ReturnType<typeof emptyCourse>): EducationCreate {
  return {
    institution: draft.institution.trim(),
    qualification: draft.qualification.trim(),
    field_of_study: draft.field_of_study.trim() || null,
    start_date: draft.start_date || null,
    end_date: draft.end_date || null,
  };
}

/** The API's own message where there is one, so a validation error explains itself. */
function detailOf(error: unknown, fallback: string): string {
  if (error instanceof HttpErrorResponse) {
    const detail = (error.error as { detail?: unknown } | null)?.detail;
    if (typeof detail === 'string') {
      return detail;
    }
  }
  return fallback;
}
