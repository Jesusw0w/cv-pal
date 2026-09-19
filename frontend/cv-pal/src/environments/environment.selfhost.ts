import { Environment } from './environment.model';

/**
 * The self-hosted container build.
 *
 * `apiUrl` is a same-origin path because nginx reverse-proxies `/api/` to the backend.
 * One origin means no CORS configuration for the user to get wrong, and it leaves the
 * door open to moving tokens into `HttpOnly` cookies later.
 */
export const environment: Environment = {
  production: true,
  apiUrl: '/api',
  appName: 'CV Pal',
  useMocks: false,
  mockLatencyMs: 0,
  mockErrorRate: 0,
};
