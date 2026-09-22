# CV Pal — Planning

The stable *what and why*: product position, principles, architecture, and the design
of what is still to build. Current state lives in [PROGRESS.md](PROGRESS.md).

## Context

Job seekers lose time to two things: keeping a CV competitive against AI screening, and
running the search itself — finding relevant roles, tailoring a CV per role, tracking
applications, and keeping a LinkedIn profile aligned with the roles they want.

CV Pal automates that loop. It keeps a structured career profile as the single source of
truth, generates ATS-safe CVs tailored to real postings, finds and scores roles against
the user's own goals, reviews the LinkedIn profile, and tracks every application — with
the user in control of the model that powers the non-deterministic parts, including a
fully local option via Ollama.

## Audience and distribution

1. **The author**, using it for a real job search — the reason correctness beats feature
   count.
2. **Other job seekers**, running it themselves.
3. **Engineers reading the repository** — open source, portfolio work. For them the
   repository *is* the product: README, docs, tests and code shape. Depth over breadth.

**Self-hosted, not a hosted service.** A CV is personal data — in Europe often
special-category data — and hosting other people's makes the operator a data controller.
A hosted service would also pay for everyone's LLM calls. Self-hosting makes local-first
real: with Ollama, a CV never leaves the user's machine. Consequences: container
packaging is a feature, and per-user model configuration ("bring your own key") is the
only sustainable model. A hosted multi-tenant offering is out of scope.

**Public demo.** The mock build is a static bundle with no backend, database or model.
Deployed, it is the zero-cost, zero-data demo the README should lead with.

## Position

### Guarantees

- **Never fabricate experience.** A hallucinated employer or invented skill is something
  the user must defend in an interview. Gaps are reported as gaps.
- **Targeted automation, not spray-and-pray.** Automation is a core feature; untargeted
  volume is not. Every application is driven by the user's own rules, clears a minimum
  match score, is capped per day and per company, is tailored to the posting, and is
  logged. What matters to a recruiter is whether the application was relevant, not
  whether a human pressed the button.

### Why not compete on volume

The category's default product is volume: tools advertising 50–100 automated
applications a day for ~$10/month. Volume sells because **applications sent is the only
number a job seeker can watch move** — interviews are sparse and delayed. A tool
optimising that number optimises what the user can observe, not what they want.

The counter-position is **applications worth the reader's time**, decided against what
the user said they want:

- **Goals are the input**, not the CV alone (principle 8).
- **The claim is measured, not asserted.** Reply rate per CV variant, per source and per
  rule set is the only honest evidence that quality beats volume — evidence about the
  user's own search. If it ever says volume wins for them, the product should say so.
- **No number in the interface celebrates volume.** Applications sent appears only as a
  funnel stage with a stage after it.

**This is not built to be sold.** No tiers, no counter to inflate, no incentive to keep
someone applying rather than hired. Self-hosting and bring-your-own-key make that
structural: there is no meter because there is no operator.

### Engineering consequences

- **Security outranks features** once the source is public. `SECURITY.md` carries the
  disclosure contact and the known limitations.
- **CI is required** — the gate must run on every push, not only on the author's machine.
- **Accessibility is not optional.** People facing the most hiring friction are exactly
  who an inaccessible job tool excludes.
- **CV conventions are regional** (photo, date of birth, length differ between Germany,
  the UK and the US), so localisation is a real need, not polish.
- **MIT licence.** Maximum reach; no protection against a hosted fork, acceptable for
  self-hosted software.

## Product principles

1. **Deterministic first.** Anything computable — keyword coverage, skill overlap,
   seniority, salary filters, dates, parsing, dedupe — is computed, not prompted. Models
   are for judgement, phrasing and summarisation. Reproducible, cheap, testable.
2. **Never fabricate experience.** Every bullet, skill or claim produced must trace to a
   fact the user entered. What would need new experience is a *skill gap*, never
   silently written into a CV.
3. **The user owns the model.** Hosted (OpenAI, Anthropic, compatible endpoints) or local
   (Ollama). No feature hard-depends on one vendor.
4. **The user owns the data.** Full export and full delete are first-class; local-only
   mode keeps every byte on the user's hardware.
5. **Automation proposes, the user disposes.** Anything outward-facing needs explicit
   consent — per send by default, or a standing authorisation for one proven rule set
   that expires the moment that pattern materially changes. Dry run, audit log and kill
   switch exist either way. See *Review mode*.
6. **Credentials held to current standards.** NIST SP 800-63B; see *Password policy*.
7. **The UI is developable without the backend.** Mock mode serves every request from
   version-controlled fixtures.
8. **Goals before postings.** A good match is defined by what the user said they want —
   role and level, regime, compensation floor, what they want more and less of — not by
   what a source returned. Every score is explained in those terms ("you said no
   on-call; this role is one week in four"); non-negotiables filter rather than
   penalise; a posting the user would not accept is never presented as an opportunity.

## Interface rules

- **Navigation follows the journey, not object types.** The sidebar reads as the
  sequence of a search. A screen is added when it has content; no empty placeholders.
- **Every control ships wired, or it does not ship.** A user cannot tell a broken
  feature from an unbuilt one, and a Save that does nothing teaches that the app loses
  data.
- **Next actions over totals.** The dashboard answers *"what should I do now?"*: one
  primary card, scored or actionable numbers ("2 CVs below 70 on parseability"), the
  funnel (matched → tailored → applied → responded → interviewing).
- **Readiness as tasks, not a percentage.** The profile derives the list of what is
  missing and computes the score from it, so the two cannot disagree. Unevidenced skills
  are shown prominently — that is *never fabricate* made visible.
- **Automation state is always visible.** Per source: auto-submitted, one-click in your
  browser, or prepare-only — and whether review mode is on, in the same place.

## Stack

| Layer | Choice |
| --- | --- |
| Backend | Python 3.14, FastAPI, uvicorn |
| Database | SQLite + aiosqlite, Alembic owns the schema. Postgres-compatible code; move when semantic search needs pgvector |
| Background work | None. Board sync is an idempotent endpoint a cron entry can call; add a queue only when work genuinely needs one |
| Auth | JWT (PyJWT), opaque refresh tokens, argon2id (bcrypt verified for legacy hashes) |
| LLM | One `LLMClient` Protocol: OpenAI-compatible client (OpenAI, Ollama, LM Studio, vLLM, OpenRouter, …) and Anthropic via its own SDK |
| Parsing | pypdf, python-docx |
| Export | Markdown, DOCX (python-docx), PDF (ReportLab — pure Python, BSD, no system libraries) |
| Storage | Local filesystem |
| Tooling | uv, Nox → Ruff + `mypy --strict` + pytest + `alembic check` |
| Frontend | Angular 22, signals, standalone components (`frontend/cv-pal`); ESLint + Prettier |

## Architecture

```
routers/        HTTP edge — validation, auth, response schemas. Thin.
services/       Business logic. Framework-free, no HTTPException, unit-testable.
analysis/       Deterministic core: keywords, parseability, matching, extraction, similarity.
generation/     Tailored CV and cover letter over one block model; MD/DOCX/PDF renderers.
integrations/   Job boards, behind one Protocol.
llm.py          Provider-agnostic model client.
models.py       SQLAlchemy 2.0        schemas.py   Pydantic v2
```

Dependencies point inward; services never import routers; every external system sits
behind a `Protocol` so it can be faked in tests. Domain exceptions are raised in services
and translated to HTTP by exception handlers. Split into per-domain packages once modules
outgrow single files.

## LLM strategy

- **Provider abstraction.** One Protocol, two implementations. Anthropic uses its own
  SDK rather than an OpenAI-compatible shim, to keep native structured output and the
  `refusal` stop reason (a refusal is an HTTP 200 with an empty body; retrying it only
  spends tokens). Current Claude models reject `temperature`/`top_p`/`top_k` outright,
  so shared config must not forward them. Both pinned by tests.
- **Structured output.** Prompts demand JSON; responses are validated into Pydantic
  models with one corrective retry, then fail loudly rather than write garbage.
- **Local-first.** Ollama is first-class. `CV_PAL_LOCAL_ONLY=true` checks the base URL's
  *host*, not only the provider name — Ollama speaks the OpenAI wire format, so a hosted
  URL behind `provider=ollama` would otherwise leave the machine.
- **Proposes, never writes.** Model output that touches the profile (summary, CV import)
  is returned as a proposal the user saves through the ordinary endpoints. Empty inputs
  are refused before the model is called — the only summary of nothing is an invented one.
- **Reachability is checked, not assumed.** Each client can probe whether its model is
  usable (Ollama lists `llama3` as `llama3:latest`). The result is logged at start-up
  and served at `GET /health/llm`, which the AI screen reads to explain a missing model
  up front. It is not part of readiness: most of the product works without a model.
- **Planned:** per-user provider config with encrypted keys and per-task model choice;
  token and cost accounting with an optional budget; recording `provider`, `model` and
  prompt version on stored output; a small golden set of CVs and postings as an offline
  eval; optional PII redaction before hosted calls.

## Password policy

NIST SP 800-63B — deliberately the opposite of folk wisdom about special characters.

- **12 characters minimum**; maximum 72 *bytes* measured after UTF-8 encoding.
- **Screened** against a bundled common-password list (works in local-only mode), and
  against the user's own email and the app name.
- **No composition rules, no forced rotation, no hints or security questions.**
- **argon2id** at 19 MiB / 2 iterations / 1 lane. Hashes carry their parameters, so
  outdated hashes (including bcrypt) are upgraded on the next successful login — raising
  the cost needs a redeploy, not a migration.
- **Login throttling**: per-client rate limit plus exponential per-account backoff,
  counted for any submitted address so lockout cannot enumerate accounts. A missing
  account still hashes a dummy password, so it is not measurably faster.
- **Credential changes re-authenticate.** `PATCH /users/me/password` and
  `DELETE /users/me` require the current password: a bearer token proves a session was
  opened by the holder at some point, not that the holder is present now. A password
  change revokes every session, the caller's included — access tokens too, through the
  token version below.

### Sessions

Refresh tokens are opaque, stored only as SHA-256, and single-use. Presenting a spent one
revokes every session for that user — the legitimate holder and a thief cannot both have
spent it.

**Access tokens carry the account's token version.** Revoking every session (password
change, logout-all, a reused refresh token) bumps it, so outstanding access tokens die
at once instead of living out their 30 minutes.

**The browser keeps both tokens in HttpOnly cookies** (`SameSite=Strict`), so script on
the page — injected script included — never sees them. The app opts in with the
`X-CV-Pal-Session: cookie` header, and a cookie only authenticates alongside that header:
a cross-site form can make the browser send the cookie but cannot add a header, which is
the CSRF defence. In cookie mode the token bodies are empty. Bearer tokens in the body
remain for non-browser clients. `CV_PAL_COOKIE_SECURE` is off by default because the
default install is plain HTTP on localhost; turn it on behind HTTPS.

### No password-reset email

Deliberate. A reset link needs SMTP, which a self-hosted instance often lacks — so it
would be either a link that silently cannot deliver or mandatory mail setup. Recovery is
offline: `python -m cv_pal.admin reset-password <email>`, prompting so the password never
reaches shell history. It grants nothing an attacker with shell access to the database
does not already have. If a deployment has mail, an emailed reset can be added on top.

## Container security decisions

Implemented in `backend/Dockerfile`, `frontend/cv-pal/Dockerfile`,
`frontend/cv-pal/nginx.conf` and `docker-compose.yml`.

| Decision | Reasoning |
| --- | --- |
| Both containers run unprivileged (`cvpal` user; `nginx-unprivileged` on 8080). | A container escape should not start from root. |
| `no-new-privileges` on every service. | Blocks setuid escalation, free. |
| API not published; only the frontend, and only on `127.0.0.1`. | The API is reachable through the nginx `/api` proxy. Loopback means an instance is not on the LAN by accident — this is someone's CV. |
| Multi-stage builds, no build tooling at runtime. | Smaller image, smaller attack surface. |
| No secrets in images; the app refuses to start without `CV_PAL_SECRET_KEY`. | A baked-in secret is published with the image. |
| Migrations run in the entrypoint. | A self-hoster pulling a new image never migrates by hand. |
| One data volume for database and uploads, pre-created with the right owner. | One thing to back up; no chown at start-up. |
| Liveness for the container, readiness for compose's dependency gate. | A database blip should not restart the container, but the frontend should not serve before the API can. |
| Same-origin by default; `CV_PAL_CORS_ORIGINS` empty in compose. | Removes a common self-hosting foot-gun. |
| `client_max_body_size` slightly above the app's upload cap. | The proxy should not be what rejects a legitimate upload. |
| Hashed `.js`/`.css` cached immutably; everything else, `index.html` included, is not. | Files from `public/` are not fingerprinted. |

**Not done, deliberately:** read-only root filesystem, image signing, automatic HTTPS —
a self-hoster exposing an instance is expected to put a reverse proxy in front. Listed in
`SECURITY.md`.

## Frontend mock mode

- **Fixtures are typed TypeScript** under `src/mocks/`, against the same
  `shared/models/api.model.ts` the real services use — a contract change breaks the type
  check, not the runtime.
- **An unmapped route 404s loudly.** Silently falling through to the network would
  defeat the point.
- **Never a fallback for a failing API.** The interceptor is only registered when
  `environment.useMocks` is true.
- **Fixtures show imperfect data on purpose**, and must never be *prettier* than the
  real product can produce — a demo that shows what the product cannot do teaches the
  wrong thing and hides real gaps.

## Application quality gate

Nothing outward-facing leaves the system without passing this gate, whether a human
pressed the button or a rule set did: **automation skips the reviewer, never the
checks.** It is almost entirely deterministic — reproducible, explainable line by line,
free, and working with no model configured. A quality claim enforced by a model changes
when the model does.

### The checks

| Check | Verdict | Protects against |
| --- | --- | --- |
| **Grounding** — every claim traces to a profile fact | Block | Defending an invention in an interview |
| **Non-negotiables** — the posting breaks one | Block | Applying for work they would refuse |
| **Match floor** — score below the rule set's minimum | Block | Spray-and-pray |
| **Duplicate** — same company and role already applied to or open | Block | The most embarrassing automation failure |
| **Caps** — daily, weekly, per company | Block | Volume creeping back in |
| **Data completeness** — contact details and required form answers present, no placeholders | Block | An application binned for a blank field |
| **Parseability** — survives text extraction, sections detectable, dates machine-readable | Block on hard fail, warn on soft | An ATS silently dropping half the CV |
| **Missing required keywords** the profile cannot evidence | Warn, naming the gap | Wasting an application on an unreachable role |
| **Specificity / filler / stuffing / self-similarity** | Warn | See below |

A warning is shown, recorded on the application and passed through. A block stops the
send and names the one thing to fix. In review mode a user may override a warning; **no
one may override a block**.

### "Will an ATS flag this as AI?" — the honest version

Taken literally this cannot be built: ATSs overwhelmingly do not run AI detectors; the
detectors that exist systematically over-flag non-native speakers and plain writers —
exactly the users this project is for; and the target is unobservable.

So the check is inverted: not *does this look machine-written* but **does this look
written for this job** — measurable, and equally true of good human and machine writing:

- **Specificity** — bullets with no figure, named system, artefact or scope.
- **Filler density** — a bundled list of phrases that survive their own deletion
  ("results-driven", "passionate about").
- **Self-similarity** — shingled similarity against the user's own recent letters. The
  strongest signal available, and available to nobody else: only a tool holding the
  whole history can see that the last ten letters were 92% identical.
- **Posting specificity** — anything true only of this company and role.
- **Stuffing** — keyword density above a natural range.

**Non-negotiable rule:** the system never optimises for evading detection. A check that
could be satisfied by making text vaguer or disguising authorship — by any change that
does not also make the application more true or more specific — does not belong here.

### Review mode

`review_mode` is an account preference, **on by default**. Before anything is sent the
user sees the document as it will arrive, the diff against their base CV with the profile
fact behind each change, every form value, the destination, and the gate's verdicts.

Turning it off is deliberately not one toggle:

- **Per source and per rule set, never global.**
- **Unlocks only after that rule set produced applications the user approved without
  editing** (five, as a placeholder).
- **Disabling states what changes in plain language and takes a typed confirmation**,
  where the decision is made — not a settings tooltip.
- **Authorisation expires on material change** — editing the rule set, base CV, goals or
  profile re-arms it. The user approved a *pattern*; when the pattern changes, the
  approval does not carry.
- **Kill switch, dry run and audit log exist in both modes**, and blocks block in both.

## The three permitted transforms, and nothing else

Tailoring may change a CV in exactly three ways:

1. **Surface** — include a profile fact this CV version omitted, because the posting asks
   for it. Selection, not rewriting. Safest and usually most effective. *Built.*
2. **Substitute within an equivalence class** — the posting's term for the same thing,
   where the alias map says they are the same (`Postgres` → `PostgreSQL`). **Never across
   classes**: Oracle experience is not Postgres experience. *Built, gated on the alias
   map.*
3. **Rephrase** — the posting's vocabulary and register, same claim, same evidence.
   *Not built; the only one that wants a model.*

Anything a posting asks for that none of these can reach is a **gap**: named, ranked by
match-score cost, never written into a document.

This puts the alias map on the **safety** path. Outside software there is no equivalence
data, so transform 2 must be **disabled** there rather than approximated — see below.

### Known limitation: the vocabulary is software-specific

Every alias in `backend/cv_pal/analysis/vocabulary.py` is a software-engineering term.
The machinery is domain-neutral, the data is not: a nurse, teacher or accountant gets no
alias resolution, weaker keyword coverage, and — because of the rule above — no
substitution at all. Letting a model decide whether two unfamiliar occupational terms are
equivalent is exactly the fabrication principle 2 exists to prevent.

The fix is to derive the alias map from ESCO or O\*NET, which cover every occupation.
Until then the tool is honestly strongest for software roles, and the README says so.

## Roadmap

What exists is summarised in [PROGRESS.md](PROGRESS.md). This section is the design of
what does not.

### Scope

Depth over breadth. The v1 loop, in dependency order: career profile and goals →
analysis plus the quality gate → tailored generation and export → job sources, rules and
automation → application tracking and reply-rate analytics → LinkedIn review. Tailoring
comes before automation because automation sends the tailored output; building
submission rails before there is anything worth submitting is how a plan grows phases and
no product.

### Career profile and goals — remaining

- Model enrichment of what deterministic CV extraction could not read.
- Projects and certifications; JSON Resume import.
- Skill normalisation beyond the alias map (ESCO / O\*NET).
- Deferred goal fields, added when something reads them: direction (step up / lateral /
  pivot), commute ceiling, contract types, company size and stage, industries to avoid,
  and the *more of / less of* work-content axes.

Two rules from the goals API worth keeping: it is **`PUT`, not `PATCH`** (the form is
edited whole, so an omitted preference means cleared); and **a non-negotiable with
nothing behind it is rejected** — it would filter out every posting with no visible
reason.

### Analysis — remaining

The quality-gate measures (specificity, filler, stuffing, posting specificity), bullet
strength (action verb + scope + measurable result), readability, length and tense
consistency. All deterministic, and useful on a plain CV review long before automation.

### Phase 7 — Job sources, rules and automated application

**Rules are derived from `CareerGoals`**, not maintained separately: a rule set starts
as their projection and the user narrows it per campaign. Rules filter; the model only
writes the rationale. Every score is explainable in the user's own terms.

**Sources**, tiered by what they permit:

| Tier | Sources | Collection |
| --- | --- | --- |
| A — sanctioned | ATS boards (Greenhouse, Lever built; Ashby, Workable, SmartRecruiters), aggregator APIs (Remotive built; Adzuna, Arbeitnow, RemoteOK), company feeds | Automated |
| B — restricted | LinkedIn, Indeed, Monster | User-driven only |
| C — manual | Pasted description, recognised links | On demand — the fallback that cannot break |

**No general URL fetcher — a security decision.** Fetching a user-supplied URL from the
server is a request-forgery primitive (router, cloud metadata endpoint, every service on
the host). A link is accepted only when a sanctioned board recognises it, and is resolved
through that board's API; the API URL is built from the matched identifier, never taken
from the user. A test pins the refusal, including `169.254.169.254` and `file://`.

**Submission**, tiered the same way:

1. **Auto-submit** — tier A only, where the source publishes an application API.
2. **Assisted submit via browser extension** — fills the form in the user's own browser
   and session; the user presses submit. No stored credential, no headless session. This
   is the path LinkedIn's terms affirmatively allow (extensions enhancing the user's own
   experience, without scraping and without sending unreviewed). **Hard constraint: it
   fills fields and stops** — no synthesised clicks or scripts driving the page, which are
   what detection looks for. Build this before any tier A auto-submit.
3. **Prepare-only** — tailored CV and letter, open the posting, track the outcome.

**No headless bot for LinkedIn, Indeed or Monster.** All three prohibit it and LinkedIn
acts on it: the cost is the user's account and the network their search depends on.
Restriction rates for flagged automation are high, and vendor-level bans cut off every
user of a tool at once. The competitors' volume comes from tier A plus an answer bank —
there is no third technique being withheld.

**Rails on every tier:** daily, weekly and per-company caps; dry run by default for a new
rule set; mandatory review of a rule set's first applications; full audit log; global
kill switch. **Every submission passes the quality gate first.**

**Dedupe:** the same role on five boards collapses to one — content hash plus fuzzy
company / title / location. **Semantic search** over postings and profile via
embeddings, local in local-only mode.

### Phase 8 — Tailoring — remaining

Transform 3 (rephrase); a diff against the base CV approved per change or wholesale; a
page-count budget; selectable single-column templates; JSON Resume export; recruiter
outreach messages from the same grounded facts.

### Phase 9 — Application tracking — remaining

Per-transition status history, the exact CV version and letter sent per application,
follow-up reminders, and reply rate **per CV variant, per source and per rule set** —
the evidence for the whole quality-over-quantity position.

### Phase 10 — LinkedIn profile import and review

A LinkedIn URL cannot be fetched (automated access under LinkedIn's terms, and the
account at risk is the user's). Ingestion routes, user guide in
[linkedin-import.md](linkedin-import.md):

1. **Browser print-to-PDF** — primary. Works on every account; the parser tolerates
   navigation chrome; collapsed sections are absent and the review says so.
2. **LinkedIn's "Save to PDF"** — cleaner but inconsistently available. Support, never
   depend on.
3. **Paste** — always available; section boundaries are lost, so the review says which
   mode produced it.
4. **Official data export (ZIP)** — richest, but up to 72 hours to arrive.

A LinkedIn PDF is recognisable on upload, so the user never has to say what they are
giving. The review: headline and about coverage against target roles, completeness per
section, and consistency against the profile (dates, titles, employers). Remaining: a
model pass for phrasing, and skill gaps against the roles actually being matched, priced
in match score.

### Phase 11 — Notifications and insights

Digest of new matches and stale applications (email, webhook or in-app); insight from
the user's own match history (recurring skills, salary distribution, titles they are
competitive for); a profile-health score that decays as the CV goes stale.

### Phase 12 — Career path planning

*"Where could this career go, and would I enjoy it there?"* The output is a graph: roles
as nodes, transitions as edges with a feasibility score, one to three moves out. Each
node answers how far it is (deterministic skill overlap and gap), what the work involves,
what it pays and whether demand is rising, and what would suit or grate.

Grounding, because someone may retrain for two years on this: the user's own matched
postings first, then an occupation taxonomy (O\*NET, ESCO) for what the work involves,
and the model for narrative only — **never the source of a number**. Every claim shows
its provenance. "Boring" is personal, so the product reports what a role involves a lot
of and matches it against the user's *more of / less of* answers — the same answers
`CareerGoals` feeds to match scoring, so the two can never disagree. Multi-step per
node, cached per role, run in the background. No predictions about individual outcomes.

### Packaging

1. **Docker Compose** — built. `docker compose up` pulls images published to ghcr.io by
   the release workflow; `docker-compose.build.yml` builds from source. Ollama is an
   opt-in profile; pointing at the host's own Ollama via `host.docker.internal` is a
   supported configuration.
2. **Installable PWA** against a self-hosted instance — manifest, service worker, offline
   shell. Small; makes "on my phone" true for most people.
3. **Serverless local build** — post-1.0. The seam exists: mock mode already intercepts
   the single HTTP boundary, so a client-side implementation of the same contract (WASM
   SQLite over OPFS, pdf.js, the deterministic core in the browser) reuses the whole UI.
   Most of the product's value needs no model. Risks to design for: browser storage is
   evictable (request persistent storage, prompt for export), and two implementations of
   the deterministic core would drift — prototype Pyodide before writing a parallel
   TypeScript core. **Not before the desktop loop is proven.**
4. **Native shell** (Capacitor) — only if tier 3 proves itself.

### Later

Interview preparation grounded in profile facts; multi-language CVs and regional
formats; multiple target-role profiles from one career profile; anonymised export;
referral finder from the user's own contacts export; a browser extension to capture a
posting from any site.

## Data protection

Encrypt user LLM keys at rest (once per-user config exists). Uploads stored outside the
web root under generated names. Full export and hard delete, files included. A retention
policy for raw job descriptions. Redaction before hosted calls when enabled. Local-only
mode fails closed.

## Open decisions

1. **Which job sources next** — ATS boards give clean data, aggregators give volume.
2. **How the goals questions are asked** — one form (complete answers, a wall for a new
   user) or progressively as matches arrive (better answers, a thin matcher at first
   impression). The first-run flow currently asks the core up front.
3. **Whether `review_mode` should be disableable at all**, and after how many approved
   applications. The honest answer may be that unattended submission never earns its
   risk for a tool one person maintains.

### Resolved

- **CV → profile extraction is deterministic first**, with the model as an enricher. It
  works with no model, is testable against fixtures, and extraction feeds the record
  every CV is grounded in — the worst place to accept "usually right". The hard part
  turned out to be layout, not language, which résumé-parsing libraries do not solve
  either. Output is always a proposal the user confirms.
- **The repository lives on GitHub** — for discoverability, CI on GitHub Actions, and
  published container images on ghcr.io.
- **Multi-user, self-hosted.** **SQLite for now.** **MIT licence.**

## Writing standards

Explain the *why*; the code already says the *what*. The comments worth keeping record a
decision a reader would otherwise undo. Inline comments are one or two lines — longer
reasoning belongs in a docstring or here. **No phase numbers, session numbers or history
in code comments**; they go stale the moment the plan moves.
