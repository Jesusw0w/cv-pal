# CV Pal — Progress log

Working memory across sessions. `PLANNING.md` holds the *what and why* (stable);
this file holds the *state* (changes every session).

**Convention:** newest session at the top. Each entry records what changed, what was
verified, what was learned, and what is next. Keep decisions here so they are not
re-litigated; move anything permanent into `PLANNING.md`.

Unqualified paths inside a session entry are relative to the app that entry is about
(`backend/` or `frontend/cv-pal/`); cross-app references are always fully qualified.

---

## Current state

**Phase:** 4 — foundations hardening (items outstanding) · 4c — release readiness
(packaging done, CI outstanding) · 5 — career profile (in progress) · 6 — analysis and
rewriting built, gate not started · 7 — sources and scoring built, automation not
started · 8 — largely built
**Quality gate:** backend `uv run nox` → ruff, `mypy --strict`, pytest, `alembic check`.
Frontend `npx ng test --watch=false` and `npx ng build`.
**Counts, session 32:** backend 331 tests · frontend 50 tests · migrations at
`f3a4b5c6d7e8`.

### Works end to end, through the interface

**Every screen calls the real API.** There is no inline sample data left anywhere in the
frontend — the last of it went in session 18.

| Area | State |
| --- | --- |
| Auth (register / login / me) | Works |
| Frontend auth — login screen, route guard, silent refresh, sign-out | **Session 14** |
| Career profile screen — **editable**, with CV import and confirm | **Session 20** |
| Goals screen — target roles, regime, floor, non-negotiables | **Session 21** |
| Documents — upload, list, delete | Wired to `/cvs` |
| **CV analysis screen** — upload, paste a posting, parseability + coverage | **Session 18**, no model required |
| **CV → profile extraction** (`POST /profile/import-from-cv/{cv_id}`) | **Session 19** — deterministic, proposes only; reviewed on the profile screen since **session 20** |
| AI Tools — run a review, accept or dismiss suggestions | The one screen that needs a model |
| Job search — add a posting, watch a board, sync, scored matches | **Sessions 21–24** |
| Tailored CV with `.docx` / `.pdf` download, and a cover-letter draft | **Sessions 29–31** |
| LinkedIn — import (PDF / ZIP / paste) and section review | **Session 25** |
| Settings | **Session 18** — cut to the account and dark mode; everything else was inert |
| Frontend mock mode, no backend and no account | **Session 2** — `npm run start:mock` |
| Dashboard (actionable), journey-ordered navigation | **Sessions 12–13** |
| **First-run flow** — `/welcome`: explain, upload a CV, keep what it read, then goals | **Session 32** |
| **Summary drafted from the profile** (`POST /profile/summary`) | **Session 32** — proposes only; refuses an empty profile before calling the model |
| **Change password / delete the account**, both re-authenticated | **Session 32** — Settings; offline recovery via `python -m cv_pal.admin` |
| **Amending profile rows in place**, and citing the roles that evidence a skill | **Session 32** — the evidence loop had no way to be completed at all before |
| **`docker compose up`** — the whole stack, one command | **Session 32**, first ever run; `start-cv-pal.cmd` on Windows |

### Hardening done

| Area | State |
| --- | --- |
| Password policy | **Session 2** — NIST-aligned, 72-byte bug fixed |
| Password hashing | **argon2id session 4**, bcrypt upgraded on login |
| Login rate limiting / lockout | **Session 4** — in-process, Redis later |
| Refresh tokens + revocation | **Session 6** — rotation + reuse detection |
| Schema drift gate (`alembic check` in nox and CI) | **Session 16** |

### Not started

| Area | State |
| --- | --- |
| Application quality gate | Planned session 14, still not built — only `similarity.py` of its checks exists |
| Rule sets, queue, submission | Not started |
| Applications: tracking, status timeline, reply-rate analytics (Phase 9) | Done. `applications` table, five statuses, and reply rate over applications old enough to have been answered. No per-transition history table yet — `applied_at` and `status_changed_at` answer everything currently asked. |
| Per-account LLM provider config; token and cost accounting | Not started — configuration is per deployment, in `.env` |
| LLM reachability check | Not started — a model that is not installed fails at the first analysis, not at start-up |
| Structured logging with request IDs; storage behind an interface | Not started (Phase 4 remainder) |
| `GET /users/me/export` | Done. Walks the same loaded account as the delete, so the two cannot drift; uploaded files are downloaded from the documents endpoints rather than inlined. |

### Claims the repository makes that have never been executed

One left, down from two.

| Claim | Reality |
| --- | --- |
| ~~`README.md` and `docs/self-hosting.md`: `docker compose up` is the way in~~ | **Closed in session 32** — built, run, healthy, and wrapped in a Windows launcher |
| `CONTRIBUTING.md`: CI runs the same commands as `nox` | `.github/workflows/ci.yml` targets GitHub Actions and the only remote is self-hosted, so **CI has never run**. Resolved in planning session 17: mirror to GitHub |

---

## Session 32 — 2026-09-06

The containers finally ran, and the documentation stopped lying.

### `docker compose up`, five sessions after it was written

Both images built, the backend reached `healthy`, the frontend served, and
`http://localhost:8080` answered — the first time any of that has happened since the
compose file was written in session 7. `README.md` and `docs/self-hosting.md` have been
telling readers this was the way in for twenty-five sessions.

Nothing in the compose file was wrong. What was wrong was everything around it, and all
three problems were only visible from a cold start:

- **The secret key.** `docs/self-hosting.md` says to generate one with `openssl rand`,
  which a Windows user does not have. Forgetting it produces a backend that restart-loops
  with a pydantic error, explained only in a troubleshooting table further down the page.
- **The model.** `.env` shipped `CV_PAL_LLM_MODEL=llama3`, which was not installed on
  this machine. Nothing checks: `/health/ready` touches the database and stops there, so
  the stack reports healthy and the first analysis 502s.
- **The Ollama profile is the wrong default on a machine that already has Ollama.** The
  container is CPU-only on Windows without WSL GPU passthrough, and pulls its own copy of
  every model into a separate volume. Pointing the backend at the host's install uses the
  GPU and the models already there.

### The launcher

`start-cv-pal.cmd` at the root, two lines, calling `scripts/start-cv-pal.ps1`. A `.cmd`
because Windows opens a double-clicked `.ps1` in Notepad.

It starts Docker Desktop if it is not running and waits for the daemon, creates `.env`
and generates the secret key if it is missing, points `CV_PAL_LLM_BASE_URL` at the host's
Ollama, starts Ollama and checks the configured model is installed, brings the stack up,
waits for the app to answer, and opens it.

`-CheckOnly` runs the preflight and stops. It is both the runnable check on the script's
branching and the thing to run when something is broken, which is why it is a flag rather
than a second script.

**`extra_hosts: host.docker.internal:host-gateway`** on the backend service is the only
compose change. It is a no-op on Windows and macOS and required on Linux, which turns
"point at the Ollama you already have" into a supported configuration rather than a local
hack.

### Three defects the audit turned up

- **`local_only` checked the provider name, not the destination.** Ollama speaks the
  OpenAI wire format, so `provider=ollama` with a hosted `llm_base_url` passed validation
  and would have sent the user's CV to that host — while the README promises it "will
  refuse to contact a hosted provider at all". Now the base URL's host must be a
  private/loopback address, a bare name, or a reserved local suffix. A name test rather
  than a DNS lookup: resolving at import would make start-up depend on the network.
- **The topbar said "Dashboard" on every screen** — a literal string since the layout was
  built. Now read from `data.title` on the route. `data.title` rather than the router's
  own `title`, so the browser tab keeps saying CV Pal.
- **Mock mode 404ed on the two download buttons.** `matchId(path, '/jobs', '/tailor')`
  rejects a trailing segment, so `/tailor/docx` and `/tailor/pdf` fell through to the
  deliberate loud 404 — in the build intended to become the public demo. They now return
  the Markdown as a blob, named `CV (docx demo).md`: building a real DOCX in the browser
  would mean reimplementing `generation/` in TypeScript for a demo button, and handing
  over a file Word cannot open would be worse than the 404.

### The documentation was five rows wrong

`README.md`'s status table listed profile editing, CV import, tailored generation and
export, job sources, and LinkedIn as "not built yet". All five shipped between sessions
19 and 31. `PLANNING.md` contradicted itself on the goals screen — built per the
interface table, `❌` in the Phase 5 table three hundred lines below. `development.md`
said only Career Profile called the API; all eleven screens do.

This is the failure mode of a progress log that is only ever appended to: each session
records what it did, and nothing re-reads the summary at the top. Worth a habit — the
*Current state* section is the one part of this file that has to be re-derived rather
than extended.

### Also fixed

`cv_pal/passwords.py` had a double blank line, so `ruff format --check` failed and
therefore **`uv run nox` failed on committed `dev`**. It would have failed CI too, if CI
ran. One blank line removed.

### The first run, from using it

Feedback from the first real session on the running app, and the most useful kind:
*"I just started and didn't figure out where I should upload the CV."*

Every piece worked. Nobody could find them in the right order. The upload lives on
Documents, the import that reads it lives on Career Profile, and Goals — which decide
what a match even means — was a sidebar entry a new user had no reason to open. The
dashboard, meanwhile, greeted an empty account with six gaps and a 0%.

`/welcome` sequences the three: what this is and why the record matters, then the CV,
then what the CV could not say, then goals. It is not in the sidebar, because it is the
first run rather than a destination; `LayoutComponent` redirects to it when the profile
has loaded (`id > 0`, so never on a request still in flight), is empty, has no
`cv-pal.welcomed` flag, and the user is on `/dashboard` — which is where login lands and
the only route it is safe to redirect away from.

**Each step is the existing screen's service, not a new one.** `ImportPanelComponent` is
embedded as-is, with one new optional `cvId` input so it reads the file the user just
watched themselves upload instead of asking them to pick it out of a list of one. That
input is the whole cost of reusing it.

Two rules the flow keeps: it can be left at any point from any step, because a wizard
that traps someone is worse than no wizard; and nothing is written that the user did not
press a button for.

### Prefilling, and the honest limit of it

The feedback asked for prefill "if possible", and the interesting part was how much
already existed and was being discarded. `extract_profile` has returned
`contact.linkedin_url` and `contact.website_url` since session 19 and the import panel
threw both away — the user was typing back in what the file already said. They are now
offered as Add rows like everything else.

What cannot be prefilled is worth recording too. There is no location and no headline in
an extracted CV, because neither is reliably a labelled field. The wizard **suggests**
the most recent role's title as a headline and its location, in an editable box, and
saves nothing until Save is pressed. A suggestion in a field the user is already looking
at is not the same as writing a guess into their profile.

### `POST /profile/summary`

The third request: an option to generate a summary. Built exactly like
`/import-from-cv` — it **proposes and writes nothing**, and the draft reaches the profile
through an ordinary `PATCH /profile` if the user keeps it.

The part that matters is the guard in front of it. **A profile with no roles and no
skills is refused before the model is called at all** (`EmptyProfileError`, 400). The
only summary that could be written from nothing is an invented one, and an instruction
in a prompt not to invent is a request where this is a rule. The prompt carries the
facts and nothing else: the system prompt holds every instruction, `_summary_facts`
holds every fact the model is permitted to state, and keeping the two apart is what
makes "never state a fact that is not below" checkable.

`complete_validated` moved into `llm.py`, since the ask-validate-retry-once loop now had
two callers and would have drifted. `review_service` is 12 lines shorter for it, and
`LLMClientDep` moved to `dependencies.py` so both routers resolve the same dependency —
which is also the one the tests override.

Verified live against the container and the host's `gemma4:latest`: an empty profile
returns the refusal with `fake_llm.calls == []`'s real-world equivalent (no request
reaches Ollama), and a profile with one role comes back with *"Backend Engineer at
Seventh Lab. Builds FastAPI services for job search functionality and manages the
Alembic-owned schema supporting these services."* — every clause traceable to a field
that was entered. `GET /profile` still reports `summary: null` afterwards.

### The blank page, and the route that was missing

Reported while testing: `/welcome` showed nothing at all. The cause was a tab left open
across the rebuild — an app instance whose bundle had never heard of that path.

**The defect it exposed is that there was no wildcard route.** An unmatched path rendered
*nothing*: no message, no redirect, a white screen indistinguishable from a broken build.
`{ path: '**', redirectTo: '' }` now covers it. This is the navigation rule one level
down again — a destination that leads nowhere is worse than an absent one, and a blank
page is the worst version of it.

Two things found while chasing it:

- **`WelcomeComponent` was not actually lazy.** `LayoutComponent` imported
  `WELCOME_SEEN_KEY` from it, which pulled the whole wizard and everything it imports
  into the eagerly loaded bundle; the "lazy" chunk was a 352-byte re-export stub. The
  constant now lives in `core/first-run.ts` and the chunk is 14 kB where it belongs.
  A one-line import from a component is enough to undo a lazy route silently.
- **The first-run flow had no test**, so a template that threw would have been a blank
  page on the most important screen a new account sees. `welcome.component.spec.ts`
  renders every step.

### Accounts: change the password, or remove the account entirely

Both re-authenticate with the current password rather than trusting the bearer token.
A token proves a session was opened by the account holder at some point; it does not
prove the person holding it now is them, and these are exactly the two requests where
that gap matters — one takes the account permanently, the other destroys it.

`PATCH /users/me/password` then revokes **every** session including the caller's. A
password change that leaves the thief's refresh token working has changed a string and
nothing else.

`DELETE /users/me` removes the account, its profile, goals, CVs, postings and letters —
**and the uploaded files**, which is the part no cascade does: uploads live outside the
database, so a delete that only clears rows leaves someone's CV on the disk. The
collections are eagerly loaded before the delete because the ORM relationships are what
actually cascade here — SQLite does not enforce foreign keys unless asked, so the
`ondelete` clauses in the schema are documentation on this database rather than
behaviour.

**No password-reset email, deliberately.** It needs an SMTP server a self-hosted instance
frequently does not have, and a reset link that silently cannot be delivered is the
control-that-does-nothing rule again. Recovery is
`python -m cv_pal.admin reset-password <email>` — prompted, so the password never reaches
the shell history — which needs no infrastructure and grants no access an attacker would
not already have from being able to read the database file. Reasoned through in
`PLANNING.md` → *Password policy* so the absence reads as a decision.

Dogfooded: the two throwaway accounts left over from earlier testing were removed with
the new endpoint rather than with SQL.

### The evidence loop was closed off, and nobody could see it

Found while answering "what would you say we still miss". The profile screen reported
unevidenced skills as the thing to fix and there was **no way to fix them**: evidence
could only be set when a skill was created, `addSkill({ name })` never sent any, and the
CV importer creates them the same way. There was no `PATCH /profile/skills/{id}`.

The consequences all followed from that one missing endpoint:

- every skill in the product was permanently unevidenced;
- `completeness` could never reach 100 on any account;
- and the generator omits unevidenced skills by design, so **every generated CV omitted
  every skill**.

**Mock mode is why it went unnoticed for so long.** The fixtures ship four skills with
`is_evidenced: true`, so the demo showed a working product the real one could not
produce. A fixture that is prettier than reality teaches the wrong thing — the same
argument PLANNING already makes for showing imperfect data on purpose, applied to a case
it did not cover.

`PATCH` for skills, roles and qualifications closes it. Skills also gained an evidence
picker on the profile screen — the roles as checkboxes, replacing the citation list
rather than merging into it, since un-citing is as ordinary an edit as citing. Roles and
qualifications gained inline editing, so a typo in an employer name no longer means
deleting the row and retyping it, and education gained an add form: until now the only
way to record a qualification was to import a CV.

### Comment pass

`constants.py` and this session's additions were carrying more prose than they earned —
several constants had three lines of explanation above a name that already said it. Cut
to one line where the reason is not obvious from the value, none where it is. The
comments kept are the ones recording something a reader would otherwise undo: the
similarity threshold's measured calibration, Remotive ignoring its own query parameters,
why `local_only` checks the destination and not just the provider name.

### Verified

`uv run nox` — lint, `mypy --strict` (80 files), 331 tests, migrations up/check/down: all
green. Frontend 50 tests, `ng build`, `npm run build:mock`: green, now on the host's
own Node (v26.8.1) rather than in a container.

Against the running containers: a skill starts unevidenced, a role's title is amended
without touching its employer, citing the role flips `is_evidenced` to true, and clearing
the citation flips it back.

End to end against the running containers: wrong current password → 401; correct change
→ 204 and the old refresh token immediately revoked; sign in with the new password →
delete → 204; signing in afterwards → 401.

Both frontend runs happened **in a `node:24-alpine` container**: the host has Node
v24.14.0 and the Angular CLI now requires v24.15.0. Worth knowing before the next
frontend session — the host node_modules was shadowed with an anonymous volume so it was
not overwritten with musl binaries.

---

## Session 31 — 2026-08-08

PDF export, the third renderer over the same block model.

### ReportLab, and why not the other two

The choice was made on the deployment story rather than the API:

- **WeasyPrint** renders HTML and CSS — much the nicest authoring model — and needs
  cairo and pango on the host. A self-hosted app that requires system libraries loses
  exactly the users this project is for.
- **fpdf2** is smaller and LGPL. Importing it is fine, but it puts obligations on anyone
  redistributing, which is friction an MIT project has no reason to take on.
- **ReportLab** is BSD, pure Python, and emits real extractable text — the only property
  that decides whether a parser can read the result at all. Pillow comes with it.

**DOCX stays the format to submit where a portal accepts either**, and the endpoint's
docstring says so: it is structured data a parser reads directly, where a PDF is a page
description it has to reconstruct. The PDF is what a human opens, and what some portals
demand.

### The bug that was worth finding before shipping

`Paragraph` parses its text as a small HTML dialect. A profile containing `C++ &
<legacy>` either renders wrongly or raises mid-build, and **every string here is
user-supplied** — the case where "probably fine" is wrong. Escaped once, at the single
point where text enters ReportLab, with a test that round-trips those characters.

### The strongest test available

The generated PDF is read back with **`pypdf` — the same reader the app uses on
uploads** — and the extracted text is run through the project's **own** parseability
check. Our writer, our reader, our checker. If the renderer ever stops producing
extractable single-column text, the suite says so rather than a user discovering it
after an application disappears.

Verified live: 1 page, correct media type and filename, text extracts in reading order,
parseability 77 with nothing blocking (the two warnings were a missing education section
and length, both true of the test profile rather than defects).

Helvetica only — one of the fourteen fonts every reader has, so nothing is embedded and
nothing is substituted. A subsetted or exotic font is a common reason extracted text
comes back as mojibake.

`reportlab.*` joins `pypdf.*` and `docx.*` in the mypy override list; none ships stubs.

---

## Session 30 — 2026-08-08

Phase 8 continued: the submission format, the second permitted transform, and cover
letters with the check that keeps them honest.

### A block model, because there are now two renderers

The generator produced a Markdown string. Building a DOCX by parsing that back would
make the Markdown a private interchange format, and a formatting change in one output
would silently break the other. So `tailor` now emits **semantic blocks** — `SECTION`,
`ENTRY`, `META` — and Markdown and DOCX are two renderers over one model. `BlockKind`
says *"this names a job"*, not *"make this bold"*, because an ATS reads the DOCX style
name rather than anything visual.

### DOCX, and why each rule is in it

Every rule removes a shape this project's own `analysis.parseability` reports as lost —
which is the point: the generator and the checker have to agree, or the app flags
documents it produced itself.

- **Built-in heading styles**, not bold body text. A parser reads the style name;
  visually-bold Normal text carries no signal at all.
- **Nothing in the header or footer.** Contact details there are the classic way an
  email disappears — many parsers read the body story only.
- **No tables, no text boxes, no images.** Verified by opening the generated file.

**The filename is a security boundary**, and worth calling out. Company and title come
from a third-party job board and end up in a `Content-Disposition` header and then on
the user's disk. A quote or newline there is header injection; a slash is a path the
browser may interpret. `download_name` **rebuilds the name from an allowlist** rather
than removing dangerous characters from it — a denylist is the version that misses one.
A test feeds it `Evil"

X-Injected: yes` and `../../etc/passwd"`.

### Transform 2: the gate is the alias map, not canonical equality

`Postgres` becomes `PostgreSQL`, `K8s` becomes `Kubernetes`, because the posting uses
that spelling and **`SKILL_ALIASES` asserts the two name one thing**.

The non-obvious part is the gate. It is not "do these resolve to the same canonical
form" — coincidence can satisfy that. It is "**did the alias map put them there**". And
that is also how PLANNING's requirement to disable this transform outside software is
met **without an occupation detector and without a special case anywhere**: there is no
equivalence data for nursing or accountancy, so the map asserts nothing about them, so
no substitution ever fires. A profile outside software gets its own words back because
the map has no opinion — which is the same reason it must not guess. A test pins a
phlebotomy profile against a posting shouting `PHLEBOTOMY`, and nothing changes.

Every substituted word is recorded and shown: it is the only text in the document that
is not literally the user's own.

### Cover letters, and the check that had to ship with them

The letter is **a draft made of verified facts, not a finished letter**, and the
interface says so rather than implying otherwise. Every sentence about the user is
copied from their profile; the evidence lines are reused from the tailored CV's
`surfaced` list so the two documents cannot disagree about what the user evidences.

The paragraph that cannot be assembled is left as a bracketed prompt, and
`needs_writing` stays true until it goes. **Handing over a correct skeleton and naming
what is missing is the honest failure mode** — the alternative is generating confident
filler and letting the user discover in an interview that they cannot defend a sentence
they never wrote.

**Self-similarity shipped in the same commit, and that was not optional.** A
deterministic scaffold produces letters that resemble each other, which is precisely
what PLANNING's check exists to surface. Shipping the generator alone would have been
the product doing the thing it says it exists to prevent. On a first scaffolded draft
the number reads high **by construction**, and that is the correct message: *this is
boilerplate so far, make it specific.*

w-shingling with Jaccard: order-sensitive, cheap, and explainable — which an embedding
would not be. It measures the user **against themselves, never against a corpus**, so
there is no model of "human writing" here to be wrong about anyone's style or first
language. It warns and never blocks.

**The threshold was calibrated against measured output, not chosen.** An initial guess
of 60 sat *inside* the repeat band and would have missed the exact case the check exists
for. Measured: two scaffolded letters for different jobs score 57-64; the same letter
with only the company name swapped scores 62; a genuinely rewritten letter scores 0. The
line is now 40, well below the band, with the numbers recorded next to the constant.

`CoverLetter` is stored for one reason that outweighs a table: **the corpus can only be
the user's own letters.** Unique per posting, so saving replaces rather than
accumulates — similarity against earlier attempts at the *same* letter measures nothing.

### Verified end to end against a running server

| Checked | Result |
| --- | --- |
| Transform 2 live | `JS → JavaScript`, `K8s → Kubernetes`, `Postgres → PostgreSQL` |
| DOCX headers | correct media type, `filename="CV - Cardinal Labs - Senior Full Stack Engineer.docx"` |
| DOCX opened and inspected | Title / Heading 1 / Heading 2 styles, **0 tables**, empty header and footer |
| First letter | similarity 0, no warning |
| Second scaffolded letter | **similarity 66, warned** |
| After writing a real paragraph | **similarity 0**, `needs_writing` false |

### Next in Phase 8

1. **PDF export.** DOCX covers most ATS ingest; PDF is what a human opens. It needs a
   new dependency, which DOCX did not.
2. Transform 3 (rephrase) — the first thing here that needs a model, and the first that
   can fabricate. It should not land without the *specificity* and *filler* checks.
3. Templates and the page budget, both of which need a renderer that knows about pages.

---

## Session 29 — 2026-08-08

Phase 8 begins. The app now produces a document, which it never has before — every
screen up to this point diagnosed, ranked or recorded, and none of them made the thing
you actually send.

### One transform, chosen for what it cannot do

Of PLANNING's three permitted transforms, only **surface** is built:

1. **Surface** — a fact already on the profile is brought forward because this posting
   asks for it. Selection and ordering, never new text.
2. Substitute within an equivalence class — not built. It is only safe where something
   authoritative says two terms mean the same thing, and today that is 37 hand-curated
   software terms.
3. Rephrase — not built. It needs a model, and this works on a fresh install.

The reason to start here is not that it is easiest. **It is the only one of the three
that cannot fabricate.** Everything else in Phase 8 — DOCX and PDF export, templates,
page budgets, cover letters — is downstream of having a grounded document at all.

### The grounding invariant, as a test rather than a principle

> Every content string in the rendered document is copied verbatim from a profile row
> or the user's account details.

`test_nothing_is_written_that_the_profile_does_not_say` enforces it. The generator is a
**pure function of a `ProfileFacts` snapshot** — it never sees the ORM, so anything the
snapshot does not carry is something it structurally cannot emit.

**The test was mutation-checked rather than assumed.** Two deliberate regressions were
introduced and both were caught: inventing a summary ("Results-driven engineer with a
proven track record"), and appending a posting term the profile could not evidence to a
role's skill line. A grounding test that cannot fail is worse than no test, so this was
worth the ten minutes.

That is also what makes the *Application quality gate*'s grounding check satisfiable by
construction rather than by inspection afterwards.

### Decisions inside the slice

- **Roles are not reordered.** The spec says "select and order the most relevant
  experience"; reverse-chronological is kept anyway, because it is what parsers expect
  and shuffling breaks the date sequence an ATS uses to compute tenure. Relevance is
  expressed *inside* each role instead — a `Relevant here:` line naming the skills that
  role evidences and this posting asked for, read from `SkillEvidence`. That join was
  always described as "the point of the model"; this is the first thing that uses it.
- **Unevidenced skills are excluded and reported.** A skill no role demonstrates is a
  claim. Dropping it silently would be its own dishonesty — towards the user, who
  cannot see why their CV is missing something they typed — so it comes back named.
- **Gaps are named, never written.** A posting asking for Kubernetes does not put
  Kubernetes on a CV that cannot evidence it. That is the line between tailoring and
  keyword stuffing, and it has its own test.
- **Nothing is stored.** Deterministic and model-free, so recomputing beats keeping a
  copy in step — the same reasoning as read-time match scores. Phase 9 needs the exact
  document *sent* with an application; that is a different record with a different
  lifetime and belongs to the application.
- **The document is ASCII-only.** An en dash and a middot are what a CV normally uses,
  and both are a gamble in text written to be re-encoded to DOCX or PDF and then parsed.
  Ruff's RUF001 flagged it and was right on the merits, not just stylistically.
- **The output is checked by our own parseability checker** before it is returned, and
  the headings are the literal words `EXPECTED_SECTIONS` looks for. Generating what we
  would flag on upload would be the sharpest inconsistency this project could ship.

### Three defects found by reading real output, not fixtures

Tailoring a live Remotive posting produced a gap list reading *"you are missing:
building, built, builders, companies, e.g, experiences, collaboration, a.team"*. A gap
list exists to be acted on, and none of that is actionable.

1. **A structural bug, not a vocabulary gap.** `experience` is boilerplate; `experiences`
   was not, because `canonical` folds a plural only when the singular is a known
   *skill*. So every plural of every boilerplate word leaked — straight into the lists
   users act on. `_is_meaningful` now applies the same fold to the boilerplate set,
   which kills the class rather than the word. (`companies` still needs an explicit
   entry: the fold strips a trailing `s`, and English forms that plural y → ies.)
2. **Recruiting prose**, the same defect class as session 18's `hiring` / `engineer` /
   `experience`. `JOB_POSTING_BOILERPLATE` gained the observed offenders, each with real
   evidence behind it rather than guessed.
3. **The employer's own name.** `A.Team` is indistinguishable from a technology to the
   extractor — but the caller knows, because company is a stored field. It is now passed
   in and excluded.

The gap list is also capped at 12, required first. Forty terms is a wall nobody reads.

### Interface

A **Tailor my CV** action per posting on the jobs screen. The explanation is rendered
*above* the document on purpose: the CV is the easy part to trust and the wrong part to
trust blindly, and what makes it safe to send is seeing that every line traces to the
profile and what the posting wanted that it could not. One result open at a time, tagged
with its posting — two unlabelled documents on screen is how someone sends the wrong one.

### Verified against a live posting

Real account, real profile, a real Remotive posting (*Tech Lead Full-Stack Rails
Engineer*, Mitre Media):

| Checked | Result |
| --- | --- |
| Surfaced | Docker, JavaScript, PostgreSQL — each naming the role that evidences it |
| `Relevant here:` per role | correctly split by `SkillEvidence`, not repeated wholesale |
| Skills order | surfaced first, then the rest alphabetically |
| Unevidenced `Kubernetes` | omitted from the document, reported separately |
| Parseability of the output | 87/100, nothing blocking |
| Same profile and posting twice | byte-identical |

### Next in Phase 8

1. **Export.** Markdown is the content, not a submission format — ATS ingest `.docx` and
   `.pdf`. `python-docx` is already a dependency, as a reader; writing a single-column
   document with it is the smallest real step.
2. The **substitute** transform, limited to the alias map, and **disabled outside
   software** rather than approximated.
3. Cover letters — but they need the *self-similarity* check from the quality gate in
   the same breath, or the product ships the thing it says it is against.

---

## Session 28 — 2026-08-08

The two follow-ons session 27 named. The first was not a feature request — it was a
defect that discovery had just introduced.

### Where you can work, because discovery made its absence harmful

Before there was a discovery source, every posting arrived because the user had gone
looking for it, so the app never had to ask where they were allowed to work. A remote
feed changes that: it returns roles that are remote **and** restricted — `Remote · USA`,
`Remote · Brazil`, `Remote · Canada` — and with no location in the goals those were
scored on skills alone and ranked among the jobs the user could actually take. **The
source got better at finding roles and the ranking got worse at ordering them.**

`CareerGoals` now carries `work_locations` and `location_non_negotiable`, and matching
gained a fourth component. It is modelled on the regime rules exactly, including the
rule that matters most: **a posting that does not say where you must be is never
blocked.** Silence is not evidence, and blocking on it would hide most of the market.
A bare `Remote` names nowhere and counts as silence — without that, a remote-only feed
would read as a country nobody lives in and block everything it published.

**No geography is inferred, and that is the whole design.** The app does not assert that
Portugal is in Europe or that EMEA contains either. It compares the user's own stated
terms against the posting's. This is the same rule PLANNING already applies to the
skills alias map: the project has no authoritative containment data, and approximating
it would silently hide jobs on a guess about the world. So the goals screen asks — a
fact the user knows and we do not — and offers the regional wordings feeds actually use
(`Europe`, `EMEA`, `APAC`, …) as one-click chips, which is a prompt rather than an
inference.

Matching is prefix-based, so `Europe` matches `European timezones`. That over-matches on
shared stems — `India` against `Indiana` is the clearest — and it is accepted knowingly:
over-matching shows a posting the user dismisses in a second, under-matching hides a job
they could have taken.

Weights re-balanced to make room: coverage 0.7 → 0.6, with location at 0.1. Every
existing score moves slightly as a result.

**Two wording defects, both found by looking at real output rather than at tests.**
"Open to europe, european" — the same place matched twice through different inflections,
so a shorter matched stem now suppresses the longer. And `USA` came back as `Usa`,
because the words were being re-cased after folding; place words now carry the spelling
their source used, and only the comparison is case-insensitive. Neither would have
failed an assertion anyone would have thought to write.

### One call to sync everything

`POST /jobs/sources/sync`. The docs have claimed since session 24 that "a cron entry
hitting it nightly is safe", but per-connection sync needs the ids up front — so the
nightly entry was one command per source and a rewrite every time the user watched
another. Now it is one line that survives the watch list changing. The screen uses the
same endpoint for its **Sync all** button.

Declared **before** `/sources/{connection_id}/sync`, because FastAPI matches in order
and the parameterised route would otherwise read `sync` as a connection id and answer
422. A test pins that, and the mock backend needed the same ordering for the same
reason.

Sequential, not concurrent: these are third-party APIs whose terms ask for modest rates,
and a handful of boards gains nothing from parallelism worth looking like a burst to
someone else's server. One unreachable source reports its error in its own result and
the sweep continues.

**Deliberately not built: seeding the category from `target_roles`.** It needs a
free-text-role to category map, which is a guess, and the picker has ten entries — the
one-time cost it would save is smaller than the wrongness it would introduce. The
recurring friction was syncing, and that is what got fixed.

### Verified against a running server and the live feed

Not only through tests. A real account, real goals, the real Remotive feed:

| Checked | Result |
| --- | --- |
| `PUT /profile/goals` with four places | stored and returned |
| Two watched categories, one `POST /jobs/sources/sync` | found 4 + 1, added 5 |
| Same call again | found 4 + 1, added **0** — idempotent |
| `Remote · USA, Canada, USA timezones` | **blocked**, "it requires Canada, USA" |
| `Remote · Americas, Europe, Israel` | ok, "Open to Europe, where you said you can work" |
| `Remote · Europe, UK, Germany, France, European timezones` | ok, no duplicate stems |
| Contract types through the API | `contract`, `full_time` |

No false blocks in the whole feed: every posting ruled out was genuinely USA- or
Canada-only.

### Next up

Phase 8 is now the only thing between a good match list and an application. Nothing in
the app yet produces a document. The narrowest useful version is the **surface**
transform alone — include a fact already in the profile that this CV version omitted,
because the posting asks for it — which needs no alias map, no model, and cannot
fabricate.

---

## Session 27 — 2026-08-08

Job discovery. Until now every route into the Jobs screen required the user to already
know the company: Greenhouse and Lever answer *"what is open at this company"*, and
watching a board meant typing a company slug. There was no way to ask *"what remote
roles exist"*, which is the question a remote search actually starts from — so the
goals a user had filled in only ever re-ranked postings they had already found by hand.

### Remotive, as a third `JobBoard`

It went in behind the existing Protocol, so it reuses the whole path already built:
dedupe by content hash, scoring against goals, the non-negotiable block, `last_error`,
`last_synced_at`. New code is one class, one enum member, one column.

The difference is what `identifier` means. For a company board it is a company; for
Remotive it is one of **their category slugs** (`software-development`, `devops`, …),
because the source is a feed of the whole remote market rather than one employer.

**Its query parameters do not work, and that is load-bearing.** `search`, `category`
and `limit` are all accepted and then ignored — verified 2026-08-08, every combination
returns the identical 33 rows. So the whole feed is fetched and filtered here. The code
deliberately sends *no* parameters: sending them would be cargo cult, and would hide
the day they start working behind an apparently-correct call. A test pins the requested
URL as bare, so a future "optimisation" that adds `?category=` fails loudly.

The category filter reads the slug **out of the posting URL**
(`remotive.com/remote-jobs/<slug>/…`) rather than the `category` field, which carries
the display *name* (`Data and Analytics`) while the categories endpoint publishes slugs
(`data`). The URL already has the slug, so this avoids a second request for a
name-to-slug map that would then have to stay in step with theirs.

Attribution is a requirement, not a courtesy — their terms ask for a link back and a
mention of Remotive as the source. Both fall out of storing their `url` as
`source_url`, which the screen already links and labels, so the obligation is met by
the normal path and cannot be forgotten. An entry with no URL is dropped rather than
stored unattributed. Their terms also ask for at most a few calls a day, which one
manual sync per watched category is comfortably inside.

### The contract type, and one enum instead of two

Remotive states `job_type`; Greenhouse and Lever do not expose it at all. That asymmetry
is the whole design of the column: **nullable, never defaulted**. "Not stated" and "full
time" are different answers, and backfilling one into the other would invent the
commonest contract for most rows. The feed's own empty string maps to null, as does any
value not in the enum.

`EmploymentType` already existed for how a role was *held* on the career profile, with
the same six values. Rather than add a near-identical second enum that would drift, the
existing one gained `OTHER` and now serves both — the question has the same answers
asked of your past or of a vacancy. The same duplication existed and was resolved the
same way in `api.model.ts`.

Not part of `content_hash`: the hash collapses one role arriving from several sources,
and two sources wording the contract differently are still the same job.

### Verified against the live feed, not only fixtures

Session 25's lesson applied deliberately — the LinkedIn parser was built from docs,
looked correct, and got almost every field wrong on a real document. So the real API was
read before and after building:

| Checked | Result |
| --- | --- |
| Feed parses | 33 postings, 11 categories |
| `software-development` filter | 10 of 33, all genuinely that category |
| Contract types seen | `contract`, `full_time`, `freelance`, and one empty → null |
| Descriptions | HTML stripped, no tags survive |
| `fetch()` on a real posting URL | resolves title and contract |
| Locations | `Remote · Europe`, `Remote · Brazil`, … |

**Location is prefixed `Remote ·` on purpose.** The feed is remote-only by editorial
premise but the description does not always contain the word, and `detect_regimes`
reads the location — without the prefix a remote-only user's non-negotiable would have
nothing to confirm against.

### Found on real data, deliberately not fixed

`software-development` returned **six near-identical LawnStarter postings**, the same
role in six cities, descriptions differing by 2–4 characters. They save as six rows:
`content_hash` is exact, so it collapses re-fetches, not near-duplicates. Left alone —
they *are* six distinct postings with six locations, and fuzzy dedupe is a real feature
rather than a tweak. Worth revisiting if the noise proves annoying in use.

Related and larger: the geography in `Remote · Brazil` is not modelled anywhere. Goals
carry a work *regime* but no timezone or country, so a Europe-based user sees
Brazil-only remote roles ranked on skills alone. That is a gap in `CareerGoals`, not in
this source.

### Interface

The watched-sources card now names what each source *covers* and **which contract types
it states**, before the user commits to watching it — the contract line is the one that
changes which postings are worth opening, and promising it uniformly would be a lie
about two of the three sources. Remotive's identifier is a `select` of categories rather
than a text field, because an unknown slug is indistinguishable from a category that is
merely quiet today: it would sync cleanly, save nothing, and look like a bug for as long
as the user kept it. Each posting card shows its contract as a chip, or nothing at all
when the source did not say.

### Verification

```
backend   uv run nox                 ruff + mypy --strict + 245 tests   green
frontend  npx ng build               clean, templates type-checked
frontend  npx ng test --watch=false  44 passed
alembic   check + downgrade base     no drift, unwinds cleanly
live      RemotiveBoard vs real API  see table above
```

### Environment, worth recording

`ng build` and `ng test` could not run at all at the start of the session: Node had
moved to v24.14.0 and the Angular CLI requires ≥ v24.15.0. Backend dev extras were also
uninstalled, so `uv run pytest` failed cold — it needs `uv run --extra dev`.
`nvm install 24.19.0` fixed the first, but **`nvm use` does not take on this machine**:
a standalone Node in `C:\Program Files\nodejs` outranks the nvm shim on PATH, so nvm
reports the switch and nothing changes. The build was run by putting
`C:\Users\Joao\AppData\Local\nvm\v24.19.0` on PATH directly. Removing the standalone
install, or reordering PATH, would make `nvm use` work as intended.

### Next up

1. Nothing yet turns a match into an application — Phase 8 is still unstarted, and it is
   now the narrowest part of the loop.
2. Goals drive scoring but not collection: syncing still needs a category chosen by
   hand. Seeding it from `target_roles` is the obvious follow-on.
3. Geography in goals, per the gap above.

---

## Session 26 — 2026-07-27

Second manual test pass. Upload works now, on both the CV and LinkedIn routes — the
session 25 network failure did not recur and no new datum was captured, so that
investigation stays closed-but-unexplained.

### Unreadable filenames in dark mode: the global button reset was missing `color`

`styles.css` reset `border`, `background` and `font-size` on `button` but not `color`,
so any button that did not name a colour of its own fell back to the UA's `buttontext`
— **black, regardless of `data-theme`**. It was invisible in light mode because
`buttontext` and `--text-primary` are both near-black there.

Two places carried real text inside such a button and so were unreadable in dark mode:
the CV picker on the analysis screen (`.cv-name`) and on the AI review screen
(`.cv-pick`). Fixed at the reset with `color:inherit` rather than per screen — the
component styles were not wrong, the reset was incomplete.

Added `color-scheme` to both theme blocks at the same time. Nothing set it, so every
control the browser draws itself — scrollbar gutters, `select` popups, the native file
picker — rendered light under the dark theme. It is the same class of bug: the theme
was applied to what the app paints and not to what the UA paints.

Verified: `npx ng build` clean, 44 frontend tests pass. Both edits are CSS-only.

### The gap the tester found is real: analysis diagnoses, nothing improves or shows

Reported as "analysis tells us ATS parseability alone, no tips". Checked against the
code and the real fixtures rather than assumed:

- **Parseability does emit findings** — `Full Stack Resume v2.pdf` scores 87 with two,
  `Profile.pdf` scores 80 with two. Empty findings means a clean parse, and the screen
  says so. So the tips exist; they are just mechanical.
- **Keyword coverage never ran for them** because it is gated on a pasted posting of
  ≥ 20 characters (`MIN_JOB_DESCRIPTION_LENGTH`). With no posting, the analyse button
  legitimately produces one card. The gate is invisible until you have already pressed
  analyse — the screen offers the posting as "optional" and then silently returns half
  the report.
- **Editorial improvement exists only under AI Tools** (`POST /reviews/cvs/{id}/analyze`),
  needs a configured provider, and returns text suggestions. Nothing rewrites a file,
  which is the stated contract, not an oversight.
- **There is no way to view a CV at all.** `GET /cvs/{cv_id}` returns metadata only;
  no route streams the stored file and none returns the extracted text. This is the
  more surprising of the two gaps — the user uploaded the file and cannot see what the
  parser saw, which is exactly the evidence a parseability finding is asking them to
  act on.

Nothing built for either — recorded here so the next session decides deliberately. The
cheapest useful thing is the extracted text: it needs no renderer and it is the same
string every finding is computed from.

---

## Session 25 — 2026-07-27

First feedback from the manual test pass. Two reports: a fresh account showing
inflated scores, and uploads failing in the browser.

### A brand-new account was scored as if it had already done some of the work

Neither number was mock data — both were the real formulas, and both were wrong on an
empty account.

**Profile health read 60/100 with nothing uploaded.** `profileHealth` started from a
perfect 100 and subtracted a fixed 40-point `emptyPenalty`, so "no CV at all" scored
60. Worse, the note underneath read *"Everything current. This score falls as CVs
age."* — describing a healthy library to a user with no files. No CVs now scores 0 and
says so.

**Profile completeness read 17% on an empty profile.** `gaps` tests six conditions and
`completeness` divided by all six — but the *"evidence N skills"* check **cannot fail
when there are no skills**. An empty profile therefore passed a check it was never
asked, and collected 1/6 for it. The denominator is now the number of checks that
actually apply: five normally, six once skills exist. An empty profile scores 0.

The lesson worth keeping: **a check that is inapplicable is not a check that passed.**
Any future scoring condition that only applies to non-empty data has to join the
denominator at the same moment it becomes able to fail.

### The upload failure could not be reproduced, and the server is not the problem

Reported as a network error in the UI with the request never reaching the backend.
Everything below was verified against the *running* stack (uvicorn on `:8000`, `ng
serve` on `:4200`), not a test fixture:

| Checked | Result |
| --- | --- |
| `POST /cvs/` with a 1.5 MB PDF, `curl` | 201 |
| CORS preflight for `POST /cvs/` from `http://localhost:4200` | correct headers |
| 1.5 MB multipart from a real headless Chromium, real origin | 201 |
| Same, via `XMLHttpRequest` (what Angular uses without `withFetch()`) | 201 |
| Same, with `input.value` cleared first (`documents.component.ts:137`) | 201 |
| **The real Documents screen, driven through its own `onFileChosen`** | **201, file listed** |
| Same again with a dead access token, forcing the 401 → refresh → replay branch | 201 |

Starlette's 1 MB `max_part_size` was the leading suspect and is **not** it: that cap
applies only to non-file parts (`formparsers.py:183` — file parts spool to disk
uncapped).

Forensics on the reporting session: their account (user 3) has **no `cvs` rows and no
files written** in the window, so the request genuinely never arrived — but a
`career_goals` row *was* lazily created for them at 11:33:12, which proves
authenticated, preflighted requests from that browser did reach the backend either
side of it. So it is not CORS and not a blanket connectivity failure.

**Left open, needs one datum from the next attempt:** the DevTools Network entry for
the failed `POST /cvs/` (status, or `CORS error` / `Failed to fetch`) and any console
line. Two environment facts that could matter and are worth ruling out then: uvicorn
runs with `--reload`, so **editing any `.py` file kills in-flight requests** — with
seven backend files currently modified in the working tree, a save mid-upload would
present exactly as a network error; and `ng serve` binds `[::1]:4200` while uvicorn
binds `127.0.0.1:8000`, so every API call depends on the browser's IPv6→IPv4 fallback.
Binding uvicorn with `--host localhost` would remove the second variable entirely.

### LinkedIn: the documented feature now exists

`docs/linkedin-import.md` had described a four-option import flow with **no code behind
any of it** — `linkedin_url` was a stored string and the interface asked for it as if
that did something. Built this session: `POST /linkedin/import`, `GET /linkedin`,
`GET /linkedin/review`, `DELETE /linkedin`, plus a LinkedIn screen in the navigation.

Three ingestion routes, all of them documented ones: profile PDF (either print-to-PDF
or LinkedIn's own Save to PDF, detected on upload), the official data-export ZIP, and
paste. **No URL route, deliberately** — automated access is against LinkedIn's terms
and the account at risk is the user's own.

**The parser was written twice.** The first version was built from the documentation
and looked correct; run against a real export (`test_docs/Profile.pdf`) it got almost
every structural field wrong. What the real document does that a CV does not:

| The document | What broke |
| --- | --- |
| Sidebar first, **identity block after it** | Reading the preamble found no name and no headline |
| Several roles at one employer name it **once**, with a bare tenure line | Looking two lines back made `5 years 6 months` and `Lisbon, Portugal` into employers |
| Location is optional and sits exactly where the next role's title would | A title was consumed as a location |
| Education puts the **degree and dates on one line**, school above | Title came out as the school name |
| Non-breaking spaces throughout | Titles ended `Finance\xa0·\xa0` |

The fixture in `tests/test_linkedin_parsing.py` is that real export, and every
assertion in it failed against the first implementation. **Do not "tidy" the
non-breaking spaces out of it** — they are what the parser has to survive, and there is
a per-file ruff ignore recording why.

### The PDF routes are lossy, and the product now says so

Measured on the real export: 147 words, and it carries **only the top three skills**,
no About section and no role descriptions at all. Recruiter search filters on skills, so
the one section that decides whether a profile appears in results is the one the PDF
cannot supply.

That is why **imports merge instead of replacing.** Each field group records which route
supplied it (`field_sources`), and an import only takes a group when it is at least as
exact as whatever supplied it last — `export` > `pdf` > `paste`. So a user can import
the PDF today, request the archive (LinkedIn takes up to 72 hours), upload it when it
arrives, and a later PDF import can never silently drop the archive's skill list. A
test pins exactly that.

The screen tells the user this outright when their snapshot came from a PDF, with the
menu path for requesting the export. `docs/linkedin-import.md` gained the comparison
table.

**The review is deterministic** — per-section completeness, keyword coverage against the
target roles from `CareerGoals`, and a consistency check against the career profile.
No language model, so it works on a fresh install, and it is recomputed per request
because the goals and profile it compares against change more often than the snapshot.
The snapshot is **not** promoted into the career profile: same contract as CV import,
extraction proposes and the user confirms.

### Documentation that no longer matches the code

- `PROGRESS.md` listed CV → profile extraction as both **done (session 19)** and **not
  started**, in the same table set. The "not started" row was stale; removed.

### Note for whoever tests next

An `uploadtest@example.com` account and twelve probe CVs were created in `cv_pal.db`
while reproducing this, and **removed again** — users, CVs, goals, profile, refresh
tokens and the twelve files under `uploads/`. The maintainer's own account (user 3) was
not touched. `uploads/` still holds 37 files against a single `cvs` row — 36 orphans
from earlier sessions, harmless but nothing reaps them.

---

## Session 24 — 2026-07-27

Scheduled collection, and the last two screens off sample data. **No invented data
remains anywhere in the app code** — `grep -rl "const MOCK_" src/app` returns nothing.

### Scheduling without a job queue

A user watches a company's Greenhouse or Lever board; `POST /jobs/sources/{id}/sync`
fetches the whole board and saves whatever is new.

**The sync is idempotent by content hash**, which is what makes scheduling a
non-problem: a board that has not changed adds zero postings, so a cron entry or a
systemd timer hitting the endpoint nightly needs no coordination, no locking and no
de-duplication of its own. A test pins that — sync twice, `added: 1` then `added: 0`.

That is why there is **no arq and no Redis**. Adding a broker to a self-hosted
application for one periodic task is a dependency the deployment story does not earn,
and the hard part here was never the timer.

**A board that cannot be read is recorded, not raised.** One unreachable company must not
fail a sweep across all of them, so the failure lands on the connection where the user
can see which board is broken.

**The identifier is restricted, not escaped.** It is interpolated into a board API path,
so a permissive value would let a caller reshape the request the server makes — the same
class of problem the absent URL fetcher avoids. Pattern-validated at the schema, with a
test covering `../`, query strings and fragments.

### AI Tools was pretending to be a product we do not have

It was a chat interface: tool cards, prompt suggestions, message history, all inline
sample data. **There is no chat endpoint and no plan for one.** What the API actually
does is return typed suggestions the user accepts or rejects — a real feature, in
`review_service` since session 1, that no screen had ever reached.

Rebuilt around that. It also states plainly that it is the *only* screen needing a
language model, because on a fresh install with nothing configured it is the only one
that cannot work.

Accepting a suggestion records a decision and **does not rewrite the file**. The screen
says so.

### Documents, and a dashboard with invented numbers

`CareerDocument` had descriptions, tags, statuses and cover letters; the API has
`filename`, `version`, `created_at`. Rebuilt as the CV library it actually is, with a
footnote saying generated documents do not exist yet rather than implying they do.

The dashboard depended on those invented fields — and its funnel had **hard-coded
figures**: `Applied 28`, `Responded 9`, `Interviewing 5`. Numbers with no source, on the
first screen a user sees. Replaced with the three counts that are real, and the
"unfinished drafts" next-action branch became "upload a CV", which is the actual first
step.

### Verification

```
backend   uv run nox                  lint, mypy --strict, 213 passed (was 206)
frontend  npx ng test --watch=false   40 passed
frontend  npx ng build / -c mock      clean
```

Board syncing is covered with a mocked transport: whole-board save, the idempotent
second run, an unreachable board, per-user isolation, and identifier rejection. **Not
exercised against a live Greenhouse or Lever board** — that needs a real company slug.

### Next

- **Nothing in the app shows data it does not have.** The remaining work is features, not
  clean-up: rule sets and the application queue (Phase 7), tailored generation (Phase 8).
- Still outstanding since session 7: **the containers have never been built or run**, and
  `README.md` tells people `docker compose up` is the way in.

---

## Session 23 — 2026-07-27

Claude is a supported provider. One class and one enum member behind the existing
`LLMClient` Protocol, no caller changes — which is what the Protocol was introduced for
in the first place, so it is pleasing that it held.

### Its own SDK, not a compatibility shim

Claude is reachable through OpenAI-compatible gateways, and using one would have been a
smaller diff. It would also have cost the two things this codebase actually depends on:
native structured output, and the `refusal` stop reason that separates *the model
declined* from *the model produced garbage*. `review_service` retries once on unparsable
output; retrying a refusal only spends tokens arriving at the same answer.

### Two things that would have been silent failures

Both came from reading the current API documentation rather than working from memory, and
both are now pinned by tests:

- **Current Claude models reject `temperature`, `top_p` and `top_k` outright** — a 400,
  not a degraded response. A shared LLM config that forwards sampling parameters to every
  provider would fail every request rather than ignore them. The client sends none.
- **A refusal is a successful HTTP 200** with an empty or partial body. Reading
  `content[0]` without checking `stop_reason` raises `IndexError` on what is a perfectly
  normal outcome.

The default model is a constant rather than hard-coded at the call site, because a stale
model ID fails at request time rather than at start-up — the worst place to find out.

### What fell out for free

`local_only` already refused every non-Ollama provider, so the hard switch covers Claude
without a line of new code. The API-key requirement needed one enum added to an existing
check. Both have tests, because "it happens to work" and "it is guaranteed" differ.

### Deliberately not done

Passing a JSON schema through the Protocol so Claude's native structured output can be
used. That changes every implementation, and the prompts already demand JSON with a
validating retry behind them — the win does not pay for the churn yet.

### Verification

```
backend  uv run nox   lint, mypy --strict, 206 passed (was 198)
```

**Not exercised against the real API** — that needs a key, which is the user's to supply.
The client is covered by tests with a faked transport, so the request shape, the refusal
path, the joining of multi-block responses and the error mapping are all verified; what is
not verified is that Anthropic accepts the request.

### Next

- Scheduled collection from whole boards, rather than one link at a time
- `Documents` and `AI Tools` are the last two screens holding inline sample data

---

## Session 22 — 2026-07-27

Closed the gap session 21 left open: `/jobs` now has a screen, and the last invented data
model in the frontend is gone.

### What the old screen was pretending

`job.model.ts` described a `Job` with salary bands, seniority levels, employment types, a
requirements array and a `matchScore` — **none of which exists in the API**. It was a
design mock that had been sitting in the codebase behaving like a feature. Deleted
outright rather than mapped, because there was nothing to map it to.

The dashboard had grown two dependencies on it (`strongMatches`, `jobMatches`), so those
now read real scored postings and the job list gained an empty state it never had.

### Two lists, not one sorted list

The screen shows matches ranked by score, and **blocked postings separately**. A blocked
posting broke a non-negotiable, so it is filtered out of the ranking rather than sorted to
the bottom — mixing the two makes the ordering meaningless, which is the same distinction
the goals screen exists to keep visible.

Blocked postings are still *shown*, with the reason. A filter the user cannot see is one
they cannot revisit, and "why am I seeing nothing?" is the failure mode a silent filter
produces.

### The refusal is guidance, so it is shown verbatim

The Link tab says up front that only Greenhouse and Lever resolve, and that anything else
needs Paste. When the API refuses a link, its own message is displayed rather than a
generic error — the message *is* the next step ("paste it instead"), and replacing it
would leave the user stuck.

Mock mode mirrors the refusal rather than accepting every URL. Demoing an import that the
real build cannot safely perform would advertise a capability that does not exist and
deliberately will not be built.

### A test that was fighting the framework

The ranking assertions kept failing against the `httpResource` test plumbing while the
three request-shape tests passed. Rather than keep tuning ticks, the partition was
extracted into two pure functions — `rankMatches` and `blockedOf` — and tested directly.
Better design as well as a passing test: the rule that matters is not about HTTP.

### Verification

```
backend   uv run nox                  lint, mypy --strict, 198 passed
frontend  npx ng test --watch=false   40 passed (was 37)
frontend  npx ng build / -c mock      clean
```

**Not driven in a browser.** Four screens now depend on live data — worth a real pass.

### Next

- **Anthropic provider** behind the existing `LLMClient` Protocol, so the AI half runs on
  a Claude key
- Scheduled collection from whole boards rather than one link at a time
- The `Documents` and `AI Tools` screens are the last two still holding inline sample data

---

## Session 21 — 2026-07-27

Phase 7 opened: postings can be saved, deduplicated and scored against the user's goals,
and the goals questionnaire finally has a screen.

### The URL question turned out to be a security decision

"Let the user paste a link" sounds like a convenience. Implemented naively it is a
**server-side request forgery primitive**: the API fetches whatever URL an account gives
it, and on a self-hosted install that host can usually reach the router, the cloud
metadata endpoint, and every other service on the box. Scraping arbitrary careers pages
is separately unreliable — it breaks the week a site is restyled.

So there is **no general fetcher**. A link is accepted only when a sanctioned board
recognises it, and it is then resolved through that board's own published API rather than
by fetching the page. Greenhouse and Lever both publish unauthenticated JSON endpoints for
their own listings, which is why they are first: no key, no scraping, no terms to breach,
no account of the user's at risk.

Anything else is refused with a message pointing at paste. A test pins that refusal —
including `169.254.169.254` and `file://` — specifically so the convenience is not
quietly added back later by someone who reads the refusal as a gap.

### Blocking is not a low score

`analysis/matching.py` keeps the two mechanisms principle 8 describes visibly apart:

- A **non-negotiable** that a posting breaks *blocks* it, and the block says which one.
  A user who said "remote only" is not shown a 74% match in Munich.
- Everything else *scores*, with a stated reason, so the number reads back as a sentence.

One refinement that only showed up against real data: a non-negotiable blocks **only when
the posting actually states its arrangement**. Most postings never say, and blocking those
would hide most of the market on a technicality.

Skills contribute 70% of the score, title 20%, arrangement 10% — skills weigh most because
they are the only component measured against *evidence* rather than against a stated
preference. And `profile_as_text` feeds only **evidenced** skills into the comparison: an
unevidenced skill raising a match score would rank a job by experience the user cannot
demonstrate, which is the same rule that stops a generated CV claiming it.

### A defect the live run found, again

First real scoring reported the missing required skills as `docker, fully, postgresql,
python, remote`. Two of those are not skills. `fully` is an adverb, and **work
arrangement is already scored on its own axis** — counting "remote" again as a missing
*skill* both double-penalises the posting and reads as nonsense, since "you are missing:
remote" is not a gap anyone can act on. Both are now in the boilerplate list; the missing
list came back as `docker, postgresql, python`.

That is the third time running the thing against real input has found something the
fixtures could not. It is becoming the most reliable review step in the project.

### The goals screen

Its whole job is keeping one distinction visible: a non-negotiable **filters**, a
preference **scores**. Each strictness toggle sits next to the consequence in words, and
choosing "non-negotiable" with nothing selected warns before the API has to reject it.

Regime order is the preference, so re-adding a choice appends rather than restoring its
old position. The deferred fields (direction, commute, contract type, company size, the
more-of/less-of axes) are listed on the screen as deliberately absent, so their absence
does not read as an oversight.

### Verification

```
backend   uv run nox                  lint, mypy --strict, 198 passed (was 181)
frontend  npx ng test --watch=false   37 passed
frontend  npx ng build / -c mock      clean
```

Live, end to end: set goals to remote-only non-negotiable, pasted two postings, and
`GET /jobs` returned the remote role scored 37 with three stated reasons and the Munich
role at 0 with *"You ruled this out: the posting is on site."* An unsupported URL was
refused with the paste message.

### The honest gap

**No screen consumes `/jobs` yet.** The job-search screen still shows inline sample data,
so everything above is reachable only by `curl` — exactly the state the analysis endpoints
were in before session 18. That is the next piece of work, and it is the difference
between a feature and a feature someone can use.

### Next

- **A job-search screen**: saved postings with their scores and blocks, plus the paste and
  link-import forms
- **Anthropic provider** behind the existing `LLMClient` Protocol
- Scheduled collection from whole boards, rather than one link at a time

---

## Session 20 — 2026-07-27

Step 4: the screen that makes session 19's extraction worth having. The profile is now
editable, and a CV can be read into it.

### The first complete loop in the product

Upload a CV on the analysis screen → open Career Profile → **Read it** → add the rows
that are right. A file goes in, a structured record comes out, and the readiness score
moves. Until today a new account could see the profile screen and had no way at all to
put anything in it; `curl` was the only route.

### Confirm, row by row

The import panel shows what extraction proposed and adds nothing on its own. Decisions
worth keeping:

- **No "add everything" button.** Extraction guesses, and the whole reason it is allowed
  to guess is that a person checks each row. A bulk accept would quietly undo that.
- **Added rows leave the list**, so what remains on screen is what is still outstanding
  rather than a list the user has to remember their way through.
- **A role with no dates cannot be added by pressing Add.** The API requires a start
  date, and the honest options were to invent one or to refuse. It refuses, names the
  role, and points at the manual form. Inventing a date would be fabrication in the one
  place the product promises never to fabricate.
- **Imported skills are labelled as unevidenced** in the panel itself, with the reason: a
  generated CV will not claim them until they are linked to a role.

### Editing

Profile fields (headline, location, summary, LinkedIn, website), plus add and remove for
roles, education and skills. One detail worth recording: the edit form sends **`null` for
an emptied field, not `""`**. `PATCH` treats null as "clear" and an omitted key as "leave
alone"; an empty string would store a blank headline that reads as set and renders as
nothing. There is a test pinning that, because it is exactly the kind of thing a later
refactor silently gets wrong.

### Mock mode had to grow up

The mock backend's profile was a `readonly` constant, which was fine while every screen
only read it. It now handles `PATCH`, the three creates, the three deletes and the import
route, seeded from a `MOCK_EXTRACTION` fixture that **includes a role with no dates and a
truncated title** — the demo should show what a two-column CV really produces, because
reviewing imperfect rows *is* the feature.

### Verification

```
frontend  npx ng test --watch=false   37 passed (was 33)
frontend  npx ng build / -c mock      clean, no budget warning
```

Against the live API, running the exact sequence the screen performs: imported the real
CV, confirmed one proposed role, and it appeared in `GET /profile` alongside the record
that was already there; `PATCH` with `summary: null` cleared the field while setting the
headline; delete returned 204.

**Not driven in a browser.** The screen has more moving parts than anything built so far
— worth a real look on the next `npm start`.

### Next

5. **Anthropic provider** behind the existing `LLMClient` Protocol
6. **Tier A job fetch + goal scoring**, deterministic

Also now worth doing, and cheap: the **goals questionnaire screen**, since the profile
screen has the form patterns it needs and the backend has been waiting since session 15.

---

## Session 19 — 2026-07-27

Step 3: CV → profile extraction. Deterministic, no language model, and it **writes
nothing** — it returns a proposal the user confirms through the create endpoints that
already exist, so no new write path was needed.

### Open decision 2 resolved, and both of its options were wrong

The decision was framed as "a résumé-parsing library as a deterministic *fallback*, or
lean entirely on the LLM". The answer is neither: **the deterministic pass is the
primary** and the model becomes an enricher for what it could not read. No third-party
library — the maintained ones are heavyweight NLP stacks, and the real difficulty turned
out not to be language at all.

### The real difficulty is layout, and the real CV proved it

The author's actual CV is a two-column template. `pypdf` extracts it as **74% one-word
lines** — the date column arrives as `AUG` / `2018` / `-` / `FEB` / `2019`, five separate
lines. Any parser matching line by line finds nothing at all.

That reframed the design: **reflow before parsing.** Consecutive one- and two-word lines
are rejoined, which turns the column fragments back into readable strings. It also
retroactively justifies the `fragmented_layout` warning the parseability check emits —
that warning is not cosmetic, it is telling the user their CV is hard for a machine to
read, and here is a machine failing to read it.

### The bug that section headings cause

First working version found **3 of 5 roles**. The cause is specific to multi-column
layouts and worth recording: **`SKILLS` is a sidebar heading in the second column**, so
in reading order it lands halfway down the job list, and the two roles after it were
filed under "skills".

Fix: stop trusting position. Entries are now collected from the whole document and
classified by **their own content** — an `EDUCATION_MARKERS` list matching *University*,
*BSc*, *School*, *Universidade*, *Mestrado* and so on. What an entry says is more
reliable than which heading happens to precede it. Section headings now only bound the
skills list.

The anchor that does survive: `Organisation, Location — Title`. All 8 entries in the real
CV follow it, and unlike indentation or font weight it survives text extraction.

Also fixed: `website_url` was matching the *email's* domain, so a `@gmail.com` address
proposed `gmail.com` as the personal website. Emails are stripped before the website
search.

### Proposal, never a write — the load-bearing decision

`POST /profile/import-from-cv/{cv_id}` is read-only. Extraction is guesswork on a
document whose layout the author never controlled, and its output feeds the record every
generated CV is grounded in. A wrong guess that wrote itself into the profile would put
invented history behind every CV produced from it; a wrong guess in a proposal costs one
rejected suggestion. This is *automation proposes, the user disposes* at the point where
it matters most.

It also needed **no new write endpoints** — the client creates what the user keeps
through `/profile/experiences`, `/profile/educations` and `/profile/skills`.

### Verification

```
backend  uv run nox   lint, mypy --strict, 181 passed (was 169)
```

Against the live API with the real CV: **5 of 5 roles**, **3 of 3 courses**, correct
email, LinkedIn and GitHub, 4 skills — and the profile still held only the record that
was there before, confirming nothing was persisted.

Known imperfections, all acceptable in a proposal the user edits: two job titles are
truncated where the column cut them (`Senior Software`, `Data Analyst (Data Automation &`),
and some end dates are mis-attributed because the scrambled reading order puts a
neighbour's dates inside an entry's span. Skills are thin (4) because only vocabulary
terms are proposed — the alternative is filling the profile with sentence fragments.

### Next

4. **A screen to review and confirm what extraction proposed**, plus profile editing —
   these are the same screen, and the endpoint is useless without it
5. **Anthropic provider** behind the existing `LLMClient` Protocol
6. **Tier A job fetch + goal scoring**, deterministic

---

## Session 18 — 2026-07-27

Stripped the interface of controls that did nothing, then gave the deterministic analysis
a screen. First session with the author's **real CV** to test against (`test_docs/`,
gitignored) — which immediately paid for itself.

### The real CV found two defects the fixtures never could

The first run of keyword coverage against a real CV and a real posting reported the
missing required skills as: `apis`, `ci/cd`, `docker`, **`engineer`**, **`full`**,
**`hiring`**, `pipelines`, `rest`, **`stack`**.

Two separate bugs, both fixed at the source:

- **A posting's own recruiting prose was scored as a skill.** `hiring`, `engineer`,
  `experience`, `candidate`, `team` — every job ad contains them and none is a
  requirement. `STOPWORDS` is a function-word list and never covered them. Now a
  `JOB_POSTING_BOILERPLATE` set, which is data rather than code, exactly as
  `vocabulary.py` was designed for.
- **Every multi-word phrase also leaked its component words.** `full stack` additionally
  produced `full` and `stack`; `machine learning` would have produced `machine` and
  `learning`. The token pass runs before phrases are recognised, and nothing removed the
  parts afterwards. Now a subsumption pass. **This was a pre-existing bug affecting every
  known phrase**, present since session 8 and invisible because the curated fixtures
  never exercised it.

Plus a small one: plurals now fold when — and only when — the singular is a term the
vocabulary knows, so `REST APIs` matches `rest api` while `aws` is never cut down to
`aw`. Symmetric, because the same function normalises the CV and the posting.

Score on the real pairing went 35 → 43, and more importantly the missing list became
things a person can act on.

**The lesson worth keeping: curated fixtures agree with the code that produced them.**
Three tests were added, but the defect was found by a document nobody wrote for the test
suite.

### Thirteen controls that did nothing

Removed: five settings nav items that never navigated, a **Billing** section in a
self-hosted MIT project, Save and Cancel wired to nothing, a notification bell, a Filter
button, an Apply button, a document overflow menu, and the *Compact View*,
*Auto-suggestions* and *Default Tone* toggles — all three of which flipped a signal that
**no code anywhere read**.

`ProfileService`, `UserProfile` and `UserPreferences` were invented models with a
`plan: 'free' | 'pro' | 'enterprise'` field, for a self-hosted project with no plans.
Deleted; the sidebar now reads the real signed-in account from `/users/me` via a new
`account` resource on `AuthService`, falling back to the email when no name was given.

The principle is in `PLANNING.md` → *A control that does nothing is worse than an absent
one*: a user cannot distinguish a broken feature from an unbuilt one, and a Save button
that silently does nothing teaches that the app loses data — the worst possible
impression for a tool holding a career history.

### The analysis screen

`/analysis`, between Documents and Job Search in the journey order. Choose or upload a
CV, optionally paste a posting, get the parseability report and the keyword coverage
split into *required and missing* / *nice to have and missing* / *already covered*.

Decisions worth keeping:

- **Parseability runs without a posting.** Coverage needs one, so the two are separate
  requests and the second is conditional — a user with no specific job in mind still gets
  the check that matters most.
- **Selecting a different CV clears the results.** A report belongs to the document that
  produced it; showing it against another is actively misleading.
- **The grounding line is on the screen, not just in the docs**: a missing term is only
  worth adding if it is true of you. The whole point of the missing list is that it is a
  prompt to the user, not an instruction to the generator.
- The upload guard mirrors the API's own rules (`.pdf`/`.docx`, 10 MB) purely to answer
  instantly; the API remains the enforcer.

### Verification

```
backend   uv run nox                  lint, mypy --strict, 169 passed (was 166)
frontend  npx ng test --watch=false   33 passed (was 27)
frontend  npx ng build / -c mock      clean, no budget warning
```

End to end against the live API with the real CV: uploaded through `POST /cvs/`,
`ats-check` returned 87/100 with a fragmented-layout warning (it is a two-column
template) and a missing-phone note, `coverage` returned 43 against a full-stack posting,
and a too-short posting returned 422 — which is exactly the threshold the screen's button
guard assumes.

**Not driven in a browser.**

### Docs trimmed

Per the request to cut text that is no longer earning its place: the *Frontend mock mode*
build spec was condensed to its four surviving decisions (it shipped in session 2 and the
how-to lives in `development.md`), and **an overclaim was corrected** — `PLANNING.md`
listed Anthropic as a supported LLM provider in the Stack table. It is not implemented;
Claude is reachable only through an OpenAI-compatible gateway today, which loses
structured output and the refusal stop reason.

### Next

Order set in session 17, with 1 and 2 now done:

3. **Deterministic CV parser** → profile extraction (open decision 2)
4. **Profile editing UI**
5. **Anthropic provider** behind the existing `LLMClient` Protocol
6. **Tier A job fetch + goal scoring**, deterministic

---

## Session 17 — 2026-07-27

Planning only. Two research findings folded into Phase 7, one open decision closed, and
the *Current state* block above rewritten because it had stopped describing the project.

### The LinkedIn position got stronger, not weaker

Researched rather than reasoned from memory, because the plan was making claims about
other people's products and about LinkedIn's terms.

- **The extension path is the sanctioned path.** LinkedIn's terms explicitly permit
  browser extensions that enhance the user's *own* experience, provided they do not
  scrape in violation of clause 8.2 and do not send without the user's review. Phase 7
  had framed assisted submit as the safe compromise available to us. It is better than
  that — it is the one approach affirmatively allowed, and the careful commercial tools
  use it for that reason.
- **A hard constraint we did not have written down.** Detection fingerprints include
  extensions that inject scripts, manipulate the DOM, or bypass normal click handling. So
  "a human completes every submission" is too loose: the extension must **fill fields and
  stop**, never synthesise the click. An auto-clicking extension carries the risk profile
  of automation *and* the reduced coverage of assistance — the worst of both.
- **The risk is higher than recorded.** Restriction rates near 40% in Q1 2026 for
  accounts on flagged tools, and a vendor-level ban in March 2026 that cut off ~30,000
  users at once. A user does not have to be careless to be caught, only to have picked
  the wrong tool.

### The competitors have no third technique

Worth recording because it removes a nagging question. Their headline volume comes
overwhelmingly from **Tier A** — company career pages and ATS boards, which need no
session-borrowing — plus a stored answer bank and an LLM for free-text questions. Their
LinkedIn story is either the same review-and-submit extension, or a credential-holding
bot with the account risk attached. Nothing is being withheld from us. What separates
them is ATS breadth and a willingness to trade quality for volume, which is the product
decision *What the market already sells* declines to copy.

### Open decision 1 closed: GitHub mirror

Discoverability was always the argument. What settled it is that
`.github/workflows/ci.yml` is written for GitHub Actions and therefore **runs nowhere** —
the repository has a quality gate it never executes and a README planning a badge for it.
Running CI on the self-hosted host would mean rewriting the workflow for a runner no
reader can see. Origin stays self-hosted; GitHub becomes mirror plus CI and issues.

Decision 3 (goals questionnaire) marked half-resolved: session 15 built the short
required core it was leaning towards, leaving only the interface question.

### The status blocks had drifted

`PLANNING.md` still said Phase 6's "endpoints remain" when they were built in session 8
and verified live in session 14; Phases 4b, 4c and 5 carried no status markers at all,
so a reader could not tell built from planned. All now carry per-item state.

The rewrite of *Current state* is the substantive part. It was a flat list of areas that
answered "is this done" but not "can anyone use it" — and those have diverged sharply.
**Several finished backends have no screen**: profile writes, career goals, and both
analysis endpoints are reachable only by `curl`. That is now its own section, because it
is the most useful thing for the next session to see, and a flat table was hiding it.

A second section records the two claims the repository makes that have never been
executed — `docker compose up`, and CI. Both are release blockers and both have been
quietly outstanding for several sessions.

---

## Session 16 — 2026-07-27

Schema drift closed, and turned into a gate so it cannot come back.

### The drift was not where it was thought to be

Worth recording because the fix would have gone into the wrong file. The drift was
attributed to `CareerGoals`; it was not. `career_goals` matches its model exactly — it
was written by hand against the model rather than autogenerated. The offender was
`ix_users_id`, an index on the `users` **primary key**, created by the very first
migration (`f6bd192ca9c2`) which was autogenerated and committed without adjustment.

Both SQLite and PostgreSQL already index a primary key to enforce it, so the index costs
a write on every insert and buys nothing.

### The cost was never the index

At this size the redundant write is irrelevant. What mattered is that the index existed
in the schema and not on the model, so **`alembic check` failed on a clean database and
could never pass** — which made the one check that would have caught it in the first
place unusable as a gate. Migration `f7a8b9c0d1e2` drops it.

### The gate, which is the actual deliverable

Dropping the index alone would leave the same hole open for the next model change, so:

- **New `migrations` nox session**, in the default session list. Applies every revision
  to a throwaway SQLite file, runs `alembic check`, rolls back to base.
- **`alembic check` added to the CI migration step**, so local and CI still mean the
  same thing — the promise `CONTRIBUTING.md` makes.

The reason this needs its own session rather than trusting the test suite: **the tests
build their schema from the models via `create_all`**, so a model changed without a
migration passes them and every other check. The mismatch only appears against a real
database, by which point it is somebody's deployment. That is precisely how a redundant
index survived from the first commit to the sixteenth session.

### Verified, including that the gate is not a no-op

```
uv run nox                              lint, typecheck, 166 tests, migrations — all green
alembic upgrade head → check            "No new upgrade operations detected."
alembic downgrade -1 → upgrade head     clean, check still passes
alembic downgrade base → upgrade head   clean
```

A step that always passes is worse than no step, so the gate was proved to fail: adding
an undeclared column to a model made `alembic check` report
`FAILED: New upgrade operations detected: [('add_column', ...)]`, and removing it made it
pass again. The dev database is migrated to `f7a8b9c0d1e2`.

---

## Session 15 — 2026-07-27

`CareerGoals` backend: model, migration `e5f6a7b8c9d0`, `GET`/`PUT /profile/goals`. The
first half of principle 8 — what the user is looking for, as opposed to what they have
done — now has somewhere to live.

### Only the core, on purpose

`PLANNING.md` describes ten field groups. Five columns were built: target roles, work
regimes, a salary floor with its currency, and the two non-negotiable flags.

The reason is that **Phase 7 has no backend, so every other field would be a column with
no reader**, and the shape they should take is much easier to judge against a matcher
that exists than against one that is imagined. Direction, commute ceiling, contract
types, company size and stage, industries to avoid, and the *more of / less of* axes are
recorded as deferred in `PLANNING.md` → Phase 5 rather than left to look like an
oversight.

### Two decisions worth keeping

- **`PUT`, not `PATCH`.** The goals form is edited as a whole, so an omitted preference
  means the user cleared it. Under a merge there is no way to remove a salary floor
  without inventing a delete endpoint for a single field. Tested explicitly, because it
  is the kind of semantic that gets "fixed" into a merge by someone who has not thought
  about clearing.
- **A non-negotiable with nothing behind it is rejected at the edge.** "Regime is
  non-negotiable" with no regime chosen filters out every posting and gives the user no
  way to see why. Same for a salary floor with no floor, and a floor with no currency —
  a bare number cannot be compared to a posting's band. Three validators, three tests.
  Refusing the combination is cheaper than explaining a permanently empty result list,
  and it is the concrete form of the plan's warning that collapsing the
  non-negotiable/preference distinction is how a search ends up returning nothing.

Work regime is an **ordered list**, not a single choice, because "remote, but hybrid is
fine" is the common answer and flattening it throws away the part that decides whether a
posting is worth showing. Stored as JSON: nothing queries across users by regime, so a
child table would buy indexing nobody needs and cost two joins.

### Verification

```
backend  uv run nox                  lint, mypy --strict, 166 passed (was 155)
backend  alembic upgrade head        applies
backend  alembic downgrade -1 && upgrade head   rolls back and reapplies cleanly
```

Endpoints exercised against a running server, since the test plan now documents them:
empty record on first `GET`, `eur` normalised to `EUR`, regime order preserved, a
partial `PUT` clearing everything omitted, and all four rejections returning 422 with the
specific reason.

### A pre-existing defect found on the way, not fixed

`alembic check` reports schema drift — but **not from this change**: `career_goals`
matches its model exactly. The drift is `ix_users_id`, an index on the `users` primary
key created by the very first migration (`f6bd192ca9c2`) and not declared on the model.
It is redundant — both SQLite and PostgreSQL index a primary key already — and while it
is there `alembic check` can never pass, so it cannot be added to CI as a drift gate.

Left alone at the time: it is a schema change to `users` and unrelated to goals.
**Fixed the next morning — see session 16.**

---

## Session 14 — 2026-07-26

Two halves: the market research folded into `PLANNING.md`, then the frontend put on the
real API behind a login. `docs/app_vision.md` is now redundant and can be deleted.

---

### Part 2 — the frontend talks to the backend

Prompted by the decision that review mode is the default: with validation locked on,
running the app against real data is safe, so the UI becomes the way to exercise the
backend.

#### Auth, and the one thing that had to be right

`AuthService`, `authInterceptor` and `authGuard` (in `core/auth.ts`), a `/login` screen
that also registers, and a sign-out button in the topbar.

**The load-bearing detail is that concurrent 401s must share one refresh call.** Refresh
tokens are single-use and the backend revokes *every* session when one is presented
twice — so the obvious implementation, where each failing request refreshes on its own,
signs the user out of everything the first time two requests expire together. The
in-flight refresh is held on the service and shared with `shareReplay`, released on
completion by `finalize`. Both halves are tested: one refresh for two callers, and a
second refresh still possible afterwards. The second test exists because a `shareReplay`
that is never released fails in the opposite direction — the session can never be
renewed and the user is logged out after 30 minutes instead.

The interceptor skips `/auth/` entirely. Sending a stale token at the endpoint that
issues tokens, or refreshing a refresh that just failed, loops.

#### A real bug the tests found: `localStorage` is not always there

The first test run failed on `localStorage` being undefined in the node runner. That is
not a test-environment quirk to work around in the spec — the same code would throw
under any prerender or SSR build, which Phase 4d's PWA work makes likely. Fixed at the
source: one module-level `store` resolved once, `?.` at the five call sites. The specs
no longer touch `localStorage` at all, because persistence is a browser API, not our
logic.

#### `CareerProfileService` now fetches

`httpResource` against `GET /profile`, with `defaultValue` set to an **empty** profile
rather than a placeholder one. Two consequences worth keeping:

- `profile()` stays non-nullable, so every derived signal and the whole template needed
  no undefined handling — the migration touched almost nothing below the service.
- The URL function returns `undefined` while signed out, so the resource stays idle
  instead of firing a request that can only 401, and reading `isAuthenticated()` inside
  it is what makes the profile load itself the moment a login succeeds.

The profile page gained loading and error states. **Without them a failed request is
indistinguishable from an empty profile**, which is the worst possible message to send
someone about their own career history.

The seed profile moved from the service into `mocks/fixtures/api.fixtures.ts` and a
`GET /profile` route was added to `mock-backend.ts` — required, not optional: without it
the mock build would 404 on the screen it is meant to demo.

#### Mock mode keeps its no-signup promise

The guard would otherwise have put a login wall in front of the public demo. `AuthService`
starts with a session already established when `environment.useMocks` is true, so the
demo needs no account and the guard and interceptor still run their real code paths
rather than being special-cased out.

#### Verification

```
frontend  npx ng test --watch=false    27 passed (was 18)
frontend  npx ng build                 clean, no budget warning
frontend  npx ng build -c mock         clean
```

Against the real API, running locally with the session-11 smoke-test account — this is
the first time the frontend's exact wire format has been checked rather than assumed:

- `POST /auth/login` form-encoded with the email in `username` → token pair, and
  `access-control-allow-origin: http://localhost:4200` present, so the browser will
  allow it.
- `GET /profile` with the bearer token → the profile; **401 without it**.
- `POST /auth/refresh` → a new pair, confirming rotation.

**Not driven in a browser.** The interceptor's 401-refresh-retry path is covered by unit
tests, not by a real expiry; worth watching the first time an access token actually ages
out after 30 minutes.

#### The test plan found a bug, which is the argument for writing it

`docs/manual-test-plan.md` is new — step-by-step checks for everything built, including
the paths with no interface yet. Every API command in it was **run against a live
instance** rather than written from the source, which caught two things:

- **The login screen would have rendered password rejections as `[object Object]`.**
  FastAPI answers a policy failure with a 422 whose `detail` is a *list of validation
  objects*, not the flat `detail` string every other error uses. The form read `detail`
  directly. Fixed with a `detailOf` helper that handles both shapes and strips Pydantic's
  `Value error, ` prefix; three tests cover it. This is the one screen where the reason
  for the rejection *is* the feature, so it would have been a bad first impression on the
  first thing a new user does.
- **The lockout sequence is 1–6 then locked, not 1–5.** The lock is checked *before* the
  password is, so the sixth wrong attempt still reports invalid credentials while arming
  the 2-second backoff that the seventh hits. The first draft of the plan said attempt 6
  would be rejected, which would have read as a failed test.

A second scratch account is now in the dev database from that run —
`plantest@example.com` / `orbital-lemur-7-quilt`, with a headline, one role and two
skills. It is the account section 6 of the plan builds, so it is useful for checking the
profile screen without doing the `curl` work again. Safe to delete.

Also confirmed live: all four password-policy rejections including `Password123!`,
`PATCH /profile`, `is_current` from a null end date, `K8s` storing canonical
`kubernetes` with `is_evidenced: true`, an unevidenced skill, and refresh reuse returning
200 then 401.

---

### Part 1 — the market research, folded into planning

#### What the research actually changed

Most of it was already covered: caps, targeting, audit log, per-posting tailoring and
human confirmation are principles 2 and 5 and the Phase 7 rails. Three things were
genuinely missing, and two things in the note could not be adopted as written.

**Missing 1 — the user's goals were never modelled.** Phase 7 had *match rules*, which
are filters over postings. Nothing anywhere held what the user actually wants: the role
they are aiming at, the work regime they can live with, the floor, the parts of a job
they want more and less of. Without that, "quality" has nothing to be measured against
and the phrase is marketing. Now principle 8 and a `CareerGoals` entity, collected in
**Phase 5** rather than Phase 7 — it is part of describing yourself, not part of
configuring a search.

The non-obvious part: **Phase 12 already specified the same question set** ("more of /
less of: deep focus, variety, people contact, travel, on-call…") for career path
planning. One record now serves both. Two screens asking the same question is how they
end up holding different beliefs about what the person wants.

**Missing 2 — no gate between "tailored" and "sent".** New top-level section
*Application quality gate*: eleven checks, block versus warn, running identically whether
a human or a rule set triggered the send. Automation skips the reviewer, never the checks,
and **blocks cannot be overridden by anyone** — a gate with advisory blocks is decoration.
Nearly all of it is deterministic, so it is testable against fixtures and works with no
LLM. It also has **no upstream dependency**: most of it can be built against the analysis
core that exists today, before any job source does.

**Missing 3 — Phase 9 was in neither the in-scope nor the deferred v1.0 list**, while
Phase 7's own UI description included the application tracker. Now explicitly in scope,
for a second reason worth recording: reply rate per CV variant and per source is the only
*evidence* that quality beats volume. Asserting it without measuring it would be the same
move the volume tools make.

#### Two things in the note that were changed rather than adopted

**"Not detected as AI spam by ATS" cannot be built as stated.** ATSs parse, match and
rank; they do not generally run AI-text detectors. The detectors that exist over-flag
non-native English speakers and plain prose — i.e. they would penalise exactly the users
this project claims to be for — and they are an unobservable moving target, so any score
would be indefensible.

Inverted instead: not *does this look machine-written* but **does this look written for
this job**. Specificity (bullets with no figure, system, artefact or scope), filler
density from a bundled list, keyword stuffing, posting specificity, and — the strongest
signal, and one **no competitor can compute** — shingled self-similarity against the
user's own recent applications. Ten letters that are 92% identical are spray-and-pray
whatever wrote them. A hard rule went in alongside: **never optimise for evading
detection**; a check that could be satisfied by making text vaguer or by disguising
authorship does not belong.

**"Replace existing similar words" fabricates if read literally.** Bounded to three
transforms and nothing else — *surface* an omitted profile fact, *substitute within an
alias equivalence class*, *rephrase* with the claim unchanged. A posting asking for Oracle
must never turn Postgres experience into Oracle experience.

That has a consequence nobody had drawn: **the alias map is now on the safety path, not
just the scoring path.** Substitution is only safe because something authoritative says
two terms are the same, and today that something is 37 hand-curated software terms. For a
nurse or an accountant there is no equivalence data, so transform 2 must be *disabled*
for them rather than approximated — letting a model guess whether two occupational terms
are synonyms is fabrication with a job attached. ESCO/O\*NET therefore moves from "Phase 6
follow-up" to a **dependency of automated tailoring outside software**. The *Known
limitation* section was escalated accordingly.

#### Principle 5 was going to be broken on the day automation shipped

It said anything outward-facing "needs explicit confirmation", full stop, while Phase 7
plans unattended submission. Amended rather than papered over: consent is per send by
default, or a standing authorisation for one proven rule set — **per source, unlocked
only after approved-without-edits applications, taken by typed confirmation, and expiring
on any material change** to the rule set, base CV, goals or profile. The user approved a
*pattern*; when the pattern changes the approval does not carry. That last clause is what
makes unattended mode defensible at all.

This is the research note's "validation mode, on by default, with a warning when removed",
made specific enough to build.

#### Sequencing deliberately unchanged

The temptation was to pull Phase 7 forward, since that is where all this lands. Recorded
against: the goals questionnaire and most of the gate are cheap and buildable *now*
because they need no connector, no source and no model. Next work is still frontend →
real API, close Phase 5, then the gate. Building submission rails before there is
anything worth submitting is how the plan grows a thirteenth phase and no product.

### Next

Item 1 of session 13's list is done — that was Part 2 above.

1. **Documents → real API.** `/cvs` upload, list and delete already exist and are the
   next most valuable thing to exercise: it is the only screen with a write path, so it
   tests more of the backend than another read does.
2. **`CareerGoals` backend** — model, migration, `GET/PUT /profile/goals`. The smallest
   remaining piece of Phase 5, and it unblocks the gate.
3. **Application quality gate**, deterministic checks only, against the existing analysis
   core. No job source required.
4. **Profile editing from the interface** — the screen is live against a real API but
   still read-only, so the only way to change a profile is `curl`.
5. Backend Phase 5 completion: projects, certifications, CV → profile extraction.
6. Job search → automation UI, still mock-only until Phase 7 has a backend.
7. Still outstanding from session 7: **the containers have never been built or run.**

---

## Session 13 — 2026-07-26

### The UI feedback had a root cause nobody had written down

Challenged again on the "bland" dashboard. Session 12 had built the dashboard work and
it *was* in the working tree — but the complaint was still fair, because session 9 had
diagnosed symptoms and missed the cause: **the navigation was organised by object type,
not by the journey**. *Documents*, *AI Tools*, *Job Search* name what things are and
leave the user to infer the order to use them in. No amount of dashboard polish fixes a
sidebar that does not describe the work.

That principle is now in `PLANNING.md` → *Interface direction*, along with a status table
per item, because the same "written down but not built" gap that session 12 hit was about
to repeat: two of the three session-9 items are still unbuilt.

Nav is now **Dashboard → Career Profile → Documents → Job Search → AI Tools → Settings**.

**No placeholder entries for Applications or LinkedIn.** They belong in the journey but
have no content behind them, and a navigation item that leads nowhere reads as a broken
product rather than an unfinished one. The rule recorded: a screen is added when it has
content.

### The career profile had no interface at all

The sharpest case of the same problem. Phase 5's backend has existed since session 10 —
`GET /profile`, experiences, educations, skills with evidence — and the **first step of
the journey had no route, no nav entry and no component**. Built now:
`pages/profile/profile.component.ts` over a new `CareerProfileService`.

- **Readiness is a task list first, a score second.** `gaps` produces what is missing
  ("evidence 2 skills", "link your LinkedIn profile"); `completeness` is computed *from
  that list*, so the number and the list cannot drift apart. An earlier draft computed
  them independently, which is exactly how a score ends up disagreeing with the reason
  given for it.
- **Unevidenced skills are labelled in the interface.** `is_evidenced` was built so a
  generator can distinguish a grounded claim from an asserted one; showing it is what
  turns *never fabricate experience* into something the user can act on before an
  interview, rather than an invariant only the backend knows about.
- Skills sort evidenced-first within a category, so the claims a tailored CV may actually
  use are at the top and the unusable ones are visible underneath.
- The dashboard's `nextAction` gained profile gaps as its **top** branch: an incomplete
  profile blocks tailoring altogether, so it outranks even a stale CV.

**Data source:** a seed constant typed as `CareerProfileResponse`, held inline in the
service. Typed against the real wire contract, so a backend schema change breaks the
build here — but declared inline rather than imported from `src/mocks/`, because mock
code must stay out of the production entry graph. This matches every other service in the
app until the `HttpClient` migration lands. **No `/profile` route was added to
`mock-backend.ts`**: nothing consumes it until that migration, and an unused route is
scaffolding.

### A real bug from session 12: `--text-muted` does not exist

Session 12's dashboard CSS referenced `var(--text-muted)` in four places. **That variable
is defined nowhere** — `styles.css` has `--text-primary`, `--text-secondary` and
`--text-tertiary`. So every element session 12 intended to mute (the next-action detail
line, the eyebrow, the funnel labels, the health `/100`) has been rendering at full
primary colour. The dashboard genuinely did look flatter than intended, which is worth
noting given the feedback that prompted it.

Fixed by using the existing `--text-tertiary` rather than defining a new variable — there
were already three text greys and a fourth was not needed.

### The component style budget, fixed at the cause

Session 12 recorded fighting the 4 kB `anyComponentStyle` budget and landing 1.17 kB
over. The cause was not the new sections: **every page declared its own identical `.card`,
`.card-header` and `.badge` rules**. Those are now in `styles.css` once, and the
dashboard's copies are deleted.

Also deleted from the dashboard: `.stats-grid`, `.stat-card`, `.stat-icon*`, `.stat-info`,
`.stat-value`, `.stat-label` and their two media queries — **all dead since session 12**
removed the tile row from the template, and all still being shipped. With those gone the
build reports **no budget warning at all**, and the new profile page needed almost no
container CSS.

Same sweep removed `DashboardService.stats` and `shared/models/dashboard.model.ts`,
neither of which anything had read since session 12; that also dropped the `AiService`
dependency from `DashboardService`.

### Verification

```
frontend  npx ng build                 clean, no budget warning (was 4.30 kB over)
frontend  npx ng build -c mock         clean
frontend  npx ng test --watch=false    18 passed (was 14)
```

Four new tests on `CareerProfileService`, the load-bearing one being that
`gaps().length === 0` and `completeness() === 100` agree — which fails if a check is ever
added to one and not the other.

**Not visually verified in a browser.** Worth a look on the next `npm run start:mock`,
particularly the muted-text fix, since that is the change most likely to look different
from what session 12 described.

### Next

1. **Job search → automation** (rules → matches → queue → sent → activity log) — the
   largest unbuilt *Interface direction* item, but Phase 7 has no backend, so it would be
   mock-only UI for a while. Worth confirming that is wanted before building it.
2. **Frontend → real API.** The blocker is not the endpoints, it is token storage and a
   refresh interceptor, which has sat on "next up" since session 2. `/profile` is now the
   best first consumer: it is read-only, the contract is typed, and the page exists.
3. Backend Phase 5 completion: projects, certifications, CV → profile extraction.
4. Still outstanding from session 7: **the containers have never been built or run.**

---

## Session 12 — 2026-07-26

### The UI direction was written down but never built

Fair challenge from the user: feedback was given, a diagnosis was written, and the app
did not change. Sessions 8 and 9 deliberately held UI work "until after the review" —
but the review *was* what produced the feedback, so that hold was stale and should have
been dropped in session 9. Implemented now.

### Logo in the sidebar

`brand-icon` was a text "CP" on an accent-coloured plate. Now the mascot, with the plate
removed — the artwork carries its own outline and transparency, so a coloured square
behind it fought with it. `alt=""` because the adjacent `.brand-text` already says
"CV Pal"; a screen reader should not hear the name twice.

### Dashboard: from passive to actionable

Implements the *Interface direction* section of `PLANNING.md`.

- **Lead "next action" card** replaces the row of four equal tiles. `nextAction` is
  computed and **ordered by cost of inaction**: a stale CV outranks an unreviewed match,
  because applying with an out-of-date CV wastes every application made with it; an
  unreviewed match outranks an unfinished draft. Tone (`attention` / `opportunity` /
  `calm`) drives the left border.
- **Funnel strip** — matched → tailored → applied → responded → interviewing. The shape
  of a search, and where it stalls, which nothing else in the app showed.
- **Profile health score that decays**, penalising documents untouched for 90 days and
  unfinished drafts, so a CV going stale is visible before it costs an opportunity.
- Counts are now derived signals (`staleDocuments`, `strongMatches`, `draftDocuments`)
  rather than hard-coded totals. `aiEnhances` was a literal `8`; it now reads the
  conversation count.

### Component style budget

Worth recording because it is easy to paper over: the dashboard was **already over the
4 kB component-style budget before this change** (4.30 kB), and the first draft nearly
doubled it. Rather than raising the budget to hide that, the three new sections were
changed to reuse the existing `.card` container and only declare their own layout,
cutting the addition roughly in half. Still 1.17 kB over the *warning* threshold,
comfortably under the 8 kB error ceiling. The budget was **not** altered.

### Verification

`npx ng build` succeeds, `npx ng test --watch=false` 14 passed. Confirmed `logo.webp`
is emitted as an asset and referenced from the bundle, and the new dashboard markup is
present in the compiled chunk.

Not visually verified in a browser — worth a look on the next `npm run start:mock`, and
a hard refresh if the old assets are cached.

---

## Session 11 — 2026-07-26

### Logo and icon set

Source `cv_pal_logo.webp` was **VP8 lossy with no alpha channel** — the black background
was baked into the pixels, not a removable layer.

- Removed by **flood-filling inward from the corners**, not a global black→transparent:
  the cap, suit and magnifier frame are also black and a global key punches holes
  through the mascot. Tolerance matters — 12% fuzz bridged into the cap and suit, **2%
  is clean**. Verified at 1:1 over both theme backgrounds.
- **The full mascot is unreadable at 16–32px.** Rendered and magnified to confirm. The
  favicon is therefore a **cat-face crop**; the full mascot is used only at larger
  sizes. Two framings, deliberately.
- Generated: `logo.webp` (512px, in-app), `favicon.ico` (16/32/48 multi-res),
  `favicon-16/32/48.png`, `apple-touch-icon.png` (opaque background — iOS composites
  transparency onto black), `icon-192/512.png`, and `icon-maskable-512.png` with the art
  inside the middle 80% so Android's crop does not cut into it. 636 KB total.
- Dropped the PNG twin of `logo.webp`: 308 KB for a format every supported browser no
  longer needs.
- `index.html` wired up; title corrected from "CvPal".

**Theme finding:** hue-rotating the logo to the app's indigo `#6366f1` also turns the
cat's amber eyes blue and drains the warmth. Recommendation recorded — keep the logo
orange and promote orange to the accent, since `#6366f1` is the stock Tailwind indigo
and every competitor in this space (LinkedIn, Indeed, Monster) is blue. **Not applied**;
it is a UI decision under review.

If the logo can be re-exported from its source with a transparent background, that beats
keying black out of a lossy raster. Not required — the current result is good.

### Local `.env` files

`backend/.env` and `.env` (compose) created from their examples with freshly generated
64-character keys. Both confirmed gitignored and absent from `git status`.

Ollama is not installed on this machine, so the provider is left as `ollama` and the
app reports the model unavailable rather than failing to start — which is the intended
behaviour, and **the deterministic analysis endpoints work regardless**.

`CV_PAL_LOCAL_ONLY` stays commented out: defaulting it to true would silently block
someone who later switches to a hosted provider.

### The dev database was stale

`backend/cv_pal.db` predated all the schema work — pre-migration schema with no foreign
keys, an **empty `alembic_version`**, and zero rows. `alembic upgrade head` would have
failed on "table already exists". Backed it up to the scratchpad, removed it, and
migrated from scratch to `d4e5f6a7b8c9`. **Anyone else with a database from before the
migrations exists in the same state**, and the fix is the same: it holds nothing.

### First full-stack smoke test

Run against the real `.env` and real database with nothing set in the shell — register,
login, profile read, add experience, add skill with evidence, refresh rotation, logout.
All passed. `K8s` stored with canonical `kubernetes` and `is_evidenced: true`; a role
with no end date reported `is_current: true`.

A `smoke-test@example.com` account remains in the dev database (password
`orbital-lemur-7-quilt`) — useful for logging into the UI, safe to delete.

---

## Session 10 — 2026-07-26

**Phase 5 started: the career profile.** Plus a new Phase 12 in planning, and one
limitation the "generalist tool" framing exposed.

### The career profile (backend, working)

`career_profiles`, `experiences`, `educations`, `skills`, and a `skill_evidence` join,
with migration `d4e5f6a7b8c9` verified up and down.

Design decisions worth keeping:

- **`skill_evidence` is the point of the model, not plumbing.** A skill can cite the
  dated roles that demonstrate it, and `is_evidenced` is exposed on the API. That is
  what turns *never fabricate experience* from a principle into something a generator
  can enforce: it can tell a grounded claim from an asserted one. Deleting a role drops
  the link and leaves the skill unevidenced rather than deleting it — tested.
- **`end_date IS NULL` means "current"**, with `is_current` derived. A separate boolean
  could disagree with the dates; this cannot.
- **Skills deduplicate on the canonical form**, via a unique constraint on
  `(profile_id, canonical_name)` using `analysis.keywords.canonical`. Adding "Kubernetes"
  after "K8s" is a 400, and both match a posting asking for either. The user's own
  spelling is kept for display.
- **The profile is created on first read**, so no client ever handles "not created yet".
- **No endpoint accepts a profile id.** Ownership is resolved from the authenticated
  user on every call, so a request cannot reach another profile's rows. Citing another
  user's experience as evidence is a validation error, not a 404 — the skill is the
  resource being created and the bad reference is in the payload.

Not yet built: projects and certifications (additive, later migration), and LLM
extraction from an uploaded CV — the parsing side of Phase 5.

### New: Phase 12 — career path planning

A graph of possible next roles rather than a list, each node answering how far away it
is, what the work involves, what it pays, and what would suit or grate.

Two things I want to keep visible:

- **Grounding matters more here than anywhere else in the product.** Someone may retrain
  for two years on this advice, so numbers come from the user's own matched postings
  (Phase 7) or an occupation taxonomy, never from the model. The model writes narrative
  only, and provenance is shown per claim.
- **"Interesting and boring" is personal.** The product must not label parts of a job
  boring — what one person finds tedious another finds calming. It reports *what the
  role involves a lot of*, factually, and matches that against a short "more of / less
  of" preference set captured at profile time. That personalisation is the whole value;
  without it this is generic careers-advice text.

An agent rather than one prompt because each node is multi-step (resolve role, gather
requirements, compare, price the gap, write) with results cached per role.

### Limitation surfaced by the "generalist tool" framing

**All 37 skill aliases in `analysis/vocabulary.py` are software-engineering terms**
(`k8s`, `postgres`, `react.js`). The machinery is domain-neutral — it takes the alias map
as data — but the data is not. A nurse, teacher or electrician currently gets no alias
resolution and weaker keyword coverage, **and this would be invisible to a software
engineer testing the tool**. Recorded in `PLANNING.md`; the fix is the same work as
grounding career paths: adopt ESCO or O*NET and derive the vocabulary rather than
hand-curating it.

### Verification

`uv run nox` green: ruff, `mypy --strict`, **155 tests** (was 137). Migration verified
both directions, with the unique constraint and both cascading foreign keys confirmed in
the emitted schema.

One false alarm worth noting: this FastAPI version keeps included routers as
`_IncludedRouter` wrappers rather than flattening them into `app.routes`, so introspecting
`app.routes` for paths shows nothing. Use `app.openapi()["paths"]` instead.

### Next

Projects and certifications; CV → profile extraction; then Phase 6's grounded rewriting
or Phase 8 tailoring, both of which now have a profile to work from.

---

## Session 9 — 2026-07-26

Backend: the analysis endpoints. Planning: the first UI review, and two new
requirements — application automation and LinkedIn profile import.

### Analysis endpoints (backend, done)

`POST /analysis/cvs/{id}/ats-check` and `POST /analysis/cvs/{id}/coverage`, backed by
`services/analysis_service.py`, with `KeywordResponse`, `CoverageResponse`,
`FindingResponse` and `ParseabilityResponse` schemas. Ownership is enforced through the
existing `get_owned_cv`, so another user's CV is a 404 as everywhere else.

One test asserts the endpoints make **no LLM calls at all** — the deterministic core's
whole value is that it works with no provider configured, and that property is now
guarded rather than assumed.

The frontend contract in `api.model.ts` was extended to match, keeping the
fixtures-typed-against-the-real-contract rule intact.

`uv run nox` green: ruff, `mypy --strict`, **137 tests** (was 128).

### UI review (first look at the mock build)

Feedback: dashboard neat but bland; no automation anywhere; no LinkedIn anywhere.
Recorded in `PLANNING.md` → *Interface direction*. The substance:

- **The dashboard is passive.** It reports totals instead of prompting the next action.
  Direction: one primary "do this next" card, counts replaced with scored or actionable
  numbers, a matched → tailored → applied → responded funnel, a decaying profile-health
  score, and an activity timeline — which becomes the *trust mechanism* once a bot is
  acting on the user's behalf.
- **Job search becomes automation**: rules → matches → queue → sent → activity log, with
  the automation level shown per source.
- **LinkedIn needs its own section**, currently absent entirely.

### Two new requirements, and one reversal

**Application automation is now a headline feature.** Phase 7 was rewritten around a
rules engine plus tiered submission. **This reverses a documented guarantee**: the
README previously promised CV Pal was "not a mass-application tool". That was written
when the product was a CV tool. The promise has been narrowed to what it can actually
keep — targeted, rule-driven, rate-capped, tailored, logged — rather than left standing
while the code contradicted it. Both `README.md` and `PLANNING.md` updated, with the
change flagged in place so it does not look like drift.

**The submission tiers are the load-bearing design decision.** LinkedIn, Indeed and
Monster all prohibit automated applying and LinkedIn actively detects it; the exposure
is not primarily legal but that *the user's own LinkedIn account gets restricted* —
destroying the network their search depends on. So:

1. Auto-submit — only sources with a published application API.
2. **Assisted submit via a browser extension** — fills the form in the user's own
   browser and own session, user presses submit. No stored credential, no headless
   session, works on LinkedIn Easy Apply and everything else. Removes the tedium without
   the exposure, and is the recommended path.
3. Prepare-only — tailored CV and letter, apply manually.

Rails on every tier: daily and per-company caps, dry-run default, mandatory review of a
new rule set's first applications, full audit log, kill switch.

**LinkedIn import**: a URL cannot simply be fetched, but LinkedIn's own **More → Save to
PDF** on your own profile produces a complete profile that **CV Pal already parses**.
That is one click for the user, no credentials, nothing against any term — so it is the
primary route, with the official data export and paste as alternatives. The URL is still
stored, for consistency checks and for the extension to use in-session.

**v1.0 scope reopened.** Phases 7 and 10 had been deferred; they are back in scope,
because they are what the user actually wants the product for. The order
5 → 6 → 8 → 7 → 10 is kept as a *dependency chain, not a ranking*: auto-applying with an
untailored CV is precisely the spray-and-pray the guarantees rule out, so tailoring must
work before automation sends anything.

### LinkedIn import guidance (`docs/linkedin-import.md`)

Written for users, not developers. Checking LinkedIn's current behaviour before writing
it changed the recommendation substantially:

- **"Save to PDF" is not reliable.** LinkedIn removed it in 2025 and restored it only
  for some accounts, and it only handles English profiles correctly. It had been planned
  as the primary route; it is now listed first for speed but explicitly cannot be
  depended on.
- **Browser print-to-PDF is the actual universal path** — every account, about a minute,
  and it produces a PDF the existing parser already handles. This is what the guide and
  the interface should lead with.
- **The data export takes up to 72 hours**, not the day I had assumed, and the download
  link also expires after 72 hours. Fine as the "precise version later" route, useless
  as a first-run experience.

Consequences recorded in `PLANNING.md`: the parser must tolerate navigation chrome from
printed pages; content the user left collapsed is simply absent, so the review should
notice suspiciously empty sections; pasted profiles lose section boundaries and must be
scored and labelled differently.

**Reducing the effort the scraper would have saved:** a LinkedIn PDF is structurally
recognisable — contact block, "Top Skills", profile URL in the footer — so detecting it
on upload means the user never has to say what they are uploading. That recovers most of
the convenience for none of the exposure.

### Next

Stopping here as agreed, to link backend and frontend and review features. The natural
next backend chunk is Phase 5, the career profile domain model.

---

## Session 8 — 2026-07-26

Asked which work is independent of a pending UI review. Answer: anything that is a pure
function over text, or a data contract, is safe; anything that encodes a screen is not.
Started with the deterministic analysis core — the one item with **no dependency on
either the UI or the database schema**, so nothing decided later can invalidate it.

### `backend/cv_pal/analysis/` (new)

- `vocabulary.py` — stopwords, skill aliases, requirement markers, action verbs,
  expected section headings, known multi-word phrases. Plain frozensets, no data file
  and no filesystem read, so it works in `local_only` mode.
- `keywords.py` — extraction from a job description, required-versus-preferred
  detection by section marker, canonicalisation through aliases, and weighted coverage
  scoring against a CV.
- `parseability.py` — the mechanical ATS checks: text extractable at all, contact
  details present in the *text layer*, section headings detectable, machine-readable
  dates, column-layout detection, length, action-verb and quantification heuristics.

No model, no network, no cost, and fully reproducible. This is *deterministic first*
made real: **the majority of the product's value now works with no LLM configured.**

### Four defects the tests caught

Worth recording because three were real and one was a wrong expectation:

1. **Trailing punctuation absorbed into tokens.** The tokeniser keeps intra-word
   punctuation on purpose (`node.js`, `ci/cd`, `c++`), but that also swallowed sentence
   punctuation — `"Python."` tokenised as `python.`, so it never matched `python`. Fixed
   by stripping only trailing `./-`, which leaves `c++` and `c#` intact.
2. **Requirement markers scored as skills.** "requirements", "must", "nice",
   "essential" were being extracted as keywords. They delimit sections; they are not
   things to have.
3. **Phrase noise.** Every word n-gram became a keyword, so "senior backend engineer"
   was scored as a required skill. Now a multi-word phrase counts only if it is a known
   concept (`KNOWN_PHRASES`) or the posting repeats it.
4. **Dates counted as quantification.** "Led the migration in March 2021" was scored as
   a quantified achievement because of the year. Dates are now stripped before looking
   for numbers — a date says nothing about scale.

The fourth test failure was my expectation, not the code: a CV listing only six
technologies genuinely does not cover a posting that also says "Senior Backend
Engineer". The test was corrected rather than the behaviour.

### Verification

`uv run nox` green: ruff, `mypy --strict`, **128 tests** (was 97). 31 of the new tests
cover the analysis core, including determinism assertions on both halves.

### Deliberately not done

`DocumentService` → `HttpClient`, accessibility work, the PWA, screenshots and the demo
deployment all encode UI decisions that are about to be revisited. Building them now is
the most likely work to be thrown away.

### Next up

1. Wire the analysis into endpoints (`POST /reviews/cvs/{id}/ats-check`, and a
   coverage endpoint taking a pasted job description). Additive to the API.
2. Phase 5 — career profile domain model. Also UI-agnostic: its shape is dictated by
   what a CV contains.
3. Structured logging with request IDs.
4. After the UI review: frontend service migration, accessibility, Docker verification.

---

## Session 7 — 2026-07-26

**Phase 4c — release readiness.** Everything the repository needs before publication,
except the two items that depend on decisions still open.

### Container packaging (Tier 1)

- `backend/Dockerfile` — multi-stage, uv against the committed lock file, unprivileged
  `cvpal` user, `/data` volume pre-created with the right ownership, liveness health
  check, entrypoint that applies migrations before starting uvicorn.
- `frontend/cv-pal/Dockerfile` — Node build stage, then `nginx-unprivileged` on 8080.
- `frontend/cv-pal/nginx.conf` — serves the SPA and **reverse-proxies `/api/` to the
  backend**, so the whole stack is one origin.
- `docker-compose.yml`, `.env.docker.example`, both `.dockerignore` files.
- New `selfhost` Angular build configuration and `environment.selfhost.ts`
  (`apiUrl: '/api'`).

**The same-origin proxy is the decision with the most consequences.** It removes CORS
configuration from the self-hoster's job entirely — a common foot-gun — and it re-opens
the option of moving tokens into `HttpOnly` cookies, which the separate-origin design
had closed off. Session 6 recorded that trade-off as "worth revisiting if the compose
deployment serves both from one origin"; it now does.

Full rationale for every container security choice is in `PLANNING.md` →
*Container security decisions*, written as a table so it can be reviewed rather than
taken on trust.

### A real bug this surfaced

Uploads were written to `DEFAULT_UPLOAD_DIR`, a module constant resolving to a relative
`uploads/` path. In a container that lands inside the image, not on the volume, so
**every uploaded CV would have been lost when the container was replaced**. `upload_dir`
is now a proper setting, read at call time, and `CV_PAL_UPLOAD_DIR` points it at `/data`
in the compose environment.

The test fixture was changed to drive it through `CV_PAL_UPLOAD_DIR` and
`get_settings.cache_clear()` rather than monkeypatching the constant — so the env-var
path the container depends on is the one under test, instead of a path no test touched.

### Open-source repository files

`SECURITY.md` (disclosure route, what the software actually does, and an explicit
known-limitations section), `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`,
`docs/self-hosting.md` (written for non-developers — Docker only, with backup and
restore commands), `.github/workflows/ci.yml`, and a README rewritten to the running
order specified in `PLANNING.md`.

### Verification

```
backend   uv run nox                        lint + mypy --strict + 97 tests   green
frontend  npx ng build -c selfhost          bundle generated
compose   docker-compose.yml parsed         services, volumes, profile, gate confirmed
```

**Not verified: the container images have never been built or run.** Docker was
installed mid-session but the daemon is not running and the compose plugin is missing,
so `docker compose up` is *written but untested*. Everything in it is reasoned rather
than observed — the entrypoint, the volume ownership, the nginx proxy path rewrite, the
health-check gating. Given the earlier lesson about documenting an unverified quickstart
(the `.env` boot failure in session 3), **this must be run end to end before the README
promotes it**, and `docs/self-hosting.md` should be walked through literally.

To unblock: `sudo pacman -S docker-compose && sudo systemctl enable --now docker && sudo usermod -aG docker $USER`, then re-login.

### Still blocked on decisions

- **CI** is written for GitHub Actions but the only remote is self-hosted, so it will
  not run anywhere yet. Open decision 1.
- **The public demo** needs somewhere to host the mock build. Same decision.
- **A screenshot** for the README — left as an explicit TODO comment rather than a
  broken image link.

### Next up

1. Build and run the containers; walk `docs/self-hosting.md` literally.
2. Per-user encrypted LLM provider config; token/cost accounting.
3. Structured logging with request IDs.
4. Migrate `DocumentService` to `HttpClient` — the frontend still has inline mock data
   and no token storage or refresh interceptor.
5. Then Phase 5 — career profile as the master record.

---

## Session 6 — 2026-07-26

**Refresh tokens with revocation** — the last item Phase 4c requires before the
repository can be published.

### Design

- **Opaque random tokens, not JWTs.** Revocation needs a database lookup regardless, so
  a JWT would buy nothing and would leak its claims if exposed. 32 bytes from
  `secrets.token_urlsafe`.
- **Only the SHA-256 hash is stored.** A refresh token is high-entropy random data, not
  a guessable secret, so a password hash's work factor would buy nothing and would be
  paid on every refresh. A database leak hands over no usable sessions.
- **Single use with rotation.** Each refresh revokes the presented token and issues a
  replacement.
- **Reuse detection.** Presenting an already-revoked token revokes *every* session for
  that user: the legitimate holder and a thief cannot both have spent the same one-time
  token, so a replay is treated as evidence of theft. Rows are kept after revocation
  rather than deleted, because this needs to distinguish "revoked" from "never existed".
- `/auth/logout` ends one session, `/auth/logout-all` ends all of them and requires
  authentication.
- **Logout is idempotent**, including for unknown tokens — the caller's intent is
  satisfied either way, and reporting the difference would confirm which tokens exist.

### Decision recorded: body, not cookie

The pair is returned in the response body rather than as an `HttpOnly` cookie. That
follows from the API being bearer-token OAuth2 consumed by a separately-served SPA, and
trades XSS resistance for simplicity and CSRF-freedom. Flagged in `PLANNING.md` as worth
revisiting if the compose deployment ends up serving frontend and API from one origin,
where a cookie would be strictly better.

### Gotcha worth remembering

SQLite returns `DateTime(timezone=True)` columns as **naive** datetimes, so comparing a
stored `expires_at` against `datetime.now(UTC)` raises. `rotate_refresh_token`
normalises to UTC before comparing. The same trap will appear anywhere else stored
timestamps are compared, and it will not reproduce on Postgres.

### Frontend contract kept in sync

`api.model.ts` gained `refresh_token` on `TokenResponse` plus a `RefreshRequest`, and
the mock backend now handles `/auth/refresh`, `/auth/logout` and `/auth/logout-all`,
issuing a *different* refresh token each call so UI code that stores the rotated value
is actually exercised. This is the fixtures-typed-against-the-real-contract rule doing
its job: the backend change forced the mock change.

### Verification

```
backend   uv run nox                 lint + mypy --strict (39 files) + 97 tests   green
frontend  npx ng test --watch=false  14 tests passed
```

Migration `c3d4e5f6a7b8` verified up and down against a scratch database; unique index
on `token_hash` and the cascading foreign key confirmed in the emitted schema.

Backend tests were 84, now **97**. New coverage: token issued on login, only the hash
persisted, refresh returns a working access token, rotation, single-use enforcement,
reuse revoking the whole chain, expiry, unknown tokens, logout, logout idempotency,
logout-all across two sessions, logout-all requiring auth, and refresh rejected for a
deactivated account.

### Next up

1. Per-user encrypted LLM provider config; token/cost accounting.
2. Structured logging with request IDs.
3. Phase 4c packaging: `docker compose up`, CI, `SECURITY.md`, `CONTRIBUTING.md`,
   `docs/self-hosting.md`, README rewrite, demo deployment.
4. Migrate `DocumentService` to `HttpClient` against `/cvs` — the frontend still holds
   inline mock data and has no token storage or refresh interceptor yet, which is the
   natural place to consume this work.
5. Then Phase 5 — career profile as the master record.

---

## Session 5 — 2026-07-26

### Project intent clarified: open source, portfolio, other users

The stated purpose widened from "a tool for the author" to "a tool for the author and
other job seekers, likely open source, and portfolio work". `PLANNING.md` gained an
*Intent, audience and distribution* section, a *Phase 4c — Release readiness*, and a
*Scope for a public v1.0*.

What actually changed, as distinct from what merely sounded different:

- **Distribution decided: self-hosted, not author-hosted.** Hosting other people's CVs
  makes the operator a data controller for personal and often special-category data
  (photographs, dates of birth, nationality, disability disclosures), and means paying
  for their LLM calls. Self-hosting removes both and makes the local-first principle
  real. Consequence: `docker compose up` is now a required feature rather than a
  convenience, and per-user LLM configuration is required rather than optional.
- **The mock build becomes the public demo.** Phase 4b already produces a fully static,
  backend-free bundle. Deploying it is the cheapest possible answer to "a portfolio
  project nobody can try" — no cost, no personal data, no signup.
- **v1.0 scope narrowed** to profile → ATS optimisation → tailored CV generation
  (Phases 5, 6, 8). Job sources, assisted apply and LinkedIn review are deferred: they
  carry the most third-party risk and the highest maintenance per unit of value, and the
  product is coherent without them.
- **Security work now outranks features** before publication. Readable source makes
  unfinished auth discoverable, so refresh tokens with revocation land before the repo
  goes public, with `SECURITY.md` alongside.
- **Accessibility promoted from implicit to required.** The frontend currently has no
  ARIA attributes at all. The stated audience — people facing hiring friction —
  correlates with disability, so an inaccessible job tool excludes the people it claims
  to serve.
- **Localisation promoted from *Later*.** CV conventions differ sharply by country
  (photo, date of birth, page length), which only matters once users are not just the
  author.
- Two internal principles became user-facing guarantees in the README: never fabricates
  experience, and not a mass-application tool.

### Correction

An earlier claim in this session that the repository had no `LICENSE` was wrong. It is
present, MIT, and committed at the root. The checks that produced the claim
(`git ls-files`, `ls`) were run from inside `backend/`, and both are cwd-relative, so
neither could see a file at the repository root. Verified with an explicit path.

### Documentation and packaging plan

`PLANNING.md` gained two sections in response to "how do people run this easily":

**Documenting it as open source** — the README in running order (screenshot, demo link,
guarantees, one-command quickstart, all above the fold), the supporting files a reader
expects (`CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, issue templates,
`docs/self-hosting.md` for non-developers, `docs/architecture.md`), and a note that
`PLANNING.md` serves as the decision record rather than a folder of ADRs.

**Packaging: how people actually run it** — four tiers:

1. **Docker Compose**, the default, in Phase 4c. Docker Desktop is the only dependency;
   Ollama is an opt-in compose profile so the stack still starts on a modest laptop.
2. **Installable PWA** against the user's own instance — new Phase 4d. Cheapest possible
   answer to "on my phone", no app store, no second codebase.
3. **Serverless local build** — post-1.0. The key realisation: **the seam already
   exists.** The frontend crosses a single HTTP boundary and mock mode already
   intercepts it, so replacing fixtures with a real client-side implementation of the
   same contract gives a no-server build reusing the entire UI. And because principle 1
   is *deterministic first*, most of the product's value — parseability, keyword
   coverage, gap analysis, scoring, export — needs no model at all, so this is a real
   product rather than a crippled demo.
4. **Capacitor native shell** — only if tier 3 proves itself.

Two risks recorded rather than discovered later: browser storage is **evictable** (iOS
especially), so a serverless build must request persistent storage and treat export as
prompted rather than optional; and the deterministic core would exist twice, in Python
and TypeScript, which is the strongest argument against tier 3. Pyodide is worth
prototyping as the single-source-of-truth alternative before committing to a parallel
TypeScript core.

Also corrected the Stack table, which still listed bcrypt as the hashing scheme after
session 4 replaced it with argon2id.

### Gap found while doing this

1. **There is no CI.** `nox` and the frontend tests exist but run only locally. A public
   repository needs them on every push, both to check contributions and as an honest
   signal. Tracked in Phase 4c; blocked on where the public copy lives, since the only
   remote is self-hosted (open decision 2).

No code changed this session.

---

## Session 4 — 2026-07-26

Batch B, first half: **argon2id with rehash-on-login**, and **rate limiting plus
lockout backoff** on the auth endpoints.

### argon2id

`backend/cv_pal/hashing.py` is new and owns all password hashing; the bcrypt helpers
and the superseded `authenticate_user` were removed from `auth.py`, which now only deals
with tokens and lookups.

- New hashes are argon2id at the OWASP second-recommended configuration (19 MiB,
  2 iterations, 1 lane). Encoded length is 97 characters.
- **bcrypt is retained for verification only.** `verify_password` dispatches on the hash
  prefix, so accounts created before this change keep working.
- `needs_rehash` returns true for every bcrypt hash and for argon2id hashes whose cost
  no longer matches the configuration. `auth_service.authenticate` acts on it during the
  one moment the plaintext exists — a successful login. **Raising the cost later needs
  no migration, only a redeploy.**
- A malformed or unrecognised stored hash is treated as a mismatch, not an exception, so
  one corrupt row cannot crash the login path.
- The 72-byte password ceiling is gone; `DEFAULT_MAX_PASSWORD_BYTES` is now 1024 and
  exists only as a denial-of-service guard. Three tests that encoded the old limit were
  updated rather than deleted, including the CJK byte-vs-character case.
- Migration `b2c3d4e5f6a7` widens `users.hashed_password` from 128 to 255. Verified
  upgrade and downgrade against a scratch database.

### Rate limiting and lockout

`backend/cv_pal/rate_limit.py`: a `RateLimiter` Protocol with an in-process
implementation — sliding-window throttling per client address, plus exponential backoff
per account after `DEFAULT_LOCKOUT_THRESHOLD` consecutive failures, capped at five
minutes. `RateLimitedError` carries `retry_after`, and the error handler now emits a
`Retry-After` header, which meant teaching `handle_app_error` about per-error headers.

Two anti-enumeration details worth keeping:

- Failures are counted for **any submitted email, existing or not**. Counting only real
  accounts would make the lockout itself an account oracle.
- When no account matches, the service still runs a hash before returning `None`, so a
  missing account is not measurably faster than a wrong password.

**Known limitation, stated in the module docstring:** counters are per process, so with
multiple uvicorn workers the effective limit is multiplied by the worker count. Adequate
for a personal deployment; the Protocol exists so a Redis implementation can replace it
when the job queue lands.

The limits are module constants rather than settings — they are not worth an environment
variable until someone needs to tune them per deployment.

### Verification

`uv run nox` green: ruff, `mypy --strict` (38 files), **84 tests** (was 59). Migration
upgrade/downgrade verified against a scratch database, with the widened column
confirmed as `VARCHAR(255)`.

New tests cover: argon2id output format and cost, legacy bcrypt verification, rehash
flagging, passwords past bcrypt's old limit, corrupt-hash handling, sliding-window
expiry, per-key isolation, backoff growth and cap, reset-on-success, the 401→429
transition, `Retry-After`, lockout for unknown emails, and the end-to-end
bcrypt→argon2id upgrade through the login endpoint.

### Notes for next session

- The `limiter` fixture in `conftest.py` injects a **fresh limiter per test**. The
  application limiter is module-level state; without the override, counters leak between
  tests and make them order-dependent. Tests needing a strict quota override
  `get_rate_limiter` again inside the test body.
- Rate-limit tests use a one-request quota deliberately: exhausting the real ten-request
  limit would mean paying for ten argon2 hashes, which is slow by design.

### Next up

1. Refresh tokens with revocation; re-authentication before credential changes.
2. Per-user encrypted LLM provider config; token/cost accounting.
3. Structured logging with request IDs.
4. Migrate `DocumentService` to `HttpClient` against `/cvs`.
5. Then Phase 5 — career profile as the master record.

---

## Session 3 — 2026-07-25

### Zed editor configuration

`.vscode/` is being removed (unused). Added `.zed/` with `debug.json` (6 configs),
`tasks.json` (13 tasks) and `settings.json`.

Notes worth keeping:
- Backend debug configs set `cwd` to `backend/`, so pydantic-settings loads
  `backend/.env` on its own — **no secrets belong in `.zed/`**.
- The FastAPI debug config omits `--reload` on purpose: the reloader runs the app in a
  child process, so breakpoints in the parent never hit. The *backend: dev server* task
  keeps `--reload` for normal work.
- `debugpy` added to the dev extras. It was not installed, and relying on Zed's managed
  adapter to line up with the project venv is less predictable than declaring it.
- `PYDEVD_DISABLE_FILE_VALIDATION=1` set on the debugpy configs to silence the
  frozen-modules warning debugpy prints on Python 3.11+.
- `settings.json` excludes `.venv`, `.nox`, `node_modules`, caches and `dist` from file
  scanning; without it those dominate every search.

### Documentation reorganised

`PLANNING.md` and `PROGRESS.md` moved from `backend/` to `docs/` at the repository
root — they describe both apps, so living under `backend/` was wrong. Added:

- `docs/development.md` — how to run locally. Prerequisites, the frontend-only path,
  the full-stack path, quality checks, migrations, build configurations, and a
  troubleshooting table keyed on the exact error text.
- `docs/README.md` — index of the three documents, plus the user and self-hosting
  guides still to be written.
- `README.md` at the repository root — what CV Pal is, status, one command to get the
  UI running, links into `docs/`.
- `backend/README.md` replaced its one-line description with the actual commands.

Path references inside the moved documents were re-qualified now that they sit at the
root and the repository holds two apps.

### `.env.example` now boots the app as shipped

Verified that a developer following the previous instructions **could not start the
backend**: settings validate at import, so both `CV_PAL_SECRET_KEY` *and* a valid LLM
provider configuration are required. With only a secret key set the app died with
`llm_api_key is required for provider openai`.

`.env.example` now defaults to the local Ollama provider, which needs no credentials
and does not require Ollama to actually be running — only the analyse endpoint touches
it. `cp .env.example .env` plus a generated secret key is now genuinely enough. The
hosted OpenAI block is one uncomment away.

### `AGENTS.md` / `CLAUDE.md` removed from the project

Removed at the user's request, on the basis that the global config carries the context.
It did not: the global file held only the git rule, while the instruction to read
`PLANNING.md`/`PROGRESS.md` and to record progress lived in `backend/AGENTS.md`.

That instruction has been generalised into `~/.claude/CLAUDE.md` (and `AGENTS.md`) as a
project-documentation convention: read `docs/PLANNING.md` and `docs/PROGRESS.md` when
present, and append to `PROGRESS.md` before finishing. Nothing project-specific is
needed in this repository as a result — the Python conventions come from the
`python-developer` skill.

### Verification

Backend `uv run nox` green (lint, `mypy --strict`, 59 tests) after the docstring and
README edits. Every relative link in `README.md`, `docs/README.md`,
`docs/development.md` and `docs/PLANNING.md` resolved against the filesystem.

---

## Session 2 — 2026-07-25

> Note: this file was missing at the start of this session — deleted after session 1 and
> never committed, so git could not restore it. Reconstructed here. **Commit it** so the
> next session does not lose the history again.

### Repository safety audit (pre-publication)

Asked whether anything must be withheld before pushing or going public. **Verdict:
nothing.** Checks run:

- Secret scan (regex for OpenAI/Anthropic/AWS keys, private keys, JWTs, bcrypt hashes,
  generic `secret=`/`api_key=` assignments) across **every blob in all history**, not
  just the working tree. One hit: the literal string `API_KEY` in `PLANNING.md`, i.e.
  the `CV_PAL_OPENAI_API_KEY="your-openai-api-key"` placeholder.
- `backend/cv_pal.db` **was committed** in early history. Extracted the historical blob
  and queried it: **0 user rows**, empty tables. No personal data.
- `backend/uploads/*` — 8 files **were committed**. Contents are literally
  `fake pdf content` and `content`.
- `.gitignore` verified with `git check-ignore`: `.env`, `*.db`, `backend/uploads/`,
  `.venv`, `.nox`, caches all correctly ignored.
- `alembic.ini` carries no credentials.

Two follow-ups, neither a security issue:
- `frontend/cv-pal/src/environments/*.ts` is untracked **and not gitignored**, while
  `angular.json` references `environment.ts` in `fileReplacements` — a fresh clone will
  not build until these are committed. They contain only URLs.
- The remote is `gitssh.seventhlab.xyz`, so history is presumably already pushed.
  Cleaning the junk blobs would be cosmetic and needs a force-push; not worth it.

### Password policy (new requirement)

Specified in `PLANNING.md` → *Password policy*, implemented in `backend/cv_pal/passwords.py`.

**A live bug was found and fixed.** bcrypt raises above 72 bytes of input rather than
truncating, and `UserCreate.password` was unbounded — so registering with a long
passphrase returned a **500**, not a validation error. Verified against the installed
bcrypt: 72 bytes hashes fine, 73 raises `ValueError`.

Implemented: 12-character minimum; 72-**byte** ceiling measured on the UTF-8 encoding
(a 30-character CJK password exceeds it while looking short); screening against a local
common-password list with padding-stripped variants, so `Password123!` is caught as
readily as `password`; rejection of values derived from the user's own email or the app
name. The existing "must contain a digit" rule is retained — NIST advises against
composition rules, but removing a check is a regression until screening has proven
itself, so it is marked for later removal rather than dropped now.

The check moved from a field validator to a `@model_validator(mode="after")` because
context screening needs the email alongside the password.
`test_policy_limit_agrees_with_the_hasher` guards the policy ceiling against bcrypt's,
so the two cannot drift apart and reintroduce the 500.

The blocklist is local by design (`backend/cv_pal/common_passwords.py`, a frozenset rather than
a data file so it needs no package-data wiring): screening has to work in `local_only`
mode, where nothing may leave the machine.

### Frontend mock mode (new requirement)

Specified in `PLANNING.md` → *Frontend mock mode*, implemented under `frontend/cv-pal/src/mocks/`.

Found on inspection that the frontend does **not** call the API at all — services such
as `DocumentService` hold ~100 lines of mock data inline and expose it through signals,
and `provideHttpClient` was never registered. So mock mode had to be built from the
infrastructure up:

- `environment.model.ts` gains `useMocks`, `mockLatencyMs`, `mockErrorRate`;
  `environment.mock.ts` added; `mock` configuration wired into `angular.json` for both
  `build` and `serve`; `npm run start:mock` / `build:mock`.
- `api.model.ts` mirrors the backend Pydantic response schemas, so fixtures are
  type-checked against the real contract.
- `mock-backend.ts` — in-memory store seeded from fixtures, routing the endpoints the
  backend actually exposes (`/auth/*`, `/users/me`, `/cvs`, `/reviews/*`, `/health`).
  Mutations persist for the page lifetime, so upload → analyse → accept is clickable.
- `mock-api.interceptor.ts` — latency simulation, error injection, and a **404 for any
  unmapped route** so a missing fixture is loud instead of silently hanging.
- Registered conditionally: `mockInterceptors()` returns `[]` in non-mock builds, so
  mock mode can never act as a fallback for a failing real API.

`app.spec.ts` was already failing before this session — the CLI scaffold test asserted
an `<h1>Hello, cv-pal</h1>` that commit `e0e59c8` removed when the shell became a bare
`<router-outlet />`. Replaced with an assertion that matches the actual shell.

### Verification

```
backend   uv run nox                    lint + mypy --strict + 59 tests   all green
frontend  npx ng test --watch=false     13 tests passed (2 files)
frontend  npx ng build -c mock          bundle generated
frontend  npx ng build -c production    bundle generated
```

Mock code confirmed **absent from the production bundle** — grepping the built output
for `MockBackend` / `No mock route` returns nothing, so the build-time
`environment.useMocks` constant lets it tree-shake away.

Still not verified: no call has been made to a real LLM provider.

### Decisions

- **Frontend services were deliberately not migrated to `HttpClient` this session.**
  Their endpoints (jobs, profile, ai, dashboard) do not exist in the backend yet, and
  converting the signal-based synchronous API to async would refactor component
  templates for no present gain. The mock infrastructure is proven by unit tests
  instead, and is waiting for services as their endpoints land.
- Dev `apiUrl` corrected from `http://localhost:3000/api` to `http://localhost:8000`:
  FastAPI serves on 8000 and mounts routers at the root with no `/api` prefix.

### Next up (batch B, revised)

1. Auth hardening: rate limiting and lockout backoff on `/auth/login`, refresh tokens
   with revocation, re-authentication before credential changes.
2. argon2id with rehash-on-login, replacing bcrypt and its 72-byte limit.
3. Per-user encrypted LLM provider config; token/cost accounting.
4. Structured logging with request IDs + consistent error envelope.
5. Migrate `DocumentService` to `HttpClient` against `/cvs` as the reference
   implementation, exercising mock mode for real.
6. Then Phase 5 — career profile as the master record.

---

## Session 1 — 2026-07-25

### Audit findings

Full read of `backend/cv_pal/` and `backend/tests/`. Baseline before any change: **18 of 22 tests
failing**, dev dependencies not installed, so neither ruff nor mypy had ever run in the
project venv.

**Broken (not just untidy):**

1. **No foreign keys on any model.** `CV.user_id` and `Suggestion.cv_id` were plain
   indexed integers while `relationship()` was declared on both sides. SQLAlchemy cannot
   infer a join condition, so *every* mapper failed to initialise — the cause of all 18
   test failures.
2. **`routers/reviews.py` was sync code against an async session.** It imported
   `sqlalchemy.orm.Session`, used `db.query(...)`, and declared handlers as `def`, while
   `get_db` yields an `AsyncSession` (which has no `.query()`). Every reviews endpoint
   would have raised `AttributeError` at runtime.
3. **Schema drift.** Only one migration existed (`users`). The `cvs` and `suggestions`
   tables were never migrated — they existed solely because `Base.metadata.create_all()`
   ran in the app lifespan. A fresh Postgres deploy via Alembic would have been missing
   two tables.
4. **`backend/alembic/env.py` used a sync engine** (`engine_from_config`) against an
   `sqlite+aiosqlite://` URL — migrations could not run at all.
5. **Sync LLM client inside async handlers.** `openai.OpenAI` blocks the event loop for
   the whole duration of a completion; with a local Ollama model that is tens of seconds
   during which the server serves nobody.
6. **Test fixtures were sync** (`create_engine`, `sessionmaker`) against the async app,
   and wrote a real `test.db` file.

**Security:**

7. `secret_key` defaulted to `"change-me-in-production"`.
8. Upload validation trusted the file extension only; no magic-byte check, and the whole
   file was read into memory before the size check.
9. No rate limiting anywhere, including on login.
10. `get_current_user` returned a `UserResponse` but every caller annotated it as `User`.

**Tooling:**

11. `pyproject.toml` restated six flags that `strict = true` already implies.
12. Nox had no test session; `mypy --strict` never covered `backend/tests/`.
13. Every dependency used `Depends()` as a default value, needing 20+ `# noqa: B008`.

### Changes applied

- `models.py` — real `ForeignKey` with `ondelete="CASCADE"`, `func.now()` server
  defaults, timezone-aware `DateTime`, sized `String` columns, cascade on relationships.
- `config.py` — `SettingsConfigDict`, `LLMProvider`/`StrEnum`, `secret_key` required
  with no default, `SecretStr` for keys, `local_only` switch, validation that a hosted
  provider has an API key.
- `dependencies.py` (new) — `Annotated` DI aliases; all 20+ `# noqa: B008` removed.
- `exceptions.py` + `error_handlers.py` (new) — domain exception hierarchy; services
  raise these, the edge translates them to HTTP.
- `services/` (new) — `cv_service.py`, `review_service.py`: business logic moved out of
  routers, framework-free and unit-testable. Ownership enforced inside the query (a join
  for suggestions), so another user's resource is indistinguishable from a missing one.
- `llm.py` / `prompts.py` / `parsing.py` / `storage.py` (new) — `AsyncOpenAI` behind an
  `LLMClient` Protocol, versioned prompts, structured-output validation with one
  corrective retry, blocking file parsing moved to a worker thread, streamed uploads
  with magic-byte checks and server-generated storage keys.
- `main.py` — `create_all()` removed (Alembic owns the schema), exception handlers
  registered, `/health/live` + `/health/ready`.
- `backend/alembic/env.py` — async migration support; new migration adds `cvs` + `suggestions`
  with their foreign keys and corrects the drift in `users`.
- `backend/tests/conftest.py` — async fixtures, in-memory database, `httpx.AsyncClient` +
  `ASGITransport`, fake LLM provider so tests never touch a real model.
- `noxfile.py` / `pyproject.toml` — tests session added, `mypy --strict` covers
  `cv_pal` + `tests`, ruff rule set expanded.

### Verification

`uv run nox` — all three sessions green: ruff (31 files), `mypy --strict` (30 files, no
issues), pytest (39 passed). Baseline was 18 failed / 4 passed with no lint or type
checking installed at all.

Migrations verified end to end against a scratch database: `alembic upgrade head`
creates all three tables with foreign keys present, `alembic downgrade base` unwinds
cleanly.

### Notes

- `mypy --strict` passes with **no** `# type: ignore` in first-party code. The only
  concession is `ignore_missing_imports` for `pypdf` and `docx`, which ship no stubs.
- `D100`/`D104` (module and package docstrings) are switched off deliberately.
- Several `# noqa: S105` remain on constants whose *names* contain "password" or
  "token"; all are messages or scheme names, not secrets. Note that ruff wants the
  `noqa` on the *string* line, not the opening-paren line, after formatting.
- `ConflictError` maps to **400**, not 409, to preserve the existing duplicate-email
  contract the frontend may depend on.
- `backend/tests/conftest.py` primes `CV_PAL_SECRET_KEY` in `os.environ` before importing
  anything from `cv_pal`, because settings validate at import time. The `# noqa: E402`
  imports below that are intentional.
- Stale artefacts left in place: `backend/test.db` (nothing writes it now) and
  `backend/cv_pal.db` (the dev database).

### Decisions

- **Stay on SQLite for now**, but write Postgres-compatible code. Revisit at Phase 7
  when semantic search needs pgvector. (`PLANNING.md` open decision 2 resolved.)
- **Multi-user from the start.** Every table already carries `user_id`. (Open decision 1
  resolved.)
- Migrations own the schema, always. `create_all()` is allowed in tests only.
