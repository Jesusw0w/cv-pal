import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { authInterceptor } from './auth';
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
      .flush({ access_token: 'access-1', refresh_token: 'refresh-1', token_type: 'bearer' });
  });

  afterEach(() => backend.verify());

  it('refreshes once on a 401 and replays the original request with the new token', () => {
    let body: unknown = null;
    http.get('/profile').subscribe((response) => (body = response));

    const first = backend.expectOne('/profile');
    expect(first.request.headers.get('Authorization')).toBe('Bearer access-1');
    first.flush({ detail: 'Not authenticated' }, { status: 401, statusText: 'Unauthorized' });

    backend
      .expectOne((request) => request.url.endsWith('/auth/refresh'))
      .flush({ access_token: 'access-2', refresh_token: 'refresh-2', token_type: 'bearer' });

    // The retry must carry the *new* token; replaying with the expired one loops.
    const retry = backend.expectOne('/profile');
    expect(retry.request.headers.get('Authorization')).toBe('Bearer access-2');
    retry.flush({ id: 1 });

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

  it('leaves the auth endpoints alone so a failed login cannot trigger a refresh', () => {
    http.post('/auth/login', null).subscribe({ error: () => undefined });

    const request = backend.expectOne('/auth/login');
    expect(request.request.headers.has('Authorization')).toBe(false);
    request.flush({ detail: 'Invalid credentials' }, { status: 401, statusText: 'Unauthorized' });
  });
});
