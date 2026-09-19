# Running CV Pal locally

Two apps: a FastAPI backend in `backend/` and an Angular frontend in
`frontend/cv-pal/`. You can run either on its own.

## Prerequisites

| Tool | Version | Needed for |
| --- | --- | --- |
| [uv](https://docs.astral.sh/uv/) | latest | Backend — installs Python 3.14 for you |
| Node + npm | **22.22.3+, 24.15+ or 26+** | Frontend. The Angular CLI refuses to start below this and names the version it wants. |
| [Ollama](https://ollama.com/download) | optional | Local LLM, so no API key is needed |
| Docker Desktop | optional | Running the whole stack the way a self-hoster does — see [self-hosting.md](self-hosting.md) |

---

## Frontend only, no backend

The fastest way to work on UI. Serves everything from local fixtures — no API, no
database, no LLM, no network.

```bash
cd frontend/cv-pal
npm install
npm run start:mock
```

→ <http://localhost:4200>

---

## Full stack

### 1. Backend

```bash
cd backend
uv sync --extra dev              # install deps (creates .venv)
cp .env.example .env             # then set CV_PAL_SECRET_KEY in .env
uv run alembic upgrade head      # create the database schema
uv run uvicorn cv_pal.main:app --reload
```

→ API on <http://localhost:8000>, interactive docs on <http://localhost:8000/docs>

Generate a secret key with:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

`.env.example` ships pointing at a local Ollama server, so no API key is required and
the app boots whether or not Ollama is running. To use a hosted model instead, uncomment
the Claude or OpenAI block in `.env`. Claude goes through Anthropic's own SDK, so
`CV_PAL_LLM_BASE_URL` does not apply to it.

`CV_PAL_LOCAL_ONLY=true` refuses every hosted provider at start-up, Claude included.

### 2. Frontend

In a second terminal:

```bash
cd frontend/cv-pal
npm install
npm start
```

→ <http://localhost:4200>, talking to the backend on port 8000.

---

## Using a local LLM

Only the CV analysis endpoint needs a model. For a fully local setup:

```bash
ollama pull llama3               # matches CV_PAL_LLM_MODEL in .env
ollama serve                     # usually already running
```

Set `CV_PAL_LOCAL_ONLY=true` to make the app refuse to contact any hosted provider —
useful when working with a real CV.

---

## Checks before pushing

```bash
cd backend            && uv run nox              # ruff + mypy --strict + pytest + migrations
cd frontend/cv-pal    && npm run lint && npm run format:check && npm test -- --watch=false && npm run build
```

`nox` runs four sessions (`lint`, `typecheck`, `tests`, `migrations`). Run one with
`uv run nox -s lint`. `uv run nox -s format` applies ruff formatting and safe autofixes.

The frontend splits the same job across two tools: `npm run lint` is ESLint
(`angular-eslint`, including template accessibility rules) and catches mistakes, while
`npm run format` is Prettier and settles layout. They do not overlap — the ESLint config
carries no stylistic rules — so neither needs to know about the other.

The `migrations` session applies every revision to a throwaway database, runs
`alembic check`, and rolls back to base. It is there for the one failure the test suite
cannot see: **the tests build their schema from the models**, so a model changed without
a migration passes them and only breaks against a real database.

---

## Database changes

The schema is owned by Alembic — never created at startup.

```bash
cd backend
uv run alembic revision --autogenerate -m "add jobs table"   # then READ the output
uv run alembic upgrade head
uv run alembic downgrade -1                                  # undo one revision
```

Autogenerate misses renames, type changes and server defaults, so always review the
generated file before applying it.

---

## Build configurations (frontend)

| Command | Environment file | API |
| --- | --- | --- |
| `npm start` | `environment.ts` | `http://localhost:8000` |
| `npm run start:mock` | `environment.mock.ts` | Local fixtures |
| `npm run build` | `environment.prod.ts` | `https://api.cvpal.app` |
| `npm run build:mock` | `environment.mock.ts` | Local fixtures |

Mock mode lives in `frontend/cv-pal/src/mocks/`. Fixtures are in `mocks/fixtures/`,
typed against `shared/models/api.model.ts`, which mirrors the backend response schemas.
An unmapped route returns a 404 and logs a warning, so a missing fixture is obvious
rather than a hanging request. Mock code is excluded from production builds.

**Signing in.** `npm start` talks to the real API, so it now requires an account: the
app redirects to `/login`, which can also register one. The backend must be running and
`CV_PAL_CORS_ORIGINS` must include `http://localhost:4200` — it does in `.env.example`.

`npm run start:mock` needs no account at all: the mock build starts with a session
already established, which is what keeps the public demo signup-free.

> Every screen calls the real API — there is no inline sample data left. Under
> `npm run start:mock` the same screens are served from `src/mocks/`, so the two builds
> look alike but only one of them keeps what you type.

---

## Editor (Zed)

`.zed/` is committed with debug configurations, tasks and project settings.

- **Debug** (`debugger: start`) — FastAPI server, all tests, current test file, current
  file, and Chrome against the dev server. The backend configs run with `cwd` set to
  `backend/`, so `.env` is picked up automatically; no secrets live in `.zed/`.
- **Tasks** (`task: spawn`) — dev servers, `nox` and its individual sessions, tests,
  migrations.

The FastAPI debug config deliberately omits `--reload`: the reloader runs your code in
a child process, so breakpoints in the parent never hit. Use the *backend: dev server*
task when you want reload and don't need to break.

Other editors work fine — none of this is required to run the project.

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| `ValidationError: secret_key Field required` | `CV_PAL_SECRET_KEY` is unset. It has no default on purpose. Set it in `.env`. |
| `llm_api_key is required for provider openai` | Provider is `openai` with no key. Either set `CV_PAL_LLM_API_KEY` or switch to `CV_PAL_LLM_PROVIDER=ollama`. |
| `no such table: users` | Migrations were not applied. Run `uv run alembic upgrade head`. |
| CORS errors in the browser console | Add the frontend origin to `CV_PAL_CORS_ORIGINS` and restart the backend. |
| `502` from the analyse endpoint | The LLM is unreachable. Check Ollama is running, or that the hosted key is valid. |
| `429` from `/auth/login` or `/auth/register` | Rate limit or failed-login backoff. The `Retry-After` header says how long to wait; restarting the server clears it, since the limiter is in-process. |
| `Address already in use` | Something holds 8000 or 4200. `uvicorn --port 8001`, or `ng serve --port 4300`. |
| Tests pass locally but `nox` fails | `nox` builds clean virtualenvs. Your `.venv` may hold a stale dependency — `uv sync --extra dev` to resync. |

---

## Layout

```
backend/
  cv_pal/
    routers/     HTTP edge — thin, validation and response shaping only
    services/    business logic, framework-free and unit-testable
    models.py    SQLAlchemy 2.0
    schemas.py   Pydantic v2 wire contracts
    llm.py       provider-agnostic LLM client
  alembic/       migrations — the source of truth for the schema
  tests/
frontend/cv-pal/
  src/app/       components, services, models
  src/mocks/     mock-mode interceptor and fixtures
  src/environments/
docs/            this folder
```

Conventions and rationale live in [PLANNING.md](PLANNING.md); current state and session
history in [PROGRESS.md](PROGRESS.md).
