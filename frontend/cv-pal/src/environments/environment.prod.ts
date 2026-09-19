import { Environment } from './environment.model';

export const environment: Environment = {
  production: true,
  apiUrl: 'https://api.cvpal.app/api',
  appName: 'CV Pal',
  useMocks: false,
  mockLatencyMs: 0,
  mockErrorRate: 0,
};
