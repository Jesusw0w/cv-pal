# CV Pal

**Keep your CV competitive against AI screening — without letting it invent your career.**
Keep a structured record of your career, check any CV against a real posting for ATS
parseability and keyword coverage, and — as the phases land — generate versions tailored
to the postings worth applying for. Runs entirely on your own machine if you want it to.

<!-- TODO before publishing: screenshot or short recording of the documents view here.
     Nothing establishes faster that the project is real. -->

<!-- TODO: link the deployed mock build once it is hosted.
## Try it
[Live demo](#) — no account, no backend, nothing stored. -->

## Two guarantees

- **It never invents experience.** Every line it writes is grounded in something you
  entered. Where a role wants something you do not have, it says so as a *gap* rather
  than quietly adding it. You should never have to defend a claim this tool made up.
- **It automates the tedium, not the judgement.** The tools in this space advertise
  50–100 automated applications a day. This one will not do that, because *applications
  sent* is the number you can watch move, not the one you want. Applications go out
  against rules you set, from goals you stated, only above a match score you choose,
  capped per day and per company, tailored to each posting, and written to a log you can
  read. **Nothing is sent without you seeing it first** — review mode is on by default,
  and turning it off is per source, takes a typed confirmation, and switches itself back
  on whenever your CV, profile or rules change.

## Run it yourself

**Windows:** clone the repository and double-click **`start-cv-pal.cmd`**. It starts
Docker Desktop if it is not already running, generates the secret key on first run,
checks your local model, and opens the app when it is ready.

**Any platform:**

```bash
git clone <this repository> && cd cv-pal
cp .env.docker.example .env          # then set CV_PAL_SECRET_KEY
docker compose --profile ollama up -d
```

Open <http://localhost:8080>. That pulls prebuilt images from ghcr.io rather than
building; to build from the working tree instead, add
`-f docker-compose.yml -f docker-compose.build.yml`. Full walkthrough, including
backups and troubleshooting: **[docs/self-hosting.md](docs/self-hosting.md)**.

Already running Ollama on the machine? Drop the `--profile ollama` and set
`CV_PAL_LLM_BASE_URL=http://host.docker.internal:11434/v1` — it uses your GPU and the
models you have already pulled, instead of downloading them again into a container.

Just want to look at the UI? No backend needed:

```bash
cd frontend/cv-pal && npm install && npm run start:mock
```

## Why local-first

Your CV is one of the most sensitive documents you own: employment history, contact
details, often your address and date of birth. CV Pal is **software you run**, not a
service someone else hosts — there is no account on anyone else's server.

You choose the model that powers the AI parts: a local one via
[Ollama](https://ollama.com), so nothing leaves your machine, or a hosted provider with
your own key. Set `CV_PAL_LOCAL_ONLY=true` and it will refuse to contact a hosted
provider at all.

By default the app listens only on `127.0.0.1` — your machine, not your network.

## Status

Early, and honest about it.

| Works | Not built yet |
| --- | --- |
| Accounts, sign-in, sessions with refresh and revocation | The application quality gate — the checks that have to pass before anything is sent |
| A guided first run: upload a CV, keep what it read correctly, then say what you are looking for | Changing your name after registration — it is asked once and cannot be edited |
| A summary drafted from the facts already in your profile, which you read before keeping | Match rules, an application queue, and automated submission |
| Career profile: roles, education and skills — add, amend or remove any of them, cite the roles that evidence a skill, or import the lot from a CV | Application tracking and reply-rate analytics |
| Career goals: target roles, work regime, salary floor, and which of those are non-negotiable | Per-account model configuration — it is per deployment, in `.env` |
| CV upload, listing, deletion | Scheduled collection: syncing a board is a command you run, or a cron entry |
| ATS parseability check and keyword coverage, with no model needed | Projects, certifications, and JSON Resume import |
| AI CV review with accept/reject suggestions | A skill vocabulary beyond software roles — see [PLANNING](docs/PLANNING.md#known-limitation-the-vocabulary-is-software-specific) |
| Job postings: paste one, import a Greenhouse / Lever / Remotive link, or watch a board and sync it | Exporting your data from the interface — it is in one volume you can back up, but there is no button yet |
| Changing your password, and deleting the account outright — profile, CVs, files and all | |
| Match scoring against your goals, with the reason for every score | |
| Tailored CV generation and DOCX / PDF export, every line grounded in your profile | |
| Cover-letter drafts, checked against your own recent letters so they cannot all be the same one | |
| LinkedIn import — print-to-PDF, the official export, or paste — with a section-by-section review | |
| Local or hosted models, per deployment | |

Session-by-session detail: [docs/PROGRESS.md](docs/PROGRESS.md).

## Architecture at a glance

```
frontend/cv-pal   Angular 22. One HTTP boundary, which mock mode intercepts —
                  the same seam that will allow a serverless build later.
        │  /api   (nginx proxies to the backend, so it is all one origin)
        ▼
backend/cv_pal
  routers/        HTTP edge: validation and response shaping only
  services/       business logic — framework-free, unit-testable
  analysis/       the deterministic core: keywords, parseability, matching, similarity
  generation/     tailored CV and letter assembly; Markdown, DOCX and PDF renderers
  integrations/   job boards, behind one Protocol
  llm.py          provider-agnostic model client (OpenAI, Anthropic, Ollama, compatible)
  models.py       SQLAlchemy 2.0        schemas.py   Pydantic v2
  alembic/        migrations own the schema; never create_all()
```

Deterministic first: keyword coverage, parseability, skill overlap and scoring are
*computed*. The model is used for judgement and phrasing only — which keeps results
reproducible, cheap, and testable.

Design decisions and reasoning: **[docs/PLANNING.md](docs/PLANNING.md)**.

## Documentation

| | |
| --- | --- |
| [Self-hosting](docs/self-hosting.md) | Run it, no development tools needed |
| [Development](docs/development.md) | Set up, run the tests, add a migration |
| [Planning](docs/PLANNING.md) | Product plan, architecture, decisions |
| [Changelog](CHANGELOG.md) | What shipped, per release |
| [Progress](docs/PROGRESS.md) | The session-by-session account behind it |
| [Security](SECURITY.md) | Reporting, and what the software actually does |
| [Open source guide](docs/open-source-guide.md) | Branch protection, reviewing external PRs, going public |

## Contributing

Welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). The quality gate is `uv run nox`
(ruff, `mypy --strict`, pytest, and a migration check) plus the frontend tests, and CI
runs the same commands.

## Licence

[MIT](LICENSE).
