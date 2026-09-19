export interface Environment {
  production: boolean;
  apiUrl: string;
  appName: string;
  /**
   * Serve every HTTP request from local fixtures instead of calling the API.
   * Development only — never enabled in a production build.
   */
  useMocks: boolean;
  /** Artificial delay applied to mock responses, so loading states are exercisable. */
  mockLatencyMs: number;
  /**
   * Fraction of mock requests (0–1) that fail with a 500, so error states are
   * exercisable without breaking the API contract.
   */
  mockErrorRate: number;
}
