# Contributing

Thanks for looking. This is a personal project that is useful to other people, so
contributions are welcome — with the caveat that scope is guarded deliberately (see
*Roadmap → Scope* in [docs/PLANNING.md](docs/PLANNING.md)).

## Getting set up

[docs/development.md](docs/development.md) has prerequisites, the full setup, and a
troubleshooting table. The short version:

```bash
cd frontend/cv-pal && npm install && npm run start:mock   # UI only, no backend
```

## Before you open a pull request

```bash
cd backend         && uv run nox                          # ruff + mypy --strict + pytest + migrations
cd frontend/cv-pal && npm run lint && npm run format:check && npm test -- --watch=false && npm run build
```

Both must be green. CI runs the same commands, so there are no surprises.

`npm run format` applies Prettier, the way `uv run nox -s format` does for the backend.

## What the code expects

The conventions are not negotiable in review, so they are worth knowing up front:

- **Type hints on everything**, and `mypy --strict` passes with no `# type: ignore` in
  first-party code. If strict mode fights you, narrow the escape — a targeted
  `# type: ignore[code]` with a reason, not a blanket one.
- **Google-style docstrings** with `Args:`, `Returns:` and `Raises:`.
- **Constants live in `constants.py`**, typed `Final`, prefixed `DEFAULT_` when they are
  a default value. No magic values in routers or services.
- **Routers stay thin.** Business logic goes in `services/`, which never imports from
  `routers/` and never raises `HTTPException` — it raises domain errors that the edge
  translates.
- **Comment the *why*, not the *what*.** The valuable comment is the one that stops a
  future reader undoing a deliberate decision.
- **Migrations own the schema.** Never `create_all()` outside tests, and always read
  what `--autogenerate` produced before committing it.

## Tests

New behaviour needs a test. Prefer testing the service layer directly — it is
framework-free — and reserve HTTP tests for contracts: status codes, validation
failures, and ownership checks.

Tests must never call a real language model or a real network. The LLM client is
injected and replaced with a fake; the frontend has mock mode for the same reason.

## Commits and pull requests

- One logical change per pull request. A green `nox` and a description of *why* is
  enough — no template to fill in.
- Say what you verified and how. "Tests pass" is less useful than "verified the
  migration upgrades and downgrades against a scratch database".
- If you found a real problem while working on something else, say so rather than
  silently fixing it in the same change.

## Things that will be turned down

- Features that scrape sites prohibiting it, or that submit applications in bulk. See
  the guarantees in the [README](README.md); they are not negotiable.
- Anything that could put invented experience on a user's CV.
- Broad refactors without a stated problem.

## Reporting security issues

Privately, please — see [SECURITY.md](SECURITY.md).
