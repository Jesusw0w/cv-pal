import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { AuthService } from './auth.service';

describe('AuthService', () => {
  let service: AuthService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(AuthService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('spends a refresh token once even when several requests refresh at the same time', () => {
    service.login('dev@cvpal.test', 'a-long-enough-password').subscribe();
    http
      .expectOne((request) => request.url.endsWith('/auth/login'))
      .flush({
        access_token: 'access-1',
        refresh_token: 'refresh-1',
        token_type: 'bearer',
      });

    const seen: string[] = [];
    service.refresh().subscribe((tokens) => seen.push(tokens.access_token));
    service.refresh().subscribe((tokens) => seen.push(tokens.access_token));

    // One call, not two. Refresh tokens are single-use and presenting one twice revokes
    // every session for the user — so a second in-flight refresh would sign them out.
    const refreshes = http.match((request) => request.url.endsWith('/auth/refresh'));
    expect(refreshes.length).toBe(1);

    refreshes[0].flush({
      access_token: 'access-2',
      refresh_token: 'refresh-2',
      token_type: 'bearer',
    });

    expect(seen).toEqual(['access-2', 'access-2']);
    expect(service.accessToken()).toBe('access-2');
  });

  it('refreshes again after the previous refresh has settled', () => {
    service.login('dev@cvpal.test', 'a-long-enough-password').subscribe();
    http
      .expectOne((request) => request.url.endsWith('/auth/login'))
      .flush({
        access_token: 'access-1',
        refresh_token: 'refresh-1',
        token_type: 'bearer',
      });

    service.refresh().subscribe();
    http
      .expectOne((request) => request.url.endsWith('/auth/refresh'))
      .flush({
        access_token: 'access-2',
        refresh_token: 'refresh-2',
        token_type: 'bearer',
      });

    // The shared observable must be released on completion, or the session can never
    // be refreshed a second time and the user is logged out after 30 minutes.
    service.refresh().subscribe();
    const second = http.expectOne((request) => request.url.endsWith('/auth/refresh'));
    expect(second.request.body).toEqual({ refresh_token: 'refresh-2' });
    second.flush({ access_token: 'access-3', refresh_token: 'refresh-3', token_type: 'bearer' });
  });

  it('clears the session locally even if the server is unreachable on logout', () => {
    service.login('dev@cvpal.test', 'a-long-enough-password').subscribe();
    http
      .expectOne((request) => request.url.endsWith('/auth/login'))
      .flush({
        access_token: 'access-1',
        refresh_token: 'refresh-1',
        token_type: 'bearer',
      });

    service.logout();
    http
      .expectOne((request) => request.url.endsWith('/auth/logout'))
      .error(new ProgressEvent('offline'));

    expect(service.isAuthenticated()).toBe(false);
    expect(service.hasRefreshToken()).toBe(false);
  });
});
