import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { SESSION_HEADER, authInterceptor } from './auth';
import { AuthService } from './services/auth.service';

describe('authInterceptor', () => {
  let http: HttpClient;
  let backend: HttpTestingController;
  let auth: AuthService;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        // The interceptor sends a dead session to /login, so the route has to exist here.
        provideRouter([{ path: 'login', children: [] }]),
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    http = TestBed.inject(HttpClient);
    backend = TestBed.inject(HttpTestingController);
    auth = TestBed.inject(AuthService);

    auth.login('dev@cvpal.test', 'a-long-enough-password').subscribe();
    backend
      .expectOne((request) => request.url.endsWith('/auth/login'))
      .flush({ access_token: null, refresh_token: null, token_type: 'cookie' });
  });

  afterEach(() => backend.verify());

  it('sends the session cookie and header, never a bearer token', () => {
    http.get('/profile').subscribe();

    const request = backend.expectOne('/profile');
    expect(request.request.withCredentials).toBe(true);
    expect(request.request.headers.get(SESSION_HEADER)).toBe('cookie');
    expect(request.request.headers.has('Authorization')).toBe(false);
    request.flush({ id: 1 });
  });

  it('refreshes once on a 401 and replays the original request', () => {
    let body: unknown = null;
    http.get('/profile').subscribe((response) => (body = response));

    backend
      .expectOne('/profile')
      .flush({ detail: 'Not authenticated' }, { status: 401, statusText: 'Unauthorized' });
    backend
      .expectOne((request) => request.url.endsWith('/auth/refresh'))
      .flush({ access_token: null, refresh_token: null, token_type: 'cookie' });

    // The new cookie is the browser's business; the replay only has to happen.
    backend.expectOne('/profile').flush({ id: 1 });

    expect(body).toEqual({ id: 1 });
  });

  it('ends the session when the refresh itself is rejected', () => {
    http.get('/profile').subscribe({ error: () => undefined });

    backend
      .expectOne('/profile')
      .flush({ detail: 'Not authenticated' }, { status: 401, statusText: 'Unauthorized' });
    backend
      .expectOne((request) => request.url.endsWith('/auth/refresh'))
      .flush({ detail: 'Invalid refresh token' }, { status: 401, statusText: 'Unauthorized' });

    // A reused or expired refresh token means the backend has revoked every session,
    // so holding on to the local one would only produce more failing requests.
    expect(auth.isAuthenticated()).toBe(false);
  });

  it('does not refresh on a failed login', () => {
    http.post('/auth/login', null).subscribe({ error: () => undefined });

    // It still carries the session header — that is what makes login set cookies.
    const request = backend.expectOne('/auth/login');
    expect(request.request.headers.get(SESSION_HEADER)).toBe('cookie');
    request.flush({ detail: 'Invalid credentials' }, { status: 401, statusText: 'Unauthorized' });
  });
});
