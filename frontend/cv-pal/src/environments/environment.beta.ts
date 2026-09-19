import { Environment } from './environment.model';

export const environment: Environment = {
  production: false,
  apiUrl: 'https://beta-api.cvpal.app/api',
  appName: 'CV Pal (Beta)',
  useMocks: false,
  mockLatencyMs: 0,
  mockErrorRate: 0,
};
