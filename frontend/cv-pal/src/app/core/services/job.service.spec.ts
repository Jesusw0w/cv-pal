import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { AuthService } from './auth.service';
import { JobService, blockedOf, rankMatches } from './job.service';

const scored = (id: number, score: number, blocked: string | null = null) => ({
  posting: {
    id,
    source: 'manual' as const,
    source_url: null,
    title: `Role ${id}`,
    company: 'Acme',
    location: null,
    description: '',
    employment_type: null,
    created_at: '2026-07-26T09:00:00Z',
  },
  match: { score, blocked_by: blocked, reasons: [], missing_required: [] },
});

describe('JobService', () => {
  let service: JobService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(JobService);
    http = TestBed.inject(HttpTestingController);

    TestBed.inject(AuthService).login('dev@cvpal.test', 'a-long-enough-password').subscribe();
    http
      .expectOne((r) => r.url.endsWith('/auth/login'))
      .flush({ access_token: 'a', refresh_token: 'b', token_type: 'bearer' });
    TestBed.tick();
    for (const request of http.match((r) => r.url.endsWith('/users/me'))) {
      request.flush({ id: 1, email: 'dev@cvpal.test', full_name: null, is_active: true, created_at: '' });
    }
  });

  afterEach(() => {
    // Both the postings and the watched-boards resources fire on sign-in; this spec is
    // about the calls the service makes on demand.
    for (const pending of http.match((r) => r.url.includes('/jobs'))) {
      pending.flush([]);
    }
    http.verify();
  });

  it('posts a pasted posting to the paste route', () => {
    service.paste({ title: 'Engineer', description: 'x'.repeat(60) }).subscribe();

    const request = http.expectOne((r) => r.url.endsWith('/jobs/paste'));
    expect(request.request.method).toBe('POST');
    request.flush({});
  });

  it('sends a link to the import route rather than fetching it in the browser', () => {
    service.importUrl('https://boards.greenhouse.io/acme/jobs/1').subscribe();

    const request = http.expectOne((r) => r.url.endsWith('/jobs/import-url'));
    expect(request.request.body).toEqual({
      url: 'https://boards.greenhouse.io/acme/jobs/1',
    });
    request.flush({});
  });
});

describe('ranking', () => {
  it('orders by score and keeps blocked postings out of the ranking', () => {
    // A non-negotiable is a filter, not a low score. Sorting a blocked posting to the
    // bottom of the same list would make the ordering meaningless.
    const all = [scored(1, 40), scored(2, 0, 'You ruled this out.'), scored(3, 80)];

    expect(rankMatches(all).map((e) => e.posting.id)).toEqual([3, 1]);
    expect(blockedOf(all).map((e) => e.posting.id)).toEqual([2]);
  });
});
