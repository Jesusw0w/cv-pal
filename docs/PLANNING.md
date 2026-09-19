# CV Pal — Planning

## Context

Job seekers lose time to two things: keeping a CV competitive against AI screening, and
running the search itself — finding relevant roles, tailoring a CV per role, tracking
applications, and keeping a LinkedIn profile aligned with the roles they want.

CV Pal automates that loop. It maintains a structured career profile as the single
source of truth, generates ATS-optimised CVs tailored to real job postings, surfaces
matching roles from job sources, reviews the LinkedIn profile, and tracks every
application — with the user in control of the LLM that powers the non-deterministic
parts, including a fully local option via Ollama.

## Intent, audience and distribution

Three audiences, in priority order:

1. **The author**, using it for a real job search. The only user whose feedback is
   direct, and the reason correctness beats feature count.
2. **Other job seekers**, running it themselves.
3. **Engineers reading the repository** — it is intended to become open source and to
   stand as portfolio work.

The third audience changes more than it appears. For a portfolio, **the repository is
the artefact**: most readers will never run the app, so the README, the documentation,
the tests, the commit history and the shape of the code *are* the product. That argues
for depth over breadth — one loop done thoroughly, with tests and stated reasoning,
signals more than eleven half-finished phases.

### Distribution: self-hosted first

**CV Pal ships as software people run themselves, not as a service the author hosts.**
This is the single decision that most shapes the rest:

- A CV is personal data, and in Europe frequently *special-category* data — photographs,
  dates of birth, nationality, sometimes health or disability disclosures. Hosting other
  people's CVs makes the operator a data controller, with the lawful-basis, retention,
  breach-notification and subject-access obligations that follow.
- Every analysis costs money. A hosted service pays for other people's LLM calls, which
  turns cost control into a product problem before the product is finished.
- Self-hosting makes the *local-first* principle real rather than aspirational: with
  Ollama, a user's CV never leaves their machine, which is a genuine differentiator
  against every hosted CV tool.

Consequences for the plan: **container packaging is a feature, not an afterthought** —
`docker compose up` with a seeded database is the expected entry point, and it needs to
exist before any public release. Per-user LLM provider configuration moves from
nice-to-have to required, because "bring your own key" is the only sustainable model for
software other people run. A hosted multi-tenant offering stays possible, but is out of
scope until there is demand and a legal basis for it.

### Public demonstrability

A portfolio project nobody can try is a portfolio project nobody sees, and asking a
reader to `git clone && docker compose up` loses almost all of them.

The mock mode built in Phase 4b already solves this: it produces a fully static bundle
with no backend, no database and no LLM. **Deploying that build as the public demo** is
therefore a first-class deliverable — zero hosting cost, zero personal data, no signup,
and it exercises the real UI. The README should lead with that link.

### Guarantees and non-goals

Serving other people turns two internal principles into user-facing promises:

- **Never fabricate experience.** For a single user this was a quality rule. For other
  people it is a safety guarantee: a hallucinated employer or invented skill on a CV is
  something the user must then defend in an interview, or that costs them an offer. Gaps
  are reported as gaps.
- **Targeted automation, not spray-and-pray.** Automating applications is a core
  feature, not a non-goal — the whole point is to remove the tedium from a search. What
  is ruled out is *untargeted volume*: every application is driven by the user's own
  rules, must clear a minimum match score, is capped per day and per company, is
  tailored to the specific posting, and is written to an audit log. The distinction that
  matters to a recruiter is whether the application was relevant, not whether a human
  pressed the button.

Both belong in the README, not only here — they are what distinguishes this from the
generative CV tools that will happily invent a career, and from the apply-bots that
carpet-bomb job boards.

> **Revised in session 9.** The earlier wording said bulk submission was a non-goal
> outright. That was written when the product was a CV tool; automated applying is now
> a headline feature, so the promise was narrowed to what it can actually keep. The
> constraint that survives is targeting and rate limiting, not the absence of automation.

### What the market already sells, and why not to compete there

**Recorded in session 14**, from a survey of the paid tools in this space. The category's
default product is volume: JobCopilot and its imitators advertise 50–100 automated
applications a day for around $10 a month. That is a real product with real customers,
and it is what a reader will assume CV Pal is until told otherwise.

It is worth being precise about *why* volume sells, because the reason is not that it
works. It sells because **applications sent is the only number a job seeker can watch
move.** Interviews are sparse, delayed and hard to attribute; a counter that rises every
day feels like progress. A tool optimising that number is optimising the metric its user
can observe rather than the one they actually want.

The counter-position is therefore not "fewer applications" — nobody wants fewer
applications. It is **applications worth the reader's time**, decided against what the
user said they want rather than against whatever the scraper returned. Three
consequences, all of which are commitments rather than slogans:

- **Goals are the input, not the CV alone.** See principle 8. What makes a match good is
  defined by the user's stated targets, work regime, floor and tolerances; the posting is
  scored against those, and the score is explained in the user's own words.
- **The claim must be measured, not asserted.** Reply rate per CV variant, per source and
  per rule set (Phase 9) is not analytics polish — it is the only honest evidence that
  this approach beats volume, and it is evidence about the user's *own* search rather
  than a marketing figure. If that data ever says volume wins for them, the product
  should be capable of saying so.
- **No number in the interface celebrates volume.** Applications sent is never a headline
  statistic. The funnel already shows it in the only place it means anything: as a stage
  with a stage after it.

The motive belongs in the same breath, because it explains the shape of the whole
project: **this is not built to be sold.** There are no usage tiers to defend, no reason
to inflate a counter, and no incentive to keep someone applying rather than hired.
Self-hosting and bring-your-own-key are what make that structural rather than a promise —
there is no meter, because there is no operator to pay.

### Consequences for engineering standards

- **Security work outranks features before going public.** Once the source is readable,
  unfinished auth is discoverable by anyone. Refresh tokens with revocation should land
  before the repository is published, and a `SECURITY.md` with a disclosure contact
  alongside it.
- **CI is required.** The `nox` gate and the frontend tests exist but run only on the
  author's machine. A public repository needs them running on every push, both as a
  contributor check and as an honest signal.
- **Accessibility is not optional.** The audience explicitly includes people facing the
  most hiring friction, which correlates with disability. An inaccessible job-seeking
  tool excludes exactly the people it claims to help; it is also among the clearest
  craft signals a reviewer can see.
- **CV conventions are regional.** Photograph, date of birth and page-length expectations
  differ sharply between, say, Germany, the UK and the US. Serving people beyond the
  author moves localisation up from *Later*.
- **The licence is MIT**, already committed. Permissive by design: anyone may run,
  fork or build on this, which is the right trade for portfolio reach. It offers no
  protection against a hosted commercial fork — an acceptable cost given the product is
  self-hosted rather than a service.

## Documenting it as open source

The repository is read far more often than it is run. Documentation is therefore a
deliverable with the same standing as code, and it is written for four distinct readers
who want different things in the first thirty seconds.

### The README, in order

Readers abandon a README at the first paragraph that does not answer their question, so
the order matters more than the content:

1. **One sentence** on what it is and who it is for.
2. **A screenshot or short recording.** Nothing else establishes as fast that the thing
   is real and finished-looking.
3. **Try it** — the link to the hosted mock demo, with a note that it needs no account
   and stores nothing.
4. **The two guarantees** — never fabricates experience, not a mass-application tool.
   These are the differentiators against generative CV tools; they belong above the fold,
   not in a philosophy section. State the second one against the market rather than in
   the abstract: the competition advertises 50–100 applications a day, this does not, and
   here is what it does instead. A reader who has seen those ads needs the contrast, not
   a value.
5. **Run it yourself** — the shortest possible path, ideally `docker compose up`, then a
   link to the self-hosting guide.
6. **Why local-first**, in three lines: your CV is the most sensitive document you own,
   and with Ollama it never leaves your machine.
7. **Status**, honestly. What works, what does not, and a link to `PROGRESS.md`.
8. **Architecture at a glance** — a short diagram and a link to this document.
9. **Contributing**, **licence**.

Badges for CI status, licence and Python version go at the top: they are read as a
quality signal whether or not that is fair.

### Repository files a reader expects

| File | Purpose |
| --- | --- |
| `README.md` | The shop window, as above. |
| `LICENSE` | MIT, present. |
| `CONTRIBUTING.md` | How to set up, the quality gate (`nox`), commit and PR expectations, and what kinds of contribution are wanted. Points at `docs/development.md` rather than repeating it. |
| `SECURITY.md` | How to report a vulnerability privately, and the expected response time. Required before publication: without it, reports arrive as public issues. |
| `CODE_OF_CONDUCT.md` | Contributor Covenant. Cheap, and its absence is noticed. |
| `.github/ISSUE_TEMPLATE/` | Bug and feature templates that ask for the version, the provider in use, and whether it is a self-hosted or demo build. |
| `docs/self-hosting.md` | For non-developers: install Docker, copy one file, run one command, open a browser. No `uv`, no `npm`, no Python. |
| `docs/architecture.md` | The layering, the seams, and *why* — the document an engineer assessing the work will actually read. |

`PLANNING.md` doubles as the decision record: it states what was chosen and what was
rejected, which is more useful to a reader than a folder of ADRs would be at this size.

### Writing standards

Explain the *why*, not the *what* — the code already says what. The comments and
documents that earn their place are the ones recording a decision a reader would
otherwise undo: why the reloader is off in the debug config, why lockout counts
unregistered emails, why bcrypt is still in the dependency list. Keep that habit.

Two rules for inline comments specifically, both added after a pass that found the code
narrating itself:

- **One line, two at the most.** A paragraph above three lines of code is a sign the
  reasoning belongs in a docstring or in this document. Docstrings may be as full as
  they need to be; inline comments may not.
- **No phase numbers, session numbers or history.** "Phase 8", "rebuilt in session 24",
  "what was here before" — that is what this file and `PROGRESS.md` are for, and in a
  comment it goes stale the moment the plan moves. Say why the code is the way it is,
  not when it got that way.

## Packaging: how people actually run it

Four channels, in the order they should be built. Each is useful on its own, and each is
a superset of the privacy guarantees of the one before it.

### Tier 1 — Docker Compose (desktop, full features)

The default and the one that must exist first. `docker compose up` brings up the API,
the frontend, the database with migrations already applied, and optionally an Ollama
container with a model pulled.

- **Audience:** anyone with Docker Desktop on macOS or Windows, or Docker Engine on
  Linux. This is the only dependency a user should need — no Python, no Node, no uv.
- **Must include:** a `.env.example` copied to `.env` as the single configuration step,
  a healthcheck-gated startup order so the API does not race the database, a named
  volume for uploads and the database so data survives `docker compose down`, and a
  clearly documented backup path for that volume.
- **Sizing note:** an Ollama container with a 4–8 B model wants roughly 8 GB of RAM. The
  compose file should make the Ollama service opt-in via a profile rather than assume it,
  so the app starts on a modest laptop and simply reports the model as unavailable.

### Tier 2 — Installable PWA against a self-hosted instance

The cheapest way to answer "I want this on my phone". The Angular app gains a web
manifest and a service worker; the user installs it from the browser and it points at
their own instance on the local network or their own host.

Data still stays on hardware the user controls, and there is no app store, no signing,
and no second codebase. Offline support is limited to caching the shell and read-only
views, since the data lives on the server.

### Tier 3 — Serverless local build (mobile and desktop, no backend at all)

The interesting one, and it is closer than it looks. **The seam already exists:** the
frontend talks to the backend across a single HTTP boundary, and mock mode already
intercepts that boundary. Replacing fixtures with a real client-side implementation of
the same contract yields a build with no server, reusing the entire UI unchanged.

What runs in the browser without a server:

| Concern | Client-side approach |
| --- | --- |
| Storage | SQLite compiled to WASM over OPFS, or IndexedDB |
| PDF text extraction | `pdf.js` |
| DOCX extraction | `mammoth.js` |
| CV export | `docx` and `pdf-lib` |
| Keyword coverage, ATS parseability, skill matching, scoring, diffing | Plain TypeScript |

The last row is the point. **Principle 1 says deterministic first**, so the majority of
the product's value — parseability checks, keyword coverage against a job description,
gap analysis, scoring, export — needs no model at all. A serverless build is therefore a
genuinely useful product, not a crippled demo, even with no LLM present.

For the parts that do want a model, three options, honestly ranked:

1. **A model on the user's own network** — the phone talks to Ollama running on their
   desktop. Best quality, data never leaves the household. Requires that desktop to be
   on.
2. **On-device via WebGPU** (WebLLM or similar). Genuinely private and genuinely
   offline, but constrained: a 1–3 B quantised model, a one-off download of one to two
   gigabytes, and patchy WebGPU availability across mobile browsers. Honest assessment —
   adequate for extraction and classification, weak for the polished rewriting that is
   the most visible feature.
3. **The user's own hosted key, called directly from the device.** Good quality, no
   server of ours involved, but data does leave the device — so it must be opt-in and
   labelled plainly rather than presented as "local".

**Risks that must be designed for, not discovered:**

- **Browser storage is evictable.** Both OPFS and IndexedDB can be cleared by the OS
  under storage pressure, and iOS is the most aggressive. A user losing their career
  profile is unacceptable, so this build must request persistent storage *and* treat
  export as a first-class, prompted action rather than a menu item. The JSON Resume
  export already planned becomes the backup format.
- **Two implementations of the deterministic core.** Python on the server, TypeScript in
  the browser: the same rules in two languages, drifting apart. This is the strongest
  argument against Tier 3 and needs a decision before starting. The options are to keep
  the shared core deliberately small and cover both with the same golden-file fixtures;
  or to run the existing Python in the browser via Pyodide, which removes the
  duplication entirely at the cost of a large download and slower startup. Worth
  prototyping Pyodide before committing to a parallel TypeScript core.

### Tier 4 — Native shell (only if Tier 3 proves itself)

Capacitor wrapping the same Angular application: native file access, a share target so a
job posting can be shared into the app from a browser, background execution, and native
SQLite instead of OPFS. It reuses the Tier 3 work rather than replacing it, which is why
it comes last and only if there is demand. App store review, signing and release
management are a real ongoing cost for a personal project.

### Sequencing

Tier 1 belongs in Phase 4c, before publication. Tier 2 is a small addition and can
follow immediately. **Tier 3 should not start until the v1.0 desktop loop is proven** —
building the same product twice before knowing the product is right is the most
expensive mistake available here.

## Container security decisions

Recorded so they can be reviewed rather than taken on trust. All are implemented in
`backend/Dockerfile`, `frontend/cv-pal/Dockerfile`, `frontend/cv-pal/nginx.conf` and
`docker-compose.yml`.

| Decision | Reasoning |
| --- | --- |
| **Both containers run as an unprivileged user.** The backend creates a `cvpal` system account; the frontend uses `nginx-unprivileged`, which listens on 8080. | A container escape should not start from root. Nothing in the stack needs to bind a privileged port. |
| **`no-new-privileges` on every service.** | Blocks privilege escalation through setuid binaries, at no cost. |
| **The API is not published to the host.** Only the frontend's 8080 is, and only on `127.0.0.1`. | The API is reachable through the nginx `/api` proxy, so publishing it as well would add exposure without adding capability. Binding to loopback means an instance is not on the local network by accident — this is someone's CV. |
| **Multi-stage builds; no build tooling in the runtime image.** `uv`, `npm` and the dev dependencies exist only in the builder stage. | Smaller attack surface and a smaller image. |
| **No secrets in images.** `CV_PAL_SECRET_KEY` arrives at runtime from `.env`, which is gitignored, and the app refuses to start without it. | A secret baked into a layer is a secret published with the image. |
| **Migrations run in the entrypoint, not in the app.** | Keeps `create_all()` out of the runtime path and means a self-hoster pulling a new image never has to run a migration by hand. `upgrade head` is a no-op when current. |
| **The data volume holds both the database and uploads**, and the image pre-creates `/data` with the right ownership. | One volume to back up. Docker seeds a fresh named volume from the image directory, so the unprivileged process can write to it without a chown at start-up. |
| **Health checks: liveness for the backend container, readiness for compose's dependency gate.** | Restarting a container because the database blipped would turn a transient fault into an outage; but the frontend should not accept traffic until the API can actually serve. |
| **Same-origin by default.** nginx proxies `/api/`, so `CV_PAL_CORS_ORIGINS` is empty in the compose environment. | CORS misconfiguration is a common self-hosting foot-gun. Removing the need for it removes the mistake — and it re-opens the option of `HttpOnly` cookies for tokens, which the separate-origin design had closed off. |
| **`client_max_body_size` set slightly above the application's own upload cap.** | The proxy should not be the thing that rejects a legitimate upload, and should not accept far more than the app will. |
| **Static assets cached immutably, `index.html` never cached.** | Fingerprinted files are safe to cache forever; caching the entry point pins users to a stale build after an upgrade. |

**Not done, deliberately:** no read-only root filesystem (SQLite and nginx both want
writable paths, and the gain over an unprivileged user is small here), no image signing,
and no automatic HTTPS — a self-hoster exposing an instance beyond localhost is expected
to put a reverse proxy in front. All three are listed in `SECURITY.md` under known
limitations.

## Interface direction

From the first review of the mock build (session 9), extended in session 13. The
structure is sound; the problems are that it shows numbers instead of next actions, that
the automation the product is built around has no home in the navigation, and that the
navigation is organised by the wrong thing entirely.

| Item | State |
| --- | --- |
| Navigation follows the journey | Reordered in session 13; two destinations still missing |
| Dashboard: passive → actionable | Built in session 12 |
| Career profile has a screen | Built in session 13; real API session 14; **editable, with CV import, session 20** |
| Sign-in has a screen | Built in session 14 |
| Goals are asked for somewhere | Screen built in session 21 |
| The analysis has a screen | Built in session 18 — upload, paste a posting, parseability + coverage |
| Job search → automation | Postings, scoring, manual add, watched boards, tailoring and export built (sessions 21–24, 29–31); rules, queue and submission not started |
| LinkedIn has a home | Built in session 25 — import, review, consistency against the profile |

### Navigation follows the journey, not the object type

**Recorded in session 13.** This is the root of the "bland" feedback, and session 9
diagnosed only its symptoms. Making each screen more actionable is worth doing, but a
dashboard cannot compensate for navigation that does not describe the work.

The original navigation named object types — *Documents*, *AI Tools*, *Job Search* — and
left the user to infer the order to use them in. A job search is a sequence, and the
sidebar should read as that sequence top to bottom:

```
Dashboard → Career Profile → Documents → Job Search → AI Tools → Settings
```

The profile comes first because it is the record every CV is rendered from; documents
come before the search because a match is applied for with one. Two destinations the
journey needs do not exist yet and are deliberately **not** added as empty placeholders:
*Applications* (Phase 9) and *LinkedIn* (Phase 10). A navigation entry that leads
nowhere is worse than an absent one — it reads as a broken product rather than an
unfinished one.

The corollary is that **a screen is added when it has content, and the order is fixed
when it is added**, rather than reserving slots in advance.

### A control that does nothing is worse than an absent one

**Recorded in session 18**, as the same rule one level down. The navigation had no empty
destinations, but the screens were full of empty controls: a five-item settings nav where
nothing navigated, a **Billing** section in a self-hosted MIT project, name and title
fields that wrote to an in-memory object and were lost on reload, *Compact View*,
*Auto-suggestions* and *Default Tone* toggles that no code read, Save and Cancel buttons
wired to nothing, a notification bell, a Filter button, an Apply button. Thirteen controls
in total, all removed.

They are worse than absent because a user cannot tell a broken feature from an unbuilt
one. Pressing Save and having nothing happen teaches that the app loses data — which, for
a tool holding a career history, is the single most expensive impression to create.

The replacement rule: **every control ships wired, or it does not ship.** Settings is now
two sections — the account, and dark mode — because those are the only two that were ever
real. `ProfileService` and its invented `UserProfile`/`UserPreferences` models were
deleted outright; the sidebar reads the actual signed-in account from `/users/me`.

### The career profile had no screen at all

The sharpest instance of the problem above. Phase 5's backend landed in session 10 —
`GET /profile`, experiences, educations, skills with evidence links — and the first step
of the entire journey was invisible in the interface: no route, no navigation entry, no
component. Built in session 13.

Two decisions worth keeping:

- **Readiness is expressed as tasks, not a percentage.** The page derives a list of
  what is missing (*evidence 2 skills*, *link your LinkedIn profile*) and computes the
  score *from that list*, so the number and the list cannot disagree. This is the same
  rule as "replace vanity counts with movement", applied one screen earlier.
- **Unevidenced skills are shown as such, prominently.** `is_evidenced` exists so a
  generator can tell a grounded claim from an asserted one; surfacing it in the interface
  is what turns *never fabricate experience* from a backend invariant into something the
  user can see and act on before it costs them an interview.

### The dashboard reads as bland because it is passive

Neat, but it reports state rather than prompting action. A job search is a pipeline with
a next step at every moment, and the dashboard should always answer *"what should I do
now?"*. Concretely:

- **Lead with the one thing worth doing next** — a CV whose ATS check is failing, three
  matches waiting for review, an application with no response in two weeks. One primary
  card, not a row of equal tiles.
- **Replace vanity counts with movement.** "8 documents" says nothing. "2 CVs below 70
  on ATS parseability" is a task. Numbers should be actionable or scored, not totals.
- **Show the funnel**, because that is the shape of a search: matched → tailored →
  applied → responded → interviewing. Where applications stall is the most useful thing
  a job seeker can see, and nothing else in the product shows it.
- **A profile-health score that decays**, so a CV going stale is visible before it costs
  an opportunity.
- **Recent activity as a timeline** — what the automation did while the user was away.
  With a bot acting on their behalf, this stops being decoration and becomes the trust
  mechanism.

Visual density should rise with meaning, not decoration: a sparkline of response rate
earns its space, a gradient does not.

### Job search becomes automation

The current screen finds and lists matches, which is half of it. It should become one
place covering the whole loop, in this order:

1. **Rules** — the target roles, must-haves, exclusions, locations, salary floor, and
   the caps and match-score threshold that bound the automation. Pre-filled from the
   user's goals rather than asked again, and showing which answers came from there.
2. **Matches** — scored against those rules, each with the *reason* for its score and
   the specific gaps, from the deterministic analysis. Reasons are phrased against the
   user's stated goals, per principle 8.
3. **Queue** — matches with a tailored CV prepared, awaiting the user's go-ahead. This is
   where the *Application quality gate* is surfaced: the verdicts, the diff against the
   base CV with the profile fact behind every change, and the form values as they will be
   sent. Blocks are shown as the one thing to fix, not as a red badge.
4. **Sent** — the application tracker with status and follow-up reminders.
5. **Activity log** — every automated action, reversible where possible.

The automation level is per source and visible at all times, since it differs by what
each site permits: *auto-submitted*, *ready for one-click submit in your browser*, or
*prepared, apply manually*. **Whether `review_mode` is on for that source is shown in the
same place** — a user should never have to open Settings to find out whether something is
about to be sent in their name.

### LinkedIn needs a home in the navigation

Absent from the interface today. It wants its own section: connect the profile (Save to
PDF upload, data export, or paste), then a scored section-by-section review, a
consistency check against the CV, and skill gaps against the roles being matched.

## Product principles

1. **Deterministic first.** Anything that can be computed — keyword coverage, skill
   overlap, seniority match, salary filters, date maths, file parsing, dedupe — is
   computed, not prompted. LLMs are used for judgement, phrasing, and summarisation
   only. This keeps results reproducible, cheap, and testable.
2. **Never fabricate experience.** Every CV bullet, skill, or claim the system produces
   must be grounded in a fact the user entered in their profile. Suggestions that would
   require new experience are surfaced as *skill gaps*, never silently written into a CV.
3. **The user owns the model.** Any LLM-backed operation runs on a provider the user
   picked — hosted (OpenAI, Anthropic, OpenAI-compatible endpoints) or fully local
   (Ollama). No feature may hard-depend on a single vendor.
4. **The user owns the data.** CVs and career history are sensitive. Full export and
   full delete are first-class features; a local-only mode (Ollama + SQLite/Postgres on
   the user's machine) must keep every byte on their hardware.
5. **Automation proposes, the user disposes.** Automated runs produce drafts, matches
   and queued applications. Anything outward-facing (sending an application, publishing
   a profile change) needs explicit consent — either per send, which is the default, or
   a standing authorisation the user granted for one proven rule set with the
   consequences stated, and which expires the moment that pattern materially changes.
   Dry-run mode, an audit log and a kill switch are present either way. See
   *Application quality gate → Review mode*.

   > **Amended in session 14.** This previously said "explicit confirmation" without
   > qualification, which the product would not have kept: unattended submission is a
   > planned feature and would have contradicted the principle on the day it shipped. The
   > wording now describes consent that can be granted once for a bounded pattern, which
   > is defensible, rather than a per-send confirmation that was going to be quietly
   > dropped.
6. **Credentials are held to current standards.** An account here guards a full career
   history and, later, the ability to apply for jobs in the user's name. Password rules
   follow NIST SP 800-63B: length over composition theatre, breach/common-password
   screening, and a hashing scheme with no silent truncation. See *Password policy*.
7. **The UI must be developable without the backend.** Frontend work cannot be gated on
   a running API, a database, or an LLM. A mock mode serves every request from
   version-controlled fixtures. See *Frontend mock mode*.
8. **Goals before postings.** What counts as a good match is defined by what the user
   said they want — role and level, work regime, compensation floor, and the parts of a
   job they want more and less of — not by what a source happened to return. Every score
   is explained in those terms ("you said no on-call; this role is one week in four"),
   non-negotiables filter rather than merely penalise, and a posting the user would not
   accept is never presented as an opportunity. Added in session 14; it is the axiom the
   whole *quality over quantity* position rests on, and it was previously implicit in
   Phase 7's match rules rather than stated.

## Stack

| Layer | Choice |
| --- | --- |
| Backend | Python 3.14, FastAPI, uvicorn |
| Database | SQLite + aiosqlite (dev) → PostgreSQL + asyncpg (prod), Alembic migrations |
| Background work | arq (Redis) — scheduled searches, analyses, digests |
| Auth | JWT (python-jose), argon2id hashing (bcrypt verified for legacy hashes) |
| LLM | Provider-agnostic layer behind one `LLMClient` Protocol. OpenAI, **Anthropic**, Ollama, and any OpenAI-compatible endpoint (LM Studio, vLLM, OpenRouter, Together, Groq) |
| Embeddings | Provider-agnostic: hosted embeddings or local via Ollama; `sqlite-vec` (dev) / `pgvector` (prod) |
| File parsing | pypdf, python-docx (+ `docx2python`/OCR fallback for scanned PDFs) |
| Document export | DOCX (python-docx), PDF (WeasyPrint/Typst), Markdown, JSON Resume |
| Storage | Local filesystem behind a storage interface → S3-compatible in prod |
| Package manager | uv |
| Quality gate | Nox → Ruff + `mypy --strict` + pytest |
| Frontend | Angular 22 (`frontend/cv-pal`) |

## Architecture

```
routers/          HTTP edge — validation, auth, response schemas. Thin.
services/         Business logic. Framework-free, no HTTPException, unit-testable.
integrations/     LLM providers, job sources, storage, parsers. Behind Protocols.
repositories/     Data access (introduced where a service needs a fake in tests).
models/ schemas/  SQLAlchemy 2.0 ORM  |  Pydantic v2 wire contracts.
workers/          arq task definitions — thin wrappers over services.
```

Rules: dependencies point inward; services never import routers; every external system
(LLM, job board, storage, parser) sits behind a `Protocol` so it can be faked in tests
and swapped per user. Domain exceptions are raised in services and translated to HTTP
at the edge by exception handlers.

Split by domain once modules grow: `backend/cv_pal/{auth,profile,cvs,jobs,applications,linkedin}/`
each with `router.py`, `service.py`, `models.py`, `schemas.py`.

## LLM strategy

**Provider abstraction.** One `LLMClient` Protocol. The single implementation today is
`OpenAICompatibleClient`, which covers hosted OpenAI, Ollama, and every gateway that
speaks the same wire format — LM Studio, vLLM, OpenRouter, Together, Groq — since the
only difference is the base URL and credential.

**Anthropic was added in session 23** through its own SDK, not an OpenAI-compatible
gateway. The shim would have cost the two things this codebase depends on: native
structured output, and the `refusal` stop reason that separates "the model declined" from
"the model produced garbage" — `review_service` retries once on unparsable output, and
retrying a refusal only spends tokens reaching the same answer.

It landed as predicted: one class and one enum member behind the existing Protocol, with
no caller changes. Two things that would have been silent failures without reading the
current API docs rather than working from memory — **current Claude models reject
`temperature`, `top_p` and `top_k` outright** (a 400, not a degraded response), so a
shared LLM config must not forward them; and a refusal is a **successful HTTP 200** with
an empty body, so `content[0]` without a `stop_reason` check raises `IndexError` on a
normal outcome. Both are pinned by tests.

Still deliberately not done: passing a JSON schema through the Protocol so Claude's
native structured output can be used. That is a change to every implementation, and the
prompts already demand JSON with a validating retry behind them.

**Configuration is per user, not per deployment.** Server-level settings are only the
default. A user can register their own provider + model + API key + base URL, stored
encrypted at rest, and choose a model *per task* (e.g. a cheap local model for keyword
extraction, a stronger hosted one for CV rewriting).

**Local-first path.** Ollama is a first-class provider, documented end to end: install,
`ollama pull <model>`, point `CV_PAL_LLM_BASE_URL` at `http://localhost:11434/v1`. A
"local only" toggle refuses to send data to any hosted endpoint, so the whole product
works air-gapped. Recommended local defaults are shipped as constants and validated at
startup by probing `/api/tags`.

**Structured output.** All LLM calls that feed the database request a JSON schema
(native structured output where the provider supports it, schema-in-prompt plus
validation retry where it does not — local models frequently need this). Responses are
parsed into Pydantic models; a validation failure retries once, then fails the task
loudly rather than writing garbage.

**Operational concerns.** Prompts live in versioned template files, not inline strings,
and every stored LLM output records `provider`, `model`, `prompt_version` so results are
explainable and re-runnable. Token usage and estimated cost are recorded per user per
task, with an optional budget cap. Calls are async, rate-limited, retried with backoff,
and cached by content hash (re-analysing an unchanged CV costs nothing). PII redaction
runs before any hosted call when the user enables it.

**Quality.** A small golden set of CVs and job descriptions with expected outputs runs
as an offline eval so prompt changes and model swaps can be compared, not guessed at.

## Password policy

Aligned with NIST SP 800-63B, which is deliberately the opposite of the folk wisdom
about special characters.

**Rules:**

- **Minimum 12 characters.** Length is the only property that reliably buys entropy.
- **Maximum 72 *bytes*, not characters.** bcrypt operates on 72 bytes and modern
  versions raise rather than truncate, so an unbounded field turns a long passphrase
  into a 500. UTF-8 means a 30-character password can exceed 72 bytes, so the limit is
  measured after encoding.
- **Screen against a common/breached password list.** "Password123!" satisfies every
  composition rule and is worthless. The check is local (a bundled list) so it works in
  `local_only` mode; an optional Have I Been Pwned k-anonymity lookup can be enabled
  where sending a hash prefix is acceptable.
- **Reject context-specific values** — the user's own email or its local part, the
  application name, and simple variations of them.
- **No forced composition rules going forward.** NIST advises against mandatory
  digit/symbol requirements: they push users toward `Passw0rd!` patterns and reduce
  real entropy. The existing "must contain a digit" check is retained for now because
  removing a check is a regression until the blocklist is in place; it should be dropped
  once screening is live.
- **No silent truncation, no maximum-length theatre, no periodic forced rotation, and
  no password hints or knowledge-based recovery questions.**

**Hashing: argon2id**, at the OWASP-recommended 19 MiB / 2 iterations / 1 lane. The
encoded hash carries its own parameters, so bcrypt and argon2id coexist: legacy hashes
still verify, and any hash whose algorithm or cost is out of date is replaced during the
one moment the plaintext is available — a successful login. Raising the cost parameters
later therefore needs no migration, only a redeploy.

Because argon2id has no 72-byte input limit, the length ceiling exists purely to stop
someone posting a megabyte of text at the hasher.

**Adjacent hardening:** rate limiting and lockout backoff on `/auth/login` are done —
per-client throttling plus exponential per-account backoff, counted for any submitted
address whether or not it exists, so lockout cannot be used to enumerate accounts. The
unauthenticated path also hashes a dummy password when no account matches, so a missing
account is not measurably faster than a wrong password.

**Sessions:** refresh tokens are opaque random strings, stored only as a SHA-256 hash,
and are single-use — each refresh revokes the presented token and issues a replacement.
Presenting an already-revoked token revokes *every* session for that user, on the basis
that the legitimate holder and a thief cannot both have spent the same one-time token.
`/auth/logout` ends one session; `/auth/logout-all` ends them all.

The pair is returned in the response body rather than set as an `HttpOnly` cookie. That
follows from the API being bearer-token OAuth2 consumed by a separately-served SPA, and
it trades XSS resistance for simplicity and CSRF-freedom. Worth revisiting if the
compose deployment ends up serving the frontend and API from one origin, where a cookie
would be strictly better.

**Credential changes re-authenticate** (session 32). `PATCH /users/me/password` and
`DELETE /users/me` both require the account's current password alongside the bearer
token. A token proves a session was opened by the account holder at some point; it does
not prove the person holding it now is them, and these are the two requests where that
difference is the entire security model — one takes the account permanently, the other
destroys it. A password change then revokes **every** session, the caller's included: one
that leaves the thief's refresh token working has changed a string and nothing else.

### No password-reset email, and why that is the answer rather than a gap

There is no signed-out reset flow, and this is a decision rather than an omission.
Sending a reset link needs an SMTP server, which a self-hosted instance frequently does
not have — so the honest options were a "forgot password" link that silently cannot
deliver, which is precisely the control-that-does-nothing this project refuses to ship,
or a mandatory mail configuration on an application whose whole premise is that it runs
on your own machine with nothing else set up.

Recovery is therefore offline: `python -m cv_pal.admin reset-password <email>`, prompting
for the new password so it never reaches the shell history. It grants no access an
attacker would not already have — running it needs shell access to the machine holding
the database, and anyone with that can read the SQLite file — and it works with no
infrastructure at all. If a deployment does have mail, an emailed reset becomes worth
adding on top; it is not worth requiring underneath.

## Frontend mock mode

**Built in session 2**; the how-to-run detail lives in [development.md](development.md).
The decisions worth keeping:

- **Fixtures are version-controlled TypeScript** under `frontend/cv-pal/src/mocks/`,
  typed against the same `shared/models/api.model.ts` interfaces the real services
  consume — so a backend contract change that breaks the fixtures fails the type check
  rather than surfacing at runtime.
- **An unmapped route returns a 404 and logs a warning.** A missing fixture must be loud;
  silently falling through to the network would defeat the point.
- **Mock mode is never a fallback for a failing API.** The interceptor is registered only
  when `environment.useMocks` is true, so in every other build it is not in the chain at
  all and real errors surface as real errors.
- **Fixtures show imperfect data on purpose** — unevidenced skills, a parseability
  warning, a coverage score in the forties. A demo that only ever shows a clean result
  teaches nothing and hides the features that exist to surface problems.

## Application quality gate

**Recorded in session 14.** Nothing outward-facing leaves the system without passing this
gate. It runs identically whether a human pressed the button or a rule set did:
**automation skips the reviewer, never the checks.**

The gate is almost entirely deterministic, per principle 1 — reproducible, explainable
line by line, free to run, testable against fixtures, and fully functional with no LLM
configured. That is also what makes it credible: a quality claim enforced by a model is
a quality claim that changes when the model does.

### The checks

| Check | Verdict | What it protects |
| --- | --- | --- |
| **Grounding** — every claim in the outgoing document traces to a profile fact | Block | The user having to defend an invention in an interview |
| **Non-negotiables** — the posting breaks something the user marked non-negotiable | Block | Applying for work they would refuse |
| **Match floor** — score below the rule set's minimum | Block | The spray-and-pray the guarantees rule out |
| **Duplicate** — same company and role already applied to or still open | Block | The single most embarrassing automation failure |
| **Caps** — daily, weekly, per-company | Block | Volume creeping back in by accident |
| **Data completeness** — contact details present, and any answer the form demands (authorisation, notice period, expectation) filled and not placeholder text | Block | An application binned for a blank field |
| **Parseability** — the export survives text extraction, sections are detectable, dates are machine-readable | Block on hard failure, warn on soft | An ATS silently dropping half the CV |
| **Missing required keywords** — a hard requirement the profile cannot evidence | Warn, naming the gap | Wasting an application on a role the user cannot yet reach |
| **Specificity / filler / stuffing / self-similarity** | Warn | See below |

A warning is shown, recorded on the application and passed through. A block stops the
send and names the one thing to fix. In review mode a user may override a warning; **no
one may override a block** — a gate whose blocks are advisory is decoration.

Most of these are buildable now, against the analysis core that already exists, before
any job source or connector does. That makes the gate an unusually good next piece of
work: it is the actual product difference, and it has no upstream dependency.

### "Will an ATS flag this as AI?" — the honest version

The research note asked for a check that an application "is not detected as AI spam by
ATS". Taken literally that cannot be built, and it is worth recording why rather than
quietly shipping something adjacent and calling it done:

- **Applicant tracking systems overwhelmingly do not run AI-text detectors.** They parse,
  match keywords and rank. The judgement about whether writing feels machine-made is made
  by a human, later, and often without them naming it.
- **The detectors that do exist are unreliable in the way that matters most here.** They
  systematically over-flag non-native English speakers and anyone whose style is plain
  and unadorned. A check built on them would penalise precisely the users this project
  says it exists for — see *Accessibility is not optional*, which is the same argument.
- **It is an unobservable, moving target.** Any score would be a number the product could
  not defend, in a product whose entire position is that its numbers are defensible.

So the check is inverted. Instead of *does this look machine-written*, the gate asks
**does this look written for this job** — which is measurable, is what a reader actually
reacts to, and is equally true of good human writing and good machine writing:

- **Specificity.** Count the bullets with no figure, no named system, no artefact and no
  scope. A document made mostly of those reads as generic whoever wrote it.
- **Filler density.** A bundled list of phrases that survive their own deletion —
  "results-driven", "passionate about", "proven track record". Local, so it works in
  `local_only` mode.
- **Self-similarity.** Shingled similarity of this letter against the user's own recent
  ones. **This is the strongest signal available and it is available to nobody else:**
  only a tool holding the whole application history can see that the last ten letters
  were 92% identical. That is spray-and-pray by definition, whatever produced the text —
  and it is the check that most directly enforces the position in *What the market
  already sells*.
- **Posting specificity.** Does the letter contain anything true only of this company and
  this role.
- **Stuffing.** Keyword density above a natural range — the decade-old ATS-gaming trick,
  which now reads as spam to the human who opens it next.

**The rule that follows, and it is not negotiable:** the system never optimises for
evading detection. If a check could be satisfied by making text vaguer, by disguising
authorship, or by any change that does not *also* make the application more true or more
specific, it does not belong in the gate. The goal is applications that are genuinely
worth reading, not applications that pass for them.

### Review mode

**`review_mode` is an account preference, on by default.** Before anything is sent, the
user sees the document exactly as it will arrive, the diff against their base CV with the
profile fact behind each change, every form value, the destination, and the gate's
verdicts.

Turning it off is deliberately not one toggle:

- **Per source and per rule set, never global.** The risk differs entirely by destination.
- **It unlocks only after that rule set has produced applications the user approved
  without editing them** (default five). An unproven rule set has not earned unattended
  operation, and the product should not pretend otherwise by offering the switch on day
  one.
- **Disabling states what changes in plain language and takes a typed confirmation**, not
  a checkbox. This is the warning the research note asked for, positioned where the user
  is actually making the decision rather than in a settings tooltip.
- **Authorisation expires on material change.** Editing the rule set, the base CV, the
  goals, or the profile re-arms review mode for that rule set. The user approved a
  *pattern* of applications; when the pattern changes, the approval does not carry. This
  is the clause that makes unattended mode defensible at all.
- **The kill switch, the dry run and the audit log exist in both modes**, and blocking
  checks block in both.

That is the reconciliation of principle 5 with a preference the user can switch off:
consent stays explicit, it is simply granted once for a bounded, proven, revocable
pattern instead of per send.

## Domain model

- **User** — account, settings (including `review_mode`, on by default), LLM provider
  configs, budget.
- **CareerProfile** — the master record: contact info, summary, links.
- **CareerGoals** — what the user is actually looking for, one record per user: target
  roles and level, direction (step up / lateral / pivot), work regime as an ordered
  preference rather than a boolean, commute ceiling, compensation floor *and* target,
  contract types, company size and stage, industries to avoid, and the *more of / less
  of* work-content axes. Every field is either a **non-negotiable** (filters) or a
  **preference** (scores, with the reason stated). Deliberately one record feeding both
  Phase 7 matching and Phase 12 path planning — the same question answered twice in two
  screens is how the two end up disagreeing.
- **Experience / Education / Project / Certification** — structured, dated facts.
- **Skill** — normalised name, category, proficiency, years, evidence links to
  Experience rows. Normalisation against a taxonomy (ESCO/O*NET-derived) so "JS",
  "JavaScript" and "ECMAScript" collapse to one skill.
- **CVDocument → CVVersion** — every generated or uploaded CV is an immutable version
  with a diff against its parent, the job it targeted, and the model that produced it.
- **Suggestion** — typed (content / structure / keywords / gap), with severity, the
  profile fact it is grounded in, and accept/reject/applied state.
- **JobSource** — a configured connector (ATS board, aggregator API, RSS, manual paste).
- **JobPosting** — normalised posting: title, company, location, remote flag, salary
  band, seniority, extracted skills, raw description, source URL, content hash.
- **SavedSearch** — query + filters + schedule; drives automated runs.
- **JobMatch** — posting × profile score with a deterministic component, an LLM
  rationale, and the gaps it identified.
- **Application** — status timeline (queued → applied → screening → interview → offer /
  rejected), the exact CV version and cover letter sent, follow-up reminders, and the
  *Application quality gate* verdicts recorded as they stood at send time, including any
  warning the user chose to override.
- **LinkedInProfile** — imported snapshot, section-level review, gap analysis.
- **AutomationRun / AuditLog** — what ran, what it changed, what it sent, dry-run flag.

## Phases

### Phase 1 — Project skeleton + auth ✅
FastAPI structure, health endpoint, JWT register/login, SQLAlchemy + Alembic, Nox + Ruff.

### Phase 2 — CV management ✅
Upload PDF/DOCX, per-user versions, delete with file cleanup.

### Phase 3 — AI-powered CV review ✅
Analyse CV, generate suggestions, accept/reject. Multi-provider LLM config (OpenAI /
Ollama / custom base URL) landed here.

### Phase 4 — Foundations hardening ⬅ **in progress**
Before building further, make the base safe and scalable. Batch A is done (see
`PROGRESS.md`): async correctness, Alembic owning the schema, service layer + domain
exceptions, `Annotated` dependencies, upload hardening, ownership enforced in queries,
`mypy --strict` and pytest as blocking Nox sessions.

Done in batch B: the *Password policy* section in full — 12-character minimum,
common-password screening, context-value rejection, argon2id with rehash-on-login, and
per-client rate limiting with per-account lockout backoff on the auth endpoints.

Done in session 32: re-authentication before credential changes, account deletion with
its files, and offline password recovery. See *Password policy*.

Remaining:
- Per-user encrypted LLM provider configuration, with token and cost accounting.
- Structured logging with request IDs and a consistent error envelope.
- Storage behind an interface (local filesystem now, S3-compatible later).
- Move the rate limiter to Redis when the job queue arrives — the in-process
  implementation multiplies the effective limit by the worker count.

### Phase 4b — Frontend mock mode ✅
Done in session 2. Implements the *Frontend mock mode* section: `mock` build configuration, conditional
interceptor, typed JSON fixtures, in-memory mutation store, latency and error injection.
Sequenced here because it unblocks all UI work from backend availability, and every
later phase ships UI.

### Phase 4c — Release readiness ⬅ **in progress**
Everything the repository needs before it can be published. None of it is user-facing
work, and all of it is cheap now and expensive later. Detail in *Documenting it as open
source* and *Packaging: how people actually run it*.

| Deliverable | State |
| --- | --- |
| Refresh tokens with revocation, finished **first** per *Consequences for engineering standards* | ✅ session 6 |
| **Tier 1 packaging** — `docker compose up` bringing up backend, frontend and database with migrations applied, Ollama as an opt-in profile, named volumes | ✅ session 32 — **built and run for the first time**; `start-cv-pal.cmd` wraps it for Windows |
| **CI** running `nox` and the frontend tests on every push, with a status badge | ⚠️ workflow written; runs nowhere until the GitHub mirror exists |
| **`SECURITY.md`**, **`CONTRIBUTING.md`**, **`CODE_OF_CONDUCT.md`** | ✅ |
| **`docs/self-hosting.md`** — install Docker, copy one file, run one command; no `uv`, no `npm`, no Python | ✅ |
| Licence referenced from the README (MIT, committed) | ✅ |
| Issue templates under `.github/ISSUE_TEMPLATE/` | ❌ |
| **`docs/architecture.md`** — the layering, the seams, and why | ❌ |
| **Public demo** — the mock-mode static build deployed, linked from the README | ❌ |
| **README to the running order** in *The README, in order* | ◐ structure is right; the screenshot and demo link are still `TODO` comments, and both are blocked on the demo being deployed |

**One ⚠️ row left.** Both were claims the repository already made and had never executed.
The packaging half closed in session 32 — the images build, the backend reaches healthy,
the frontend serves, and the instructions in `docs/self-hosting.md` are now instructions
someone has followed. `CONTRIBUTING.md` still says CI runs the same commands as `nox`,
and CI has still never run, because the only remote is self-hosted. Untested instructions
are worse than absent ones.

**What running it actually taught**, recorded because none of it was visible from the
compose file:

- **`host.docker.internal` deserves to be a documented option, not a workaround.** On a
  machine with a GPU and models already pulled, the `ollama` profile is the *worse*
  choice: the container is CPU-only on Windows without WSL passthrough, and it downloads
  its own copy of every model into a separate volume. `extra_hosts: host-gateway` on the
  backend makes pointing at the host's own Ollama work on Linux too.
- **The one-command promise was two commands and a text editor.** Generating a secret
  key with `openssl` is not a thing a Windows user has, and the failure mode for
  forgetting it is a container that restart-loops. The launcher generates it.
- **A model named in `.env` that is not installed fails at the first analysis**, not at
  start-up, because nothing probes the provider. The launcher checks; the backend still
  does not. See *LLM reachability* in the outstanding work.

### Phase 4d — Installable PWA (Tier 2)
Web manifest, service worker, offline shell. Lets the app be installed on a phone
against the user's own instance, with no app store and no second codebase. Small, and
it makes "use it on my phone" true for most people without any of the Tier 3 work.

### Scope for a public v1.0

Depth over breadth. A complete, defensible loop is worth more than broad partial
coverage, both to a real user and to a reader assessing the work:

**In scope:** career profile and goals (Phase 5) → ATS and keyword optimisation plus the
*Application quality gate* (Phase 6) → tailored CV generation and export (Phase 8) → job
sources, rules and application automation (Phase 7) → application tracking and reply-rate
analytics (Phase 9) → LinkedIn import and review (Phase 10).

> **Corrected in session 14.** Phase 9 was absent from both the in-scope and the deferred
> list while Phase 7's own interface description included "Sent — the application tracker
> with status and follow-up reminders". It was never optional: automation that cannot say
> what happened to what it sent is not something anyone should switch on. Its analytics
> half is load-bearing for a second reason — reply rate per variant and per source is the
> only evidence that quality beats volume, and asserting that without measuring it would
> be the same move the volume tools make.

**The order is a dependency chain, not a ranking.** Automation is what the product is
*for*, but it is only worth having if what it sends is good: auto-applying with an
untailored CV is exactly the spray-and-pray the guarantees rule out. So the profile
comes first because tailoring needs structured facts, tailoring comes before automation
because automation sends the tailored output, and the deterministic scoring comes early
because it is what decides whether a role is worth applying to at all.

**Still deferred:** notifications and insights (Phase 11), and everything under *Later*.

**Sequencing note (session 14).** The quality position adds weight to work that was
already planned; it must not pull Phase 7 forward. The parts of it that are cheap and
buildable now — the goals questionnaire and most of the *Application quality gate* — sit
in Phases 5 and 6 precisely because they need no connector, no job source and no LLM.
The order does not change: finish the frontend's move to the real API, close Phase 5,
then build the gate against the existing analysis core. Building submission rails before
there is anything worth submitting is how the plan grows a twelfth phase and no product.

Job-board connectors carry real maintenance cost — they break when sites change — so
they are built behind one interface, with the manual-paste path always available as the
fallback that cannot break.

### Phase 5 — Career profile (master CV) ⬅ **in progress**

The source of truth every generated CV is rendered from — what makes tailoring possible
without fabrication.

| Piece | State |
| --- | --- |
| Domain model, migration, CRUD, skill-evidence link (`career_profiles`, `experiences`, `educations`, `skills`, `skill_evidence`) | ✅ session 10 |
| Read-only screen — experience timeline, education, skills by category with evidence state, readiness list | ✅ session 13 |
| Screen wired to the real `GET /profile` instead of a seeded signal, with loading and error states | ✅ session 14 |
| `CareerGoals` model, migration and `GET`/`PUT /profile/goals` | ✅ session 15 |
| **Editing from the interface** | ✅ session 20 — edit the profile fields, add and remove roles, education and skills |
| A screen that asks the goals questions | ✅ session 21 — `/goals`, wired to `GET`/`PUT /profile/goals` |
| **A guided first run** — explain, then the CV, then what the CV could not say, then goals | ✅ session 32 — `/welcome`, entered automatically on an empty account |
| **A drafted summary from the profile's own facts** (`POST /profile/summary`) | ✅ session 32 — proposes, never writes; refuses an empty profile before calling the model |
| **Extraction from an uploaded CV** into Experience/Education/Skill records, user confirms | ✅ session 19 — deterministic, `POST /profile/import-from-cv/{cv_id}` |
| A screen to review and confirm what extraction proposed | ✅ session 20 |
| LLM enrichment of what the deterministic pass could not read | ❌ |
| Projects and certifications | ❌ |
| Import from JSON Resume | ❌ |
| Skill normalisation and deduplication beyond the current alias map | ❌ |

**Closed in session 20.** A new account can now fill the profile in: upload a CV on the
analysis screen, read it on the profile screen, and add the rows that are right. That is
the first complete loop in the product — a file goes in, a structured record comes out,
and the readiness score moves.

**Also here: the goals questionnaire** (`CareerGoals`, added session 14). It belongs in
this phase rather than in Phase 7 because it is part of describing yourself, not part of
configuring a search — and because the profile screen is where a user is already in the
frame of mind to answer it. Every question is asked once and read by three things: match
scoring (Phase 7), the *Application quality gate*'s non-negotiable check, and career path
planning (Phase 12). Small, entirely deterministic, no LLM, and it can be built before
any job source exists.

The one design point that matters: **each answer is explicitly a non-negotiable or a
preference.** Collapsing that distinction is what turns a search into a filter that
returns nothing, or into a score nobody can act on.

**Backend implemented in session 15** — `career_goals`, migration `e5f6a7b8c9d0`, and
`GET`/`PUT /profile/goals`. Deliberately only the core the *Open decisions* entry names:
target roles, work regime as an ordered preference, and a salary floor with its currency,
each paired with its non-negotiable flag. **Deferred until something reads them**:
direction (step up / lateral / pivot), commute ceiling, contract types, company size and
stage, industries to avoid, and the *more of / less of* work-content axes. Phase 7 has no
backend, so every one of those would be a column with no reader — and the shape they
should take is better decided against a matcher that exists.

Two rules worth keeping from the implementation:

- **`PUT`, not `PATCH`.** The goals form is edited whole, so an omitted preference means
  the user cleared it. Under a merge there is no way to remove a salary floor without
  inventing a delete endpoint for one field.
- **A non-negotiable with nothing behind it is rejected at the edge.** "Regime is
  non-negotiable" with no regime chosen filters out every posting and gives the user no
  way to see why. Refusing it is cheaper than explaining a permanently empty result list.

### Phase 6 — ATS & keyword optimisation ⬅ **partly built**
Deterministic core **implemented** in `backend/cv_pal/analysis/` (session 8): keyword
extraction with required/preferred detection, alias-aware coverage scoring, and the
mechanical parseability checks. **The endpoints exist too** —
`POST /analysis/cvs/{id}/ats-check` and `POST /analysis/cvs/{id}/coverage`, both verified
against a running server in session 14 and both working with no model configured.

**The screen landed in session 18**: `/analysis` — choose or upload a CV, paste a
posting, get the parseability report and the ranked missing-keyword list. It is the first
part of the product that is useful on a fresh install, because none of it needs a model.

The grounded-rewriting half followed in session 30 — see Phase 8, where transforms 1 and
2 are built and gated on the alias map. What remains here is the *Application quality
gate* checks below, and the bullet-strength and readability measures. Of those, only
self-similarity exists (`analysis/similarity.py`, session 30, used to warn on a cover
letter); specificity, filler density, stuffing and posting specificity are not written.

**Vocabulary defects found by running it against a real CV** (session 18), both fixed:
the extractor reported a posting's own recruiting prose — `hiring`, `engineer`,
`experience` — as missing required skills, and every multi-word phrase also leaked its
component words, so `full stack` additionally produced `full` and `stack`. The first is a
`JOB_POSTING_BOILERPLATE` list; the second is a subsumption pass. Both are the kind of
defect that only a real document exposes: the curated test fixtures never contained
recruiting boilerplate.
- **Parseability check** (deterministic): does the exported file survive text
  extraction, are sections detectable, are dates machine-readable, are there tables /
  columns / images / headers that ATS parsers drop.
- **Keyword coverage**: extract required and preferred keywords from a job description,
  match against the profile with synonym/taxonomy awareness, report coverage as a score
  with the missing terms ranked by impact.
- **Grounded keyword injection**: rewrite existing bullets to surface keywords the user
  genuinely has evidence for; anything else is reported as a gap, never inserted.
- Readability, bullet strength (action verb + scope + measurable result), length and
  tense consistency checks.
- The **specificity, filler and stuffing** measures from the *Application quality gate*
  live here too — they are the same deterministic machinery, and they are useful on a
  plain CV review long before any application is automated.

#### The three permitted transforms, and nothing else

**Recorded in session 14**, from the research note's request to "replace existing similar
words so it matches the needs of the company, always keeping it true to the CV". The
intent is right and the literal reading fabricates, so the boundary is drawn explicitly:

1. **Surface** — a fact already in the profile that this CV version omitted is included
   because the posting asks for it. A *selection* change, not a rewrite: the safest of
   the three, and usually the most effective.
2. **Substitute within an equivalence class** — the posting's term replaces the user's for
   the same thing, where the alias map asserts they are the same: `Postgres` →
   `PostgreSQL`. **Never across classes.** A posting asking for Oracle does not turn
   Postgres experience into Oracle experience, however similar the two look.
3. **Rephrase** — the posting's vocabulary and register, with the underlying claim and its
   evidence unchanged.

Anything a posting asks for that none of the three can reach is a **gap**: named, ranked
by what it costs in match score, never written into a document.

**This puts the alias map on the safety path, not merely the scoring path** — and that is
the non-obvious consequence. Substitution is only safe because something authoritative
says two terms mean the same thing. Today that something is 37 hand-curated software
terms (see *Known limitation*). Outside software there is no equivalence data at all, so
transform 2 must be **disabled** for those users rather than approximated: guessing that
two nursing or accountancy terms are synonyms is a fabrication with a job attached.
Adopting ESCO or O\*NET therefore stops being a quality improvement and becomes a
**dependency of automated tailoring for any occupation outside software**.

### Phase 7 — Job sources, rules and automated application

The user-facing shape is one screen: **set your rules once, and the system finds
matching roles, tailors a CV for each, and moves them towards submitted** with as much
automation as each source safely permits.

**Match rules** (deterministic, user-defined): target titles and seniority, must-have
and nice-to-have skills, exclusions, location and remote policy, salary floor, company
allow/block lists, posting age, and a minimum match score below which nothing is ever
auto-submitted. Rules run as a filter; the LLM only writes the rationale.

**Rules are derived from `CareerGoals`, not maintained separately** (session 14). The
goals record already holds the targets, regime, floor and non-negotiables; a rule set
starts as their mechanical projection and the user then narrows it for a particular
campaign. Asking the same questions twice in two screens is how the answers end up
disagreeing, and it is also what makes automation feel like configuration rather than
like being helped.

**Sources**, tiered by what they permit:

**Built in session 21:** the posting store, deduplication, deterministic scoring against
goals, paste, and link import for Greenhouse and Lever. Not built: scheduled collection,
rule sets, the queue and submission. The screen landed in session 22.

**There is deliberately no general URL fetcher**, and it is worth recording as a security
decision rather than a missing feature. Fetching a user-supplied URL from the server is a
request-forgery primitive: on a self-hosted install the API can usually reach the router,
the cloud metadata endpoint, and every other service on the host. Scraping arbitrary
careers pages is also unreliable — it breaks the week a site is restyled. So a link is
accepted only when a sanctioned board recognises it, and it is resolved through that
board's published API rather than by fetching the page. Everything else is refused with a
message pointing at paste, which always works. A test pins the refusal, including for
`169.254.169.254` and `file://`, so the convenience is not quietly added later.

| Tier | Sources | Collection |
| --- | --- | --- |
| A — sanctioned | ATS boards (Greenhouse, Lever, Ashby, Workable, SmartRecruiters), aggregator APIs (Adzuna, JSearch, Arbeitnow, RemoteOK, Remotive), company RSS/JSON | Automated, scheduled |
| B — restricted | LinkedIn, Indeed, Monster, remote.com | User-driven only, see below |
| C — manual | URL import, pasted description | On demand |

**Submission**, tiered the same way. This is the part that needs care:

1. **Auto-submit** — Tier A only, where the source publishes an application API.
   Fully hands-off, subject to the rails below.
2. **Assisted submit via browser extension** — the extension fills the application form
   in *the user's own browser, in their own logged-in session*, and the user presses
   submit. This works on LinkedIn Easy Apply, Indeed, Monster and anything else, removes
   essentially all of the tedium, and is **not** automated access: there is no stored
   credential, no headless session, and a human completes every submission. This is the
   recommended path for Tier B and should be built before any Tier A auto-submit.

   **It is also the sanctioned path, not a cautious substitute for one** (researched in
   session 17). LinkedIn's terms explicitly permit browser extensions that enhance the
   user's *own* experience, provided they do not scrape in violation of clause 8.2 and do
   not send without the user's review. That is a description of this design. The earlier
   wording here framed the extension as the safe compromise available to us; it is
   better than that — it is the one approach that is affirmatively allowed, and the more
   careful commercial tools use it for exactly that reason.

   **Hard constraint that follows, and it is narrower than "a human submits":** the
   extension **fills fields and stops**. It must not synthesise the click, inject scripts
   that bypass normal click handling, or otherwise drive the page as if it were the user.
   Those are the specific fingerprints LinkedIn's detection looks for, so an extension
   that auto-clicks lands in the detected category while still calling itself assisted —
   the worst of both, since it carries the risk of automation and the reduced coverage of
   assistance. The user's real click is the feature, not a formality.
3. **Prepare-only** — generate the tailored CV and cover letter, open the posting, track
   the outcome. The fallback that always works.

**Why not a headless bot for LinkedIn, Indeed and Monster.** All three prohibit
automated access and applying in their terms, and LinkedIn in particular detects and
acts on it. The consequence is not primarily legal — it is that the user's LinkedIn
account is restricted or removed, which destroys the professional network their job
search depends on. Building the capability into a job-search tool would mean the tool's
headline feature is the thing most likely to harm its user. The extension path delivers
the same reduction in effort without that exposure. If this is revisited, it should be
an explicitly user-enabled, off-by-default mode with the risk stated in the interface,
never the default behaviour.

**The risk is worse than this section originally implied** (session 17). Reported
restriction rates for accounts running flagged automation sat near 40% in Q1 2026, and
LinkedIn banned an outreach vendor's company page and founder profiles in March 2026,
cutting off roughly 30,000 users at once. A vendor-level ban is the part worth noting:
the user does not have to be careless to be caught, only to have picked the wrong tool.

**And the competitors are not doing something cleverer here.** A survey of the paid tools
(session 17) found their headline volume comes overwhelmingly from **Tier A** — scanning
company career pages and ATS boards, which needs no session-borrowing at all — plus a
stored answer bank and an LLM for free-text questions. Their LinkedIn story is either the
same review-and-submit extension described above, or a credential-holding bot with the
account risk attached. There is no third technique being withheld from us. What separates
them is breadth of ATS coverage and willingness to trade quality for volume, which is a
product decision rather than an engineering one — and it is the decision *What the market
already sells* declines to copy.

**Rails on every tier**, without exception: a daily and weekly cap, a per-company cap,
dry-run as the default for a new rule set, a mandatory human review of the first
applications a rule set produces, a full audit log of what was sent where and with which
CV version, and a global kill switch.

**Every submission on every tier passes the *Application quality gate* first** — the
blocking checks are not skippable by any mode, and `review_mode` (on by default) governs
only whether a human sees the result before it goes. The gate is where "quality over
quantity" is actually enforced; the caps above only bound the damage if it is not.

**Normalisation & dedupe**: the same role posted to five boards collapses to one, by
content hash plus company/title/location fuzzy match.

**Scoring**: deterministic base (skill overlap weighted by recency and proficiency,
seniority, location/remote, salary band, must-have filters) plus an LLM pass for
rationale and soft-requirement judgement. Every score is explainable — "8/10: matches
6 of 7 required skills, missing Kubernetes".

Per principle 8 the explanation is given **in the user's own terms**, not only the
posting's: a role losing points for on-call frequency or a three-day office week should
say so and quote the preference it is measured against. That is the difference between a
score the user trusts and a number they learn to ignore — and a preference the user can
see costing them matches is one they can revisit, which a hidden weight is not.

**Semantic search** over postings and profile via embeddings, local when in local-only
mode. **Scheduled collection, built in session 24 without a job queue.** A watched board is
synced by an endpoint, and the sync is idempotent by content hash — a board that has not
changed adds nothing. Scheduling is therefore a cron entry or a systemd timer calling it,
which needs no locking and no de-duplication. Adding arq and Redis to a self-hosted
application for one periodic task is a dependency the deployment story does not earn;
revisit when there is work that genuinely needs a queue, such as tailoring a CV per match.

### Phase 8 — Tailored CV generation & export ⬅ **largely built**

Generate a CV version from the profile targeted at a specific posting: select and order
the most relevant experience, rewrite bullets for the posting's language, respect a
page-count budget. Diff against the base CV with a rationale per change, user approves
per change or wholesale. Export to ATS-safe DOCX, PDF, Markdown and JSON Resume.
Templates are user-selectable and deliberately single-column and parser-friendly.
Cover letter and recruiter outreach message generation from the same grounded facts.

| Piece | State |
| --- | --- |
| Selection and ordering against the posting, as semantic blocks | ✅ session 30 — `generation/tailored_cv.py` |
| Markdown, DOCX and PDF renderers over one block model | ✅ sessions 29–31 |
| Transforms 1 and 2 (surface, and substitute within an equivalence class) | ✅ session 30, gated on the alias map |
| Cover-letter draft with the self-similarity check | ✅ session 30 |
| Endpoints: `POST /jobs/{id}/tailor`, `/tailor/docx`, `/tailor/pdf`, `/cover-letter` | ✅ |
| Transform 3 (rephrase into the posting's register) | ❌ — the only one that wants a model |
| Diff against the base CV, approved per change | ❌ |
| Page-count budget, selectable templates, JSON Resume export | ❌ |
| Recruiter outreach messages | ❌ |

### Phase 9 — Application tracking & assisted apply
Kanban-style pipeline with status history, the exact CV version and letter sent per
application, follow-up reminders, response-rate analytics per CV variant and per source
(which template actually gets replies). **Assisted apply**: pre-fill and stage the
application, run the *Application quality gate*, require confirmation to send under
`review_mode`, log everything, hard rate caps, global kill switch, dry-run mode by
default. Fully automatic sending stays opt-in and per-source, only where a source's terms
allow it.

**The analytics half is not decoration** (session 14). Reply rate per CV variant, per
source and per rule set is the evidence for the entire *quality over quantity* position —
without it the claim is exactly the kind of unfalsifiable assertion the volume tools
make. It also closes the loop the product needs to improve: which template gets replies,
which gate warnings correlate with silence, and whether a user's own goals are set
somewhere they can actually be met.

### Phase 10 — LinkedIn profile import and review

The user gives CV Pal their profile and gets back a section-by-section list of what to
improve. The interesting question is *how the profile gets in*, since a LinkedIn URL
cannot simply be fetched.

**Ingestion routes.** User-facing instructions are in
[linkedin-import.md](linkedin-import.md); the engineering consequences are here:

1. **Browser print-to-PDF — the primary route.** Works on every account, takes about a
   minute, and produces a PDF **CV Pal already parses**. The parser must tolerate
   LinkedIn navigation chrome around the profile content, and content the user left
   collapsed will simply be absent — the guide tells them to expand it, and the review
   should say so when a section looks suspiciously empty.
2. **LinkedIn's own "Save to PDF".** Cleaner output, but **availability is
   inconsistent**: LinkedIn removed the option in 2025 and restored it only for some
   accounts, and it mishandles non-English characters. Support it, never depend on it,
   and never make it the only documented path.
3. **Paste.** Always available, but section boundaries are lost, so per-section scoring
   degrades to whole-document scoring. The review must say which mode produced it.
4. **Official data export (ZIP of CSVs).** The richest source — dates, titles and skills
   arrive exact rather than inferred — but LinkedIn takes **up to 72 hours** to produce
   it. Worth supporting for the precise review; useless as the first-run experience.
5. **URL fetch — not implemented.** Automated access under LinkedIn's terms, and the
   account it endangers is the user's own. Recorded so the absence reads as a decision.

**Implementation note:** a LinkedIn PDF is structurally recognisable (contact block,
"Top Skills", the profile URL in the footer). Detecting it on upload means the user does
not have to tell CV Pal what they are giving it — which is most of the convenience a
scraper would have bought, for none of the risk.

The **URL is still worth collecting** — as a stored field for consistency checking and
for the browser extension, which can read the profile the user is already looking at, in
their own session. That gives the "point it at my profile" experience without the tool
fetching anything.

**The review itself** reuses the deterministic analysis core: headline and about-section
keyword coverage against target roles, completeness scoring per section, recruiter-search
keyword optimisation, and a consistency check against the CV profile that flags dates,
titles and employers which disagree between the two. On top of that, an LLM pass for
phrasing suggestions and a skill-gap analysis against the roles the user is actually
matching — with an estimate of what each gap costs in match score.

### Phase 12 — Career path planning

*"Where could this career go, and would I enjoy it there?"* Depends on Phase 5 for the
profile and improves sharply with Phase 7, because the best evidence about a role is the
postings the user has actually matched.

**The output is a graph, not a list.** Nodes are roles; edges are transitions carrying a
feasibility score. From the user's current position, adjacent roles branch out one, two
and three moves ahead, so the shape of the decision is visible — that two paths converge,
or that one is a dead end without a specific qualification.

Each node answers four things:

1. **How far is it from here?** Deterministic, using the existing analysis core: overlap
   between the user's evidenced skills and the role's typical requirements, what is
   missing, and roughly how long that gap takes to close.
2. **What does the work actually involve?** Day-to-day activities, not a job advert.
3. **What does it pay, and is demand rising?** From real postings where available.
4. **What would suit or grate?** The subjective part — see below.

**Grounding, because this advice has consequences.** Someone may retrain for two years
on the strength of it, so invented salary figures or made-up requirements are not a
cosmetic problem. Three sources, in order of trust:

- **The user's own matched postings** (Phase 7) — real salary bands, real requirements,
  real demand, in their actual market. Best evidence, and it is already being collected.
- **An occupation taxonomy** — O*NET (US, public domain) and ESCO (EU, CC-BY) both
  publish occupation tasks, work activities and skill requirements. This is the factual
  backbone for "what the work involves".
- **The model** — narrative only: why people move between these roles, what a transition
  tends to feel like. Never the source of a number.

Every claim carries its provenance in the interface. A figure from postings is labelled
as such; a model-written paragraph is labelled as such. The *never fabricate* principle
applies with more force here than anywhere else in the product.

**"Interesting and boring" is personal, and must be framed that way.** What one person
finds tedious another finds calming. So the product does not label parts of a job boring;
it reports **what the role involves a lot of** — factually, from taxonomy work activities
— and matches that against what the user has said they want more and less of. A single
question set at profile time ("more of / less of: deep focus, variety, people contact,
travel, on-call, ambiguity, routine") turns this from generic advice into something
specific to them, which is the entire value.

That question set is no longer exclusive to this phase: it is part of `CareerGoals`,
collected in Phase 5 and read by Phase 7's scoring as well (session 14). The same answers
that tell a path planner which direction would suit the user tell the matcher which
postings to stop showing them, and there is no version of this where those two should be
allowed to hold different beliefs about what the person wants.

**Why an agent rather than one prompt.** Each node needs several steps — resolve the
role, gather its requirements, compare against the profile, price the gap, then write.
That is a multi-step task with tool use per node, and the results are cached per role so
the graph is built incrementally rather than regenerated. It runs as a background job,
like the other expensive work.

**Non-goals:** no confident predictions about individual outcomes, no "you will earn X",
and no suggesting a path the user's profile cannot support without saying plainly what it
would take to get there.

### Known limitation: the vocabulary is software-specific

Recorded in session 10, because it undercuts the generalist framing. Every one of the
37 skill aliases in `backend/cv_pal/analysis/vocabulary.py` is a software-engineering
term (`k8s`, `postgres`, `react.js`). The analysis machinery is domain-neutral — it
takes the alias map as data — but the data is not. A nurse, teacher, accountant or
electrician currently gets no alias resolution and correspondingly weaker keyword
coverage, and this would not be noticeable to a software engineer testing the tool.

Fixing it is the same work as grounding career paths: adopt ESCO or O*NET, which cover
every occupation, and derive the alias map and known phrases from them rather than
hand-curating. Until then the tool is honestly strongest for software roles, and the
README should not claim otherwise.

**Escalated in session 14.** This was recorded as a quality gap — weaker keyword coverage
for non-software users. It is now also a **safety** gap: *The three permitted transforms*
allows a tailored CV to substitute one term for another only where the alias map asserts
they mean the same thing, so outside software there is no basis for that judgement at
all. The consequence is that transform 2 must be **disabled** rather than approximated
for occupations the vocabulary does not cover, and the taxonomy becomes a hard dependency
of automated tailoring rather than an improvement to it. The alternative — letting a
model decide whether two unfamiliar occupational terms are equivalent — is exactly the
fabrication principle 2 exists to prevent, with a job application attached to it.

### Phase 11 — Notifications & insights
Daily/weekly digest of new matches and stale applications (email, webhook, or in-app),
market insight from the user's own match history (which skills recur in roles they want,
salary distribution, which titles they are competitive for), and a "profile health"
score that decays when the CV goes stale.

### Post-1.0 — Tier 3 serverless local build
The client-side implementation of the API contract described in *Packaging*: WASM
SQLite over OPFS, client-side parsing and export, the deterministic core in the browser,
and an optional model via LAN Ollama, WebGPU or the user's own key. Deliberately
sequenced after v1.0 so the product is proven before it is built a second time. The
Pyodide-versus-parallel-TypeScript-core question is decided here, not before.

### Later
- Interview preparation: likely questions from the JD + the user's own experience, STAR
  answer drafts grounded in profile facts.
- Tier 4 native shell (Capacitor) — only if the serverless build proves itself.
- Multi-language CVs and localisation of formats (EU vs US conventions, photo/no photo).
- Multiple target-role profiles ("backend" vs "platform lead") from one career profile.
- Anonymised/redacted CV export.
- Referral finder: surface people the user knows at a matched company (from their own
  contacts export).
- Browser extension to capture a posting from any site into CV Pal.
- Multi-tenant SaaS mode (org accounts, billing) if this ever goes beyond personal use.

## API surface (target)

```
Auth          POST /auth/register, /auth/login, /auth/refresh, /auth/logout,
              /auth/logout-all                                          [done]
Users         GET /users/me                                             [done]
              PATCH /users/me/password  (re-authenticates, revokes all)  [done]
              DELETE /users/me          (re-authenticates, files too)    [done]
              PATCH /users/me           (the name every CV is headed with)   [done]
              GET /users/me/export      (principle 4's other half)           [done]
Applications  GET/POST /applications, PATCH/DELETE /applications/{id}      [done]
              GET /applications/stats     (reply rate, chase list)         [done]
              GET /applications/unapplied (saved but not applied for)      [done]
LLM config    GET/POST/DELETE /settings/llm-providers, POST /settings/llm-providers/{id}/test
Profile       GET/PATCH /profile, CRUD /profile/experiences|educations|skills  [done]
              PATCH /profile/skills/{id}  (cite the roles that evidence it)  [done]
              POST /profile/import-from-cv/{cv_id}   (proposes, never writes)  [done]
              POST /profile/summary                  (proposes, never writes)  [done]
              GET /profile/skills/evidence-suggestions (proposes, never writes) [done]
              POST /profile/import/json-resume
Goals         GET/PUT /profile/goals                                    [done]
Jobs          GET /jobs (scored), POST /jobs/paste, POST /jobs/import-url,
              DELETE /jobs/{id}                                          [done]
CVs           POST/GET/DELETE /cvs, GET /cvs/{id}/versions, GET /cvs/{id}/versions/{v}/diff
              POST /cvs/{id}/export?format=docx|pdf|md|json
Reviews       POST /reviews/cvs/{id}/analyze, GET /reviews/cvs/{id}/suggestions,
              PATCH /reviews/suggestions/{id}, POST /reviews/cvs/{id}/ats-check
Jobs          CRUD /job-sources, GET/POST /jobs, POST /jobs/import-url, POST /jobs/paste
              CRUD /saved-searches, POST /saved-searches/{id}/run
Matching      GET /matches, GET /matches/{id}, POST /jobs/{id}/match
Tailoring     POST /jobs/{id}/tailor-cv, POST /jobs/{id}/cover-letter
Applications  CRUD /applications, PATCH /applications/{id}/status, GET /applications/stats
              POST /applications/{id}/preflight   (the quality gate, runs before any send)
LinkedIn      POST /linkedin/import, GET /linkedin/review, GET /linkedin/skill-gaps
Automation    GET /runs, GET /runs/{id}, POST /automation/pause
Health        GET /health/live, GET /health/ready
```

## Background jobs

`fetch_saved_search` (scheduled per search) → `normalise_and_dedupe_postings` →
`score_matches` → `notify_digest`. Plus `analyse_cv`, `tailor_cv`, `parse_cv_to_profile`,
`linkedin_review` as user-triggered async tasks. All idempotent, all recording an
`AutomationRun` with inputs, outputs, model used, cost and dry-run flag.

## Data protection

Encrypt user LLM API keys at rest. Store uploads outside the web root with generated
keys, never user-controlled filenames. Full data export and hard delete (files included).
Retention policy for raw job descriptions. Redaction before hosted LLM calls when
enabled. Local-only mode as a hard switch that fails closed.

## Running

See [development.md](development.md) for prerequisites, the full setup and
troubleshooting. The short version, from `backend/`:

```bash
uv sync --extra dev                              # install
cp .env.example .env                             # then set CV_PAL_SECRET_KEY
uv run alembic upgrade head                      # migrate
uv run uvicorn cv_pal.main:app --reload          # dev server
uv run nox                                       # lint + mypy --strict + tests
```

## Environment variables

```bash
# LLM (server defaults; users may override per account)
export CV_PAL_LLM_PROVIDER="openai"          # openai | anthropic | ollama | custom
export CV_PAL_LLM_API_KEY="..."              # not needed for ollama
export CV_PAL_LLM_MODEL="gpt-4o-mini"
export CV_PAL_LLM_BASE_URL=""                # ollama: http://localhost:11434/v1

# Local-only setup (no data leaves the machine)
#   1. install Ollama:  https://ollama.com/download
#   2. ollama pull llama3.1        # generation
#   3. ollama pull nomic-embed-text # embeddings
export CV_PAL_LLM_PROVIDER="ollama"
export CV_PAL_LLM_BASE_URL="http://localhost:11434/v1"
export CV_PAL_LOCAL_ONLY="true"

# Core
export CV_PAL_SECRET_KEY="..."               # required, no default
export CV_PAL_DATABASE_URL="sqlite+aiosqlite:///./cv_pal.db"
export CV_PAL_REDIS_URL="redis://localhost:6379/0"
```

## Open decisions

1. Which job sources to implement first — the ATS boards give clean data, the
   aggregators give volume. *Deferred past 1.0.*
2. ~~Do we want a resume-parsing library as a deterministic fallback for CV → profile
   extraction, or lean entirely on the LLM with user confirmation?~~ **Resolved in
   session 19 — see *Resolved* below.**
3. **How the goals questionnaire is asked.** *Half-resolved in session 15:* the short
   required core it was leaning towards — target roles, regime, salary floor — is what
   the `CareerGoals` backend implements. What remains is only the interface question: one
   onboarding form, or questions asked progressively as matches arrive ("was the commute
   the problem?"). A form gets complete answers but is a wall in front of a new user;
   progressive gets better answers but leaves the matcher under-informed exactly when
   first impressions are formed. Decide when the goals screen is built, not before.
4. **Whether `review_mode` should be disableable at all**, and if so after how many
   approved applications (five is a placeholder). Worth revisiting once there is a real
   application flow to watch; the honest answer may be that unattended submission never
   earns its risk for a tool one person maintains.

### Resolved

- **CV → profile extraction is deterministic first, with the model as an enricher**
  (session 19). The question was framed as "a parsing library as a *fallback*, or lean
  entirely on the LLM". Both were wrong way round: the deterministic pass is the
  **primary**, hand-written in `analysis/extraction.py`, and the model's job is to fill
  what it could not read. No third-party résumé-parsing library — the ones that exist are
  either unmaintained or heavyweight NLP stacks, and the actual difficulty turned out not
  to be language at all but **layout**, which they do not solve either.

  Three reasons the deterministic pass leads:
  - It works on a fresh install with no API key and no Ollama, like the rest of the
    analysis core.
  - It is reproducible and testable against fixtures, so a regression is visible.
  - Extraction feeds the record every generated CV is grounded in. A non-deterministic
    step there is the worst possible place to accept "usually right".

  Either way the output is a **proposal the user confirms**, so the endpoint writes
  nothing — see Phase 5.
- **The public copy lives on GitHub**, mirrored from the self-hosted origin
  (`gitssh.seventhlab.xyz`), decided session 17. Discoverability for a portfolio was
  always the argument; what settled it is that `.github/workflows/ci.yml` is already
  written for GitHub Actions and therefore **runs nowhere today** — the repository has a
  quality gate it never executes, and a README that plans a badge for it. Running CI on
  the existing host would mean rewriting the workflow for a runner nobody browsing the
  project can see. The self-hosted remote stays the origin; GitHub is a mirror plus the
  CI and issues surface.
- **Multi-user from the start**, self-hosted rather than author-hosted. See
  *Intent, audience and distribution*.
- **SQLite for now**, Postgres-compatible code throughout; revisit when semantic search
  needs pgvector.
- **Licence: MIT**, committed at the repository root.
