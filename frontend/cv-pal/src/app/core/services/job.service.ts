import { HttpClient, HttpResponse, httpResource } from '@angular/common/http';
import { Injectable, computed, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  JobBoardConnectionResponse,
  JobPostingCreate,
  JobPostingResponse,
  JobSource,
  CoverLetterDraftResponse,
  ScoredPostingResponse,
  SyncResultResponse,
  TailoredCvResponse,
} from '../../shared/models/api.model';
import { AuthService } from './auth.service';

/**
 * Saved job postings, each with its match score.
 *
 * Scores come from the API and are recomputed on every read, so editing the profile or
 * the goals changes them immediately — they are deterministic and cheap, with no model
 * involved, which is what makes recomputing per request affordable.
 */
@Injectable({ providedIn: 'root' })
export class JobService {
  private readonly http = inject(HttpClient);
  private readonly auth = inject(AuthService);

  private readonly resource = httpResource<ScoredPostingResponse[]>(
    () => (this.auth.isAuthenticated() ? `${environment.apiUrl}/jobs` : undefined),
    { defaultValue: [] },
  );

  readonly all = this.resource.value;
  readonly isLoading = this.resource.isLoading;
  readonly error = this.resource.error;

  /**
   * Postings that survived the user's non-negotiables, best score first.
   *
   * Blocked postings are kept out of the ranking rather than sorted to the bottom: a
   * non-negotiable is a filter, and mixing the two makes the ordering meaningless.
   */
  readonly matches = computed(() => rankMatches(this.all()));

  /** Kept separate but still shown — a hidden filter is one the user cannot revisit. */
  readonly blocked = computed(() => blockedOf(this.all()));

  private readonly sourcesResource = httpResource<JobBoardConnectionResponse[]>(
    () => (this.auth.isAuthenticated() ? `${environment.apiUrl}/jobs/sources` : undefined),
    { defaultValue: [] },
  );

  readonly sources = this.sourcesResource.value;

  reload(): void {
    this.resource.reload();
    this.sourcesResource.reload();
  }

  watchBoard(
    source: JobSource,
    identifier: string,
    filterByGoals = false,
  ): Observable<JobBoardConnectionResponse> {
    return this.http.post<JobBoardConnectionResponse>(`${environment.apiUrl}/jobs/sources`, {
      source,
      identifier,
      filter_by_goals: filterByGoals,
    });
  }

  /**
   * Fetch a watched board and save whatever is new.
   *
   * Idempotent by content hash, so this is also what a cron entry calls — running it
   * twice adds nothing the second time.
   */
  sync(connectionId: number): Observable<SyncResultResponse> {
    return this.http.post<SyncResultResponse>(
      `${environment.apiUrl}/jobs/sources/${connectionId}/sync`,
      null,
    );
  }

  /** Every watched source in one call — the same endpoint a scheduler would hit. */
  syncAll(): Observable<SyncResultResponse[]> {
    return this.http.post<SyncResultResponse[]>(`${environment.apiUrl}/jobs/sources/sync`, null);
  }

  unwatch(connectionId: number): Observable<void> {
    return this.http.delete<void>(`${environment.apiUrl}/jobs/sources/${connectionId}`);
  }

  paste(payload: JobPostingCreate): Observable<JobPostingResponse> {
    return this.http.post<JobPostingResponse>(`${environment.apiUrl}/jobs/paste`, payload);
  }

  /** Only Remotive, Greenhouse and Lever links resolve; anything else the API refuses. */
  importUrl(url: string): Observable<JobPostingResponse> {
    return this.http.post<JobPostingResponse>(`${environment.apiUrl}/jobs/import-url`, {
      url,
    });
  }

  /**
   * Download the tailored CV as a `.docx` — the format an ATS actually ingests.
   *
   * A blob rather than JSON, and the filename comes from the server's
   * `Content-Disposition` so the browser and the API cannot disagree about it.
   */
  tailorDocx(postingId: number): Observable<HttpResponse<Blob>> {
    return this.tailorFile(postingId, 'docx');
  }

  /**
   * The same document as a PDF.
   *
   * Prefer the `.docx` where a portal takes either: it is structured data a parser
   * reads directly, where a PDF is a page description it has to reconstruct.
   */
  tailorPdf(postingId: number): Observable<HttpResponse<Blob>> {
    return this.tailorFile(postingId, 'pdf');
  }

  private tailorFile(postingId: number, format: 'docx' | 'pdf'): Observable<HttpResponse<Blob>> {
    return this.http.post(`${environment.apiUrl}/jobs/${postingId}/tailor/${format}`, null, {
      observe: 'response',
      responseType: 'blob',
    });
  }

  /** Assemble a cover letter draft, with its similarity to the user's kept letters. */
  coverLetter(postingId: number): Observable<CoverLetterDraftResponse> {
    return this.http.post<CoverLetterDraftResponse>(
      `${environment.apiUrl}/jobs/${postingId}/cover-letter`,
      null,
    );
  }

  /** Keep a letter, which is what puts it into the corpus similarity is measured against. */
  saveCoverLetter(postingId: number, body: string): Observable<CoverLetterDraftResponse> {
    return this.http.put<CoverLetterDraftResponse>(
      `${environment.apiUrl}/jobs/${postingId}/cover-letter`,
      { body },
    );
  }

  remove(id: number): Observable<void> {
    return this.http.delete<void>(`${environment.apiUrl}/jobs/${id}`);
  }

  /**
   * Render the career profile as a CV aimed at one posting.
   *
   * Deterministic and model-free, so nothing is stored and nothing is cached here —
   * asking again costs a request and always answers the same.
   */
  tailor(postingId: number): Observable<TailoredCvResponse> {
    return this.http.post<TailoredCvResponse>(
      `${environment.apiUrl}/jobs/${postingId}/tailor`,
      null,
    );
  }
}

/**
 * Postings that survived the non-negotiables: preferred work arrangement first, then
 * best score.
 *
 * A blocked posting is removed from the ranking rather than sorted to the bottom: a
 * non-negotiable is a filter, and mixing the two makes the ordering meaningless. The
 * arrangement sorts before the score because "remote, then hybrid" means every remote
 * posting above every hybrid one — the same order the API gives an agent.
 */
export function rankMatches(all: ScoredPostingResponse[]): ScoredPostingResponse[] {
  return all
    .filter((entry) => entry.match.blocked_by === null)
    .sort(
      (a, b) => a.match.preference_rank - b.match.preference_rank || b.match.score - a.match.score,
    );
}

/** The postings a non-negotiable ruled out, still shown so the rule can be revisited. */
export function blockedOf(all: ScoredPostingResponse[]): ScoredPostingResponse[] {
  return all.filter((entry) => entry.match.blocked_by !== null);
}
