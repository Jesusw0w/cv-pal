import { Environment } from './environment.model';

export const environment: Environment = {
  production: false,
  apiUrl: 'http://localhost:8000',
  appName: 'CV Pal (Dev)',
  useMocks: false,
  mockLatencyMs: 0,
  mockErrorRate: 0,
};
