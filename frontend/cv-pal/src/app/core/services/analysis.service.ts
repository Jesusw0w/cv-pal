import { HttpClient, httpResource } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  CoverageResponse,
  CvResponse,
  ParseabilityResponse,
} from '../../shared/models/api.model';
import { AuthService } from './auth.service';

/** Matches the API's own upload rules, so a doomed upload is refused before it is sent. */
export const ALLOWED_CV_EXTENSIONS = ['.pdf', '.docx'] as const;
export const MAX_CV_BYTES = 10 * 1024 * 1024;

/** The API rejects a shorter posting than this, so the button stays disabled until then. */
export const MIN_JOB_DESCRIPTION_LENGTH = 20;

/**
 * The deterministic analysis: parseability and keyword coverage.
 *
 * Both endpoints run with **no language model configured** — they are plain Python over
 * the extracted text. That is why this screen is the first one worth using: it works on
 * a fresh install with no API key and no Ollama.
 */
@Injectable({ providedIn: 'root' })
export class AnalysisService {
  private readonly http = inject(HttpClient);
  private readonly auth = inject(AuthService);

  /** The user's uploaded CVs. Idle while signed out; reloads after an upload or delete. */
  private readonly cvs = httpResource<CvResponse[]>(
    () => (this.auth.isAuthenticated() ? `${environment.apiUrl}/cvs/` : undefined),
    { defaultValue: [] },
  );

  readonly documents = this.cvs.value;
  readonly isLoading = this.cvs.isLoading;
  readonly error = this.cvs.error;

  reload(): void {
    this.cvs.reload();
  }

  upload(file: File): Observable<CvResponse> {
    const body = new FormData();
    body.append('file', file);
    // Trailing slash: the API's collection route is `/cvs/`, and FastAPI would answer a
    // slashless POST with a redirect that drops the multipart body.
    return this.http.post<CvResponse>(`${environment.apiUrl}/cvs/`, body);
  }

  delete(cvId: number): Observable<void> {
    return this.http.delete<void>(`${environment.apiUrl}/cvs/${cvId}`);
  }

  checkParseability(cvId: number): Observable<ParseabilityResponse> {
    return this.http.post<ParseabilityResponse>(
      `${environment.apiUrl}/analysis/cvs/${cvId}/ats-check`,
      null,
    );
  }

  checkCoverage(cvId: number, jobDescription: string): Observable<CoverageResponse> {
    return this.http.post<CoverageResponse>(
      `${environment.apiUrl}/analysis/cvs/${cvId}/coverage`,
      { job_description: jobDescription },
    );
  }
}

/**
 * Why an upload cannot be accepted, or null when it can.
 *
 * Checked client-side purely to give an instant answer — the API enforces the same rules
 * and is the one that actually matters.
 */
export function rejectUpload(file: File): string | null {
  const extension = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();
  if (!ALLOWED_CV_EXTENSIONS.includes(extension as (typeof ALLOWED_CV_EXTENSIONS)[number])) {
    return `Only ${ALLOWED_CV_EXTENSIONS.join(' and ')} files can be analysed.`;
  }
  if (file.size > MAX_CV_BYTES) {
    return 'That file is over the 10 MB limit.';
  }
  return null;
}
