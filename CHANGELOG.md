# Changelog

Notable changes to CV Pal, in [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
form. Versions follow [semantic versioning](https://semver.org/spec/v2.0.0.html).

This file is the summary. Current state and what is left are in
[docs/PROGRESS.md](docs/PROGRESS.md); the reasoning behind decisions is in
[docs/PLANNING.md](docs/PLANNING.md).

## [Unreleased]

### Security

- **Browser sessions use HttpOnly cookies.** Tokens are no longer kept in
  `localStorage`, where a cross-site scripting flaw could read them. A cookie only
  authenticates alongside the app's session header, which a cross-site form cannot
  send. Set `CV_PAL_COOKIE_SECURE=true` when serving over HTTPS. Everyone is signed out
  once by the upgrade.
- **Changing your password or signing out everywhere ends sessions at once.** Access
  tokens used to keep working for up to 30 minutes afterwards.
- `python-jose`, unmaintained with open advisories, replaced by `PyJWT`.

### Fixed

- A new CV could be given the version number of one that still existed, after an
  earlier one was deleted.
- The production frontend build pointed at a hosted API that does not exist; it now
  talks to its own origin, as the container build always did.
- A changed logo or favicon could stay cached in returning browsers for a year.
- A LinkedIn button and three card-header notes were missing their styles.

- **Mock mode rendered a blank page.** `apiUrl` is a path prefix (`/api`) in the mock
  and self-hosted builds, but the mock router only stripped an origin, so every request
  404'd and the app never loaded a user. The whole frontend suite passed throughout,
  because every test used the dev environment's `http://localhost:8000` form.
- A crash in the topbar when it read the route title during construction, before the
  deepest route had a snapshot — the second reason `npm run start:mock` showed nothing.
- **The mobile menu backdrop could not be dismissed from the keyboard.** It was a `div`
  with a click handler; it is now a labelled button, hidden from the tab order while the
  menu is closed. Found by the new frontend linter.
- The sidebar's `close` output shadowed the native DOM `close` event, and is now
  `closed`.

### Added

- **The app checks whether its model is usable.** A missing or unreachable model is
  logged at start-up and explained on the AI Tools screen, instead of first appearing
  as a failed review. `GET /health/llm` reports it.

- **The frontend has a linter.** `angular-eslint` with the recommended TypeScript,
  Angular and template-accessibility rules, wired to `npm run lint` and enforced in CI.
  Prettier was configured but nothing ran it, so 52 files had drifted; `npm run format`
  applies it and `npm run format:check` gates it. The backend already had the equivalent
  through `nox`.

### Changed

- `docker compose up` now pulls published images from `ghcr.io` instead of building
  locally, so a first start is a download rather than a ten-minute Angular and Python
  build. Building from source moved to an explicit overlay,
  `docker-compose.build.yml`. Pin a version with `CV_PAL_VERSION` in `.env`.

## [0.1.0] — 2026-09-19

First public release. Early, and the [README](README.md#status) is explicit about what
is not built.

### Added

- **The app checks whether its model is usable.** A missing or unreachable model is
  logged at start-up and explained on the AI Tools screen, instead of first appearing
  as a failed review. `GET /health/llm` reports it.

- **Accounts** — registration (closable via `CV_PAL_ALLOW_REGISTRATION`), sign-in,
  password change, and account deletion that removes the profile, CVs and uploaded
  files with it. Sessions use short-lived JWTs plus single-use opaque refresh tokens.
- **Guided first run** — upload a CV, confirm what was read correctly, then state what
  you are looking for. The drafted summary is shown for approval before it is kept.
- **Career profile** — roles, education and skills, each editable and removable, with
  skills citable to the roles that evidence them. Importable wholesale from a CV.
- **Career goals** — target roles, work regime, salary floor, and which of those are
  non-negotiable.
- **CVs** — upload, list and delete, with uploads validated by magic bytes and stored
  under server-generated names.
- **Analysis** — ATS parseability and keyword coverage, both computed rather than
  generated, so they need no model and give the same answer twice.
- **AI CV review** — suggestions accepted or rejected individually.
- **Job postings** — paste one, import a Greenhouse, Lever or Remotive link, or watch a
  board and sync it on demand.
- **Match scoring** against your goals, with the reason stated for every score.
- **Tailored CV generation** and cover-letter drafts, every line grounded in something
  already in your profile, exportable to DOCX and PDF. Letters are checked against your
  own recent ones so they cannot all be the same letter.
- **LinkedIn import** — print-to-PDF, the official data export, or paste, each reviewed
  section by section before anything is kept.
- **Models** — OpenAI, Anthropic, Ollama or any OpenAI-compatible endpoint, chosen per
  deployment. `CV_PAL_LOCAL_ONLY=true` refuses to contact a hosted provider at all,
  checked against the base URL as well as the provider name.
- **Self-hosting** — `docker compose up`, with the UI and API on one origin behind
  nginx, bound to `127.0.0.1` by default. `start-cv-pal.cmd` does the same on Windows
  from a double-click.

### Security

- Passwords hashed with argon2id; legacy bcrypt hashes upgraded on next login.
- Password screening per NIST SP 800-63B: 12-character minimum, common-password
  blocklist, and rejection of passwords derived from the user's own email.
- Login rate limited per client with per-account exponential backoff, counted for any
  submitted address so lockout cannot enumerate accounts.
- Ownership enforced inside the query, so another user's record is indistinguishable
  from one that does not exist.
- No default secret key: an unconfigured instance refuses to start.

Known limitations are listed in [SECURITY.md](SECURITY.md#known-limitations).
