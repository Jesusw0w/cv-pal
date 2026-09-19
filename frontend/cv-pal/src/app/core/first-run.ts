/**
 * Whether an account has been through, or left, the first-run flow.
 *
 * Keyed by user id rather than kept as one flag for the browser. A single flag meant
 * the second account created on a shared machine never saw the first run at all: the
 * first account had already set it, and the check could not tell the two apart.
 *
 * Its own module because importing it from `WelcomeComponent` pulls the whole wizard
 * into the eager bundle — which is what the lazy route exists to avoid.
 */
const PREFIX = 'cv-pal.welcomed';

/** The pre-account key, from before this was per user. Cleared on sight. */
const LEGACY_KEY = PREFIX;

function keyFor(userId: number): string {
  return `${PREFIX}.${userId}`;
}

export function hasSeenWelcome(userId: number): boolean {
  return localStorage.getItem(keyFor(userId)) !== null;
}

export function markWelcomeSeen(userId: number): void {
  // The old flag would keep every future account on this browser out of the first run.
  localStorage.removeItem(LEGACY_KEY);
  localStorage.setItem(keyFor(userId), '1');
}

/** Forget the flag, so setup runs again. Used by account deletion and by re-running it. */
export function forgetWelcome(userId: number): void {
  localStorage.removeItem(keyFor(userId));
}
