import { HttpClient, httpResource } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { LlmStatusResponse, SuggestionResponse } from '../../shared/models/api.model';

/**
 * AI CV review: the one part of the product that needs a language model.
 *
 * Everything else — parseability, keyword coverage, extraction, match scoring — is
 * deterministic and works with no model configured. This does not, and the screen says
 * so rather than failing mysteriously on an install with no provider set up.
 */
@Injectable({ providedIn: 'root' })
export class ReviewService {
  private readonly http = inject(HttpClient);

  /** Asked up front, so a missing model is a notice rather than a failed review. */
  readonly modelStatus = httpResource<LlmStatusResponse>(() => `${environment.apiUrl}/health/llm`);

  suggestionsFor(cvId: number): Observable<SuggestionResponse[]> {
    return this.http.get<SuggestionResponse[]>(
      `${environment.apiUrl}/reviews/cvs/${cvId}/suggestions`,
    );
  }

  analyse(cvId: number): Observable<SuggestionResponse[]> {
    return this.http.post<SuggestionResponse[]>(
      `${environment.apiUrl}/reviews/cvs/${cvId}/analyze`,
      null,
    );
  }

  /**
   * Record the user's decision on one suggestion.
   *
   * Accepting does **not** rewrite the CV — it marks the suggestion as something the
   * user agreed with. Nothing this product generates edits a document behind the user's
   * back.
   */
  decide(suggestionId: number, accepted: boolean): Observable<SuggestionResponse> {
    return this.http.patch<SuggestionResponse>(
      `${environment.apiUrl}/reviews/suggestions/${suggestionId}`,
      { accepted },
    );
  }
}
