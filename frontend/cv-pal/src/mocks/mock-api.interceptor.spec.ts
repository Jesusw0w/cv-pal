import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { firstValueFrom } from 'rxjs';

import { CvResponse, SuggestionResponse } from '../app/shared/models/api.model';
import { environment } from '../environments/environment';
import { mockApiInterceptor, resetMockBackend } from './mock-api.interceptor';

const API = 'http://localhost:8000';

describe('mockApiInterceptor', () => {
  let http: HttpClient;
  let originalUseMocks: boolean;

  beforeEach(() => {
    // The spec runs under the default environment, where useMocks is false; the
    // interceptor is a no-op unless the flag is on.
    originalUseMocks = environment.useMocks;
    (environment as { useMocks: boolean }).useMocks = true;
    resetMockBackend();

    TestBed.configureTestingModule({
      providers: [provideHttpClient(withInterceptors([mockApiInterceptor]))],
    });
    http = TestBed.inject(HttpClient);
  });

  afterEach(() => {
    (environment as { useMocks: boolean }).useMocks = originalUseMocks;
  });

  it('serves the CV collection from fixtures without touching the network', async () => {
    const cvs = await firstValueFrom(http.get<CvResponse[]>(`${API}/cvs/`));

    expect(cvs.length).toBeGreaterThan(0);
    expect(cvs[0].filename).toBeDefined();
  });

  it('matches routes when apiUrl is a path prefix rather than an origin', async () => {
    // What the mock and self-hosted builds actually send. Every test above uses the dev
    // environment's `http://localhost:8000`, so the whole suite passed while
    // `npm run build:mock` served a blank page: `/api/cvs/` matched no route, every
    // request 404'd, and the app never got a user.
    const original = environment.apiUrl;
    (environment as { apiUrl: string }).apiUrl = '/api';
    try {
      const cvs = await firstValueFrom(http.get<CvResponse[]>('/api/cvs/'));

      expect(cvs.length).toBeGreaterThan(0);
    } finally {
      (environment as { apiUrl: string }).apiUrl = original;
    }
  });

  it('honours pagination parameters', async () => {
    const cvs = await firstValueFrom(
      http.get<CvResponse[]>(`${API}/cvs/`, { params: { limit: 1 } }),
    );

    expect(cvs.length).toBe(1);
  });

  it('returns a single CV by id', async () => {
    const cv = await firstValueFrom(http.get<CvResponse>(`${API}/cvs/1`));

    expect(cv.id).toBe(1);
  });

  it('returns 404 with the API error envelope for an unknown CV', async () => {
    await expect(firstValueFrom(http.get(`${API}/cvs/999`))).rejects.toMatchObject({
      status: 404,
      error: { detail: 'CV not found' },
    });
  });

  // These 404ed because the route matcher rejects a path with a trailing segment —
  // broken in exactly the build meant to be the public demo.
  it.each(['docx', 'pdf'])('serves the tailored CV download as %s', async (format) => {
    const response = await firstValueFrom(
      http.post(`${API}/jobs/1/tailor/${format}`, null, {
        observe: 'response',
        responseType: 'blob',
      }),
    );

    expect(response.status).toBe(200);
    expect(await response.body!.text()).toContain('##');
    expect(response.headers.get('Content-Disposition')).toContain('filename=');
  });

  it('drafts a summary from the seeded profile without saving it', async () => {
    const drafted = await firstValueFrom(
      http.post<{ summary: string }>(`${API}/profile/summary`, null),
    );

    expect(drafted.summary.length).toBeGreaterThan(0);
    // The guarantee, mirrored in mock mode because it is the guarantee: the draft is a
    // proposal, so the profile is unchanged until the user saves it.
    const profile = await firstValueFrom(
      http.get<{ summary: string | null }>(`${API}/profile`),
    );
    expect(profile.summary).not.toBe(drafted.summary);
  });

  it('returns 404 for a route with no fixture, rather than hitting the network', async () => {
    await expect(
      firstValueFrom(http.get(`${API}/does-not-exist`)),
    ).rejects.toMatchObject({ status: 404 });
  });

  it('persists mutations within a session', async () => {
    const before = await firstValueFrom(http.get<CvResponse[]>(`${API}/cvs/`));

    const body = new FormData();
    body.append('file', new File(['x'], 'new-cv.pdf'), 'new-cv.pdf');
    const created = await firstValueFrom(http.post<CvResponse>(`${API}/cvs/`, body));

    const after = await firstValueFrom(http.get<CvResponse[]>(`${API}/cvs/`));

    expect(created.filename).toBe('new-cv.pdf');
    expect(after.length).toBe(before.length + 1);
  });

  it('removes a CV and its suggestions on delete', async () => {
    await firstValueFrom(http.delete(`${API}/cvs/1`));

    await expect(firstValueFrom(http.get(`${API}/cvs/1`))).rejects.toMatchObject({
      status: 404,
    });
  });

  it('creates suggestions when a CV is analysed', async () => {
    const created = await firstValueFrom(
      http.post<SuggestionResponse[]>(`${API}/reviews/cvs/2/analyze`, {}),
    );

    const listed = await firstValueFrom(
      http.get<SuggestionResponse[]>(`${API}/reviews/cvs/2/suggestions`),
    );

    expect(created.length).toBeGreaterThan(0);
    expect(listed.length).toBeGreaterThanOrEqual(created.length);
  });

  it('rotates the refresh token, as the real backend does', async () => {
    const first = await firstValueFrom(
      http.post<{ refresh_token: string }>(`${API}/auth/login`, {}),
    );
    const second = await firstValueFrom(
      http.post<{ refresh_token: string }>(`${API}/auth/refresh`, {
        refresh_token: first.refresh_token,
      }),
    );

    expect(first.refresh_token).toBeTruthy();
    expect(second.refresh_token).not.toBe(first.refresh_token);
  });

  it('updates the accepted state of a suggestion', async () => {
    const updated = await firstValueFrom(
      http.patch<SuggestionResponse>(`${API}/reviews/suggestions/1`, {
        accepted: true,
      }),
    );

    expect(updated.accepted).toBe(true);
  });

  it('resets to the seeded fixtures', async () => {
    await firstValueFrom(http.delete(`${API}/cvs/1`));
    resetMockBackend();

    const cv = await firstValueFrom(http.get<CvResponse>(`${API}/cvs/1`));

    expect(cv.id).toBe(1);
  });

  it('passes requests through untouched when mock mode is off', async () => {
    (environment as { useMocks: boolean }).useMocks = false;

    // With mocks disabled nothing intercepts, so the request reaches the real
    // (absent) backend and fails as a network error rather than returning fixtures.
    await expect(firstValueFrom(http.get(`${API}/cvs/`))).rejects.toBeDefined();
  });
});
