import { Environment } from './environment.model';

/**
 * UI development without a backend: no API, no database, no LLM, no network.
 * Run with `npm run start:mock`.
 */
export const environment: Environment = {
  production: false,
  apiUrl: '/api',
  appName: 'CV Pal (Mock)',
  useMocks: true,
  mockLatencyMs: 300,
  mockErrorRate: 0,
};
