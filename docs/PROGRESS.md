# CV Pal — Progress

Current state and what is left. `PLANNING.md` holds the *what and why*;
[CHANGELOG.md](../CHANGELOG.md) records what shipped per release; this file holds the
*state*. Update **Current state** in place — do not only append — and add a short dated
entry under **Log** for anything non-obvious. The session-by-session history up to
2026-09-22 is in git (`git log -p -- docs/PROGRESS.md`).

---

## Current state — 2026-09-22

**Released** as 0.1.0. Self-hosted via `docker compose up` (pulls images from ghcr.io),
or `start-cv-pal.cmd` on Windows. CI runs on GitHub Actions; tagging `v*` publishes
images.

**Quality gate:** backend `uv run nox` → ruff, `mypy --strict`, pytest (377), `alembic
check`. Frontend `npm run lint`, `npm run format:check`, `npm test -- --watch=false`
(59), `npm run build`. Migration head `d7e8f9a0b1c2`.

### Built

| Area | What works |
| --- | --- |
| Accounts | Register, login, refresh with rotation and reuse detection, logout / logout-all. Edit name; change password and delete account (both re-authenticate). Export all data. Offline password reset: `python -m cv_pal.admin reset-password <email>`. |
| Sessions | HttpOnly `SameSite=Strict` cookies for the browser, gated on the `X-CV-Pal-Session` header; bearer tokens for other clients. Revoking all sessions voids live access tokens through a per-account token version. |
| Security | argon2id (bcrypt upgraded on login), NIST password policy, per-client rate limit + per-account lockout, CSP, unprivileged containers, API not published to the host. |
| First run | `/welcome`: explain → upload CV → keep what it read → goals. Shown once, on an empty profile. |
| Career profile | Roles, education, skills — add, amend, delete. Skills cite the roles that evidence them, with suggestions drawn from role descriptions. Import from an uploaded CV (deterministic, proposes only). Summary drafted by the model from profile facts (proposes only; refuses an empty profile). |
| Goals | Target roles, work regime, salary floor, work locations — each a non-negotiable or a preference. |
| Documents | Upload (PDF/DOCX, magic-byte checked), list, delete with file cleanup. |
| CV analysis | ATS parseability and keyword coverage against a pasted posting. No model needed. |
| AI review | Model-backed suggestions, accept or dismiss. Warns up front when the model is unavailable (`GET /health/llm`). |
| Job search | Paste a posting, import a Greenhouse / Lever / Remotive link, watch boards and sync them (one call syncs all — cron-friendly). Scored against goals, with the reason stated. |
| Tailoring | Tailored CV (surface, and substitute within the alias map) as Markdown / DOCX / PDF. Cover-letter draft with a self-similarity warning. |
| Applications | Five statuses, reply rate over applications old enough to have been answered, chase list, "saved but not applied". |
| LinkedIn | Import via print-to-PDF, official export ZIP, or paste; section review and consistency check against the profile. |
| Mock mode | `npm run start:mock` — the full UI from fixtures, no backend, no account. |

### Left to do

Roughly in priority order.

1. **Public demo.** Deploy the mock build and link it from the README.
2. **Application quality gate** (PLANNING → *Application quality gate*). Only
   self-similarity exists. Missing: specificity, filler density, stuffing, posting
   specificity, duplicate and cap checks, `POST /applications/{id}/preflight`.
3. **Per-account LLM config** — encrypted keys, per-task model, token and cost
   accounting. Currently per deployment, in `.env`.
4. Rules, queue and assisted submission (Phase 7) — only once the gate exists.
5. **Split `job-search` and `profile` into child components.** Their styles are still
   over the 4 kB budget warning (4.85 kB and 4.62 kB) after shared rules moved to
   `styles.css`; what remains is genuinely page-specific.
6. Smaller: transform 3 (rephrase, needs a model), per-change diff and approval, JSON
   Resume import/export, projects and certifications, structured logging with request
   IDs, storage behind an interface, `docs/architecture.md`, PWA (Tier 2).

### Known limitations

- **Vocabulary is software-only.** The alias map is software-engineering terms, so
  transform 2 (substitute) must stay disabled outside it — guessing synonyms is
  fabrication. The fix is ESCO / O\*NET.
- **SQLite does not enforce foreign keys.** Cascades happen through ORM relationships,
  which is why collections are eager-loaded before an account delete. `ondelete` in the
  schema is documentation here, not behaviour.
- **The rate limiter is in-process**, so its limit multiplies with the worker count.

### Gotchas

- The Angular CLI needs Node ≥ 24.15 (or 22.22.3+, or 26+).
- `uv run nox` installs unpinned dependencies, CI installs the lockfile. Newer `openai`
  / `anthropic` releases type against their own `httpx` fork, so test fakes built from
  plain `httpx` objects need a `cast(Any, …)` to pass under both.
- Importing anything from a lazy component into eager code (e.g. a constant from
  `WelcomeComponent` into `LayoutComponent`) silently un-lazies the route. Shared
  constants live in `core/`.
- Component styles are scoped, but anything in `styles.css` is not: moving a rule there
  is only safe where every copy was identical, or the local variants override every
  declaration of the shared one.
- Mock fixtures must not be prettier than reality — fixtures with evidenced skills hid
  for weeks that the real product had no way to evidence one.
- FastAPI matches routes in order: `/jobs/sources/sync` must be declared before
  `/jobs/sources/{id}/sync`. Same in the mock backend.
- On a machine that already runs Ollama, point the backend at the host
  (`http://host.docker.internal:11434/v1`) instead of using the `ollama` profile — the
  container is CPU-only on Windows and downloads every model again.

---

## Log

### 2026-09-22 — Audit, session hardening, doc clean-up

- **Sessions moved to HttpOnly cookies.** The container build is same-origin, so the
  `localStorage` trade-off no longer had a reason behind it. The frontend keeps only a
  `cv-pal.signed-in` flag, and clears the old token keys on load. The session header
  doubles as the CSRF defence — a cookie without it does not authenticate.
- **Access tokens die with the session.** `users.token_version` (migration
  `d7e8f9a0b1c2`) is carried as `ver` in every access token and bumped whenever all
  sessions are revoked. Deploying it signs everyone out once: older tokens have no
  `ver`.
- **Model availability is checked.** Logged at start-up (in the background, never
  blocking), served at `GET /health/llm`, and shown as a notice on AI Tools.
- **`python-jose` → `PyJWT`** (jose is unmaintained with open CVEs). `httpx` moved to
  runtime dependencies — the job-board code imports it, and it had only worked because
  `openai` pulls it in.
- **CV version numbers could repeat** after a delete (`count + 1`); now `max + 1`.
- **The LLM client was built per request**, each with a never-closed connection pool;
  now cached for the process.
- **The `production` frontend build pointed at `https://api.cvpal.app`**, a hosted
  service that does not exist. `production` is now the same-origin build; `beta` and
  `selfhost` are gone.
- **nginx cached `public/` files as immutable for a year**, though they are not
  fingerprinted. Now only the hashed `.js` / `.css` are.
- **Shared CSS moved to `styles.css`** (`.primary`, `.page`, `.intro`, `.card-note`,
  `.upload`, `.remove:hover`) — only where copies were identical or fully overridden.
  A LinkedIn button and three card-header notes that had those classes but no rule are
  now styled like everywhere else.
- **Removed:** unused images (`cv_pal_logo.webp`, `icon-192/512`, maskable icon,
  `favicon-48`), `docs/manual-test-plan.md` (written for session 31, claimed Docker had
  never run), `docs/open-source-guide.md` (maintainer notes, not project docs — in git
  history). This file cut from ~3,000 lines to current state; PLANNING from ~1,500 to
  decisions and roadmap.

Verified: `uv run nox` green. Frontend lint, format check, 59 tests, `ng build` and
`ng build --configuration=mock` green. Not visually checked in a browser, and the
container images were not rebuilt.
