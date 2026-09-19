# Manual test plan

For the state of the app as of **session 31**. Replaces the session 18 plan, which
covered less than half of what now exists.

Each step is *action → what you should see*. **Anything that fails is worth recording
rather than fixing in the moment** — several checks depend on the ones before them, and
a note written while it is fresh is worth more than a half-fix.

> **Short on time?** Do §1 (Docker, ~10 min — it has never been run), then §8–§12, which
> are the parts built in the last five sessions and the least exercised by anyone.

**Read §14 before reporting anything.** It lists behaviour that looks like a bug and is
not, so you do not spend time on things already known and deliberate.

---

## 0. Pick a path

| Path | Use it when | Section |
| --- | --- | --- |
| **Docker** | You want to test what a *user* gets | §1 |
| **From source** | You want reload, logs and a debugger | §2 |
| **Mock mode** | You want the UI with no backend at all | §3 |

Docker and source both work on Windows and Arch. Commands are given for both throughout;
where only one block appears, it is identical on each.

---

## 1. Docker — the path that has never been executed

`README.md` and `docs/self-hosting.md` have claimed since session 7 that
`docker compose up` is the way in. **The containers have never been built or run.**

This section is therefore not setup — **it is the test**. Expect it to be the most
likely part of this document to fail, and record exactly where.

### 1a. Install Docker

**Arch Linux**

```bash
sudo pacman -S --needed docker docker-compose
sudo systemctl enable --now docker.service
sudo usermod -aG docker "$USER"     # then log out and back in, or: newgrp docker
```

**Windows** — install [Docker Desktop](https://www.docker.com/products/docker-desktop/),
start it, and wait for the whale icon to stop animating.

Both:

```bash
docker compose version
```

| Check | Expected |
| --- | --- |
| Prints a version | `Docker Compose version v2.x` or later |
| Arch: `docker ps` without `sudo` | A table, not a permission error |

### 1b. Configure

**Arch / Git Bash**

```bash
cd /path/to/cv-pal
cp .env.docker.example .env
openssl rand -hex 32
```

**Windows PowerShell**

```powershell
cd C:\Dev\cv-pal
Copy-Item .env.docker.example .env
-join ((1..32) | ForEach-Object { '{0:x2}' -f (Get-Random -Maximum 256) })
```

Paste the result after `CV_PAL_SECRET_KEY=` in `.env`. Nothing else needs changing.

### 1c. Build and start

This plan builds from source rather than pulling the published images, because the
point is to test what is in the working tree. That is what the build overlay is for —
plain `docker compose up` would pull from ghcr.io and test nothing.

Without a local model — everything except the AI review screen works:

```bash
docker compose -f docker-compose.yml -f docker-compose.build.yml up -d --build
```

The first build downloads Python and Node base images and compiles the frontend.
**Several minutes is normal.** Watch it rather than backgrounding it the first time by
dropping the `-d`.

| Check | Expected |
| --- | --- |
| `docker compose ps` | `backend` and `frontend` both `running`, backend `(healthy)` |
| `docker compose logs backend \| head -20` | `Applying database migrations...` then uvicorn startup |
| <http://localhost:8080> opens | The login screen |
| `docker compose logs frontend` | nginx access lines, no `emerg` or `crit` |

**Failure modes worth distinguishing**, because they point at different things:

| Symptom | Where the problem is |
| --- | --- |
| Build fails in the `node` stage | Frontend Dockerfile or the lock file |
| Build fails in the `uv sync` stage | `uv.lock` out of step with `pyproject.toml` |
| Backend restarts in a loop | `CV_PAL_SECRET_KEY` empty, or migrations failing |
| Page loads but every API call 404s | nginx `/api/` proxy — the trailing slash on `proxy_pass` |
| Page loads but every API call 502s | Backend not healthy yet, or not reachable on the compose network |

### 1d. With a local model (optional, needs ~8 GB free RAM)

```bash
docker compose --profile ollama up -d
docker compose exec ollama ollama pull llama3
```

Only the **AI review** screen (§13) needs this. Skip it and everything else still works
— that is the design, and it is worth confirming rather than assuming.

### 1e. Stopping, and starting over

```bash
docker compose down                 # stop, keep your data
docker compose down -v              # stop and DELETE the database and uploads
docker compose logs -f backend      # follow the backend log
docker compose exec backend sh      # a shell inside the container
```

`down -v` is how you get back to a clean slate for §4. It is destructive — that is the
point, but do read it twice.

---

## 2. From source

### 2a. Prerequisites

**Arch Linux**

```bash
sudo pacman -S --needed nodejs npm
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows PowerShell**

```powershell
winget install --id=astral-sh.uv -e
winget install --id=CoreyButler.NVMforWindows -e
nvm install 24.19.0
nvm use 24.19.0
```

| Check | Expected |
| --- | --- |
| `node --version` | **v22.22.3+, v24.15.0+ or v26+** — the Angular CLI hard-fails below these |
| `uv --version` | Any recent version |

> Node **v24.14.0 will not work** and fails with a clear message. If `nvm use` reports
> success but `node --version` disagrees, a standalone Node install is ahead of nvm on
> `PATH` — check `where.exe node` on Windows, `which -a node` on Arch.

### 2b. Backend

```bash
cd backend
uv sync --extra dev
cp .env.example .env          # then set CV_PAL_SECRET_KEY
uv run alembic upgrade head
uv run uvicorn cv_pal.main:app --host localhost --port 8000 --reload
```

> `--host localhost` is deliberate. `ng serve` binds IPv6 and uvicorn defaults to IPv4,
> so every API call otherwise depends on the browser's fallback between them.

> Dev dependencies live in `optional-dependencies`, so it is **`uv run --extra dev`** for
> anything test-related. Plain `uv run pytest` fails with "program not found".

### 2c. Frontend

Second terminal:

```bash
cd frontend/cv-pal
npm install
npm start
```

| Check | Expected |
| --- | --- |
| `curl -s localhost:8000/health/ready` | `{"status":"ok","database":"ok"}` |
| <http://localhost:4200> | Redirects to `/login` |
| Browser console | No CORS errors — `.env.example` already allows `:4200` |

---

## 3. Mock mode — no backend, no account

The public-demo path. **Stop the backend first**: if it is running and mock mode still
works, that proves nothing.

```bash
cd frontend/cv-pal
npm run start:mock
```

| Step | Expected |
| --- | --- |
| Open <http://localhost:4200> | Lands on the dashboard — **no login screen** |
| Career Profile | The seeded profile: 3 roles, several skills, 1 education |
| Jobs | Three postings, one **blocked** by a non-negotiable |
| Jobs → *Tailor my CV* | A document, built from the seeded profile |
| Jobs → *Draft one* (cover letter) | A letter, similarity 0 |
| Browser console | **No `[mock] No mock route` warnings** |

A `No mock route` warning means a screen calls an endpoint the mock backend does not
implement. Note which — it is a real gap, not a test failure.

Restart the backend and return to `npm start` for everything below.

---

## 4. Account and the password policy

Use **Create an account** on `/login`.

| Password | Expected |
| --- | --- |
| `short1` | Rejected — at least 12 characters |
| `passwordpassword` | Rejected — no digit |
| `Password123!` | Rejected — common password, despite satisfying every composition rule |
| your own email | Rejected — context-specific value |
| `orbital-lemur-7-quilt` | Accepted |

| Step | Expected |
| --- | --- |
| Register with an accepted password | Signed in, land on the dashboard |
| Register the same email again | Rejected — already registered |
| Sign out, sign in with the wrong password | Stays on `/login`, error shown, **no redirect** |
| Six wrong passwords in a row | `429`, with a `Retry-After`. Restarting the backend clears it |

Two failure modes worth recording: *"Something went wrong. Is the API running?"* means
the message never reached the UI, and a bracketed blob like `[object Object]` means a
validation error is being rendered raw instead of unwrapped.

---

## 5. Career profile

**Give this real data.** Everything downstream — matching, tailoring, the letter — is
only as good as what is here, and testing with `asdf` tells you nothing.

| Step | Expected |
| --- | --- |
| Fill headline, summary, location | Saves, survives a reload |
| Add 2–3 real roles with dates | Listed newest first |
| Leave one role's end date empty | Shows as **current** |
| Add an education entry | Listed |
| Add 5–8 real skills | Listed |
| **Cite roles as evidence on most of them** | Marked evidenced |
| **Leave one skill with no evidence** | Marked unevidenced — §10 depends on this |
| Add `Postgres`, `K8s` or `JS` if they apply to you | Stored with your spelling — §10 depends on this too |
| Add the same skill twice with different spellings (`K8s`, `Kubernetes`) | Second one rejected as duplicate |

### CV import

| Step | Expected |
| --- | --- |
| Upload a real CV (PDF or DOCX) | Appears in the list |
| Import from it | A **proposal**, nothing written yet |
| Reject some entries, confirm the rest | Only the confirmed ones appear on the profile |
| Upload a 15 MB file | Rejected — over the 10 MiB cap |
| Rename a `.txt` to `.pdf` and upload | Rejected — magic bytes, not the extension |

---

## 6. Goals — including geography

This screen decides what §8 and §9 do. Fill it properly.

| Step | Expected |
| --- | --- |
| Add 2–3 target roles, one per line | Saved |
| Tick **Remote** under *How you will work* | Saved |
| Tick **Non-negotiable** with nothing selected | Warning that nothing can ever match |
| Under **Where you can work**, add `Portugal` | Saved |
| Click the `Europe`, `EU`, `EMEA` chips | Added to the box, and disappear from the suggestions |
| Tick the location **Non-negotiable** | Saved |
| Reload | Everything comes back |

> **The app does not know Portugal is in Europe, and that is deliberate.** It has no
> authoritative containment data and guessing would silently hide jobs, so it compares
> your words against the posting's. If you list only `Portugal`, a posting saying
> `Europe` will *not* match. **List the wider regions too** — that is what the chips are
> for. If this feels wrong in use, say so; it is a real design trade-off, not an
> oversight.

---

## 7. CV analysis — no model needed

| Step | Expected |
| --- | --- |
| Choose an uploaded CV, press analyse with **no posting pasted** | A parseability report only |
| Paste a real posting (>20 chars), analyse again | Parseability **and** keyword coverage |
| Read the missing-keyword list | Are these real skills, or recruiting noise? **Record any noise you see** |

Session 29 removed a lot of prose from these lists (`building`, `built`, `companies`,
`e.g`). Whether enough is gone is exactly what real postings will tell us.

---

## 8. Job discovery — Remotive

The reason this exists: Greenhouse and Lever answer *"what is open at this company"*, so
you must already know the company. Remotive answers *"what remote roles are open at
all"*.

| Step | Expected |
| --- | --- |
| Jobs → **Watched sources** → source picker | Remotive first, then Greenhouse, Lever |
| Read the **Covers** and **Contract types** lines | They change per source |
| Select Greenhouse | Contract types reads *"Not stated"* — it genuinely is not published |
| Select Remotive | The identifier becomes a **category dropdown**, not a text box |
| Watch `Software Development` | Appears in the list, *never synced* |
| **Sync now** | *"Found N posting(s), added N new."* |
| **Sync now** again | Found N, **added 0** — idempotent |
| Watch `DevOps` too, then **Sync all** | One call, both sources, a summary line |

| Check | Expected |
| --- | --- |
| Each posting shows a contract chip | `Full-time`, `Contract`, `Freelance`… |
| Some postings show **no** chip | Correct — the source did not state one, and guessing would be worse |
| Locations read `Remote · Europe`, `Remote · USA` | Remotive is remote-only by construction |
| Postings link back to Remotive | Their terms require attribution, and it should be visible |

> Remotive publishes a rotating feed of ~30 roles delayed 24 hours. **A quiet category
> is normal**, not a failure. Sync once a day; their terms ask for no more.

Also worth one pass:

| Step | Expected |
| --- | --- |
| Paste a real posting on the **Paste** tab | Saved and scored |
| Add a Greenhouse or Lever link on the **Link** tab | Read through the board's API |
| Paste a LinkedIn or careers-page link | **Refused**, with a message pointing at Paste |

That refusal is deliberate — see §14.

---

## 9. Geography and non-negotiables

With **Remote** and your locations both marked non-negotiable:

| Check | Expected |
| --- | --- |
| A `Remote · USA` posting | Under **Ruled out by your non-negotiables**, reason naming `USA` |
| A `Remote · Europe` posting | Ranked normally, reason *"Open to Europe, where you said you can work"* |
| A `Remote · Worldwide` posting | Ranked normally — restricts nobody |
| A posting with no location | **Not** blocked — silence is not evidence you cannot be there |
| Each score | Reads back as four sentences: skills, title, arrangement, location |

**The thing to judge:** is anything blocked that you could actually have taken? That is
the failure that costs you a job, and it is the one worth reporting immediately.

---

## 10. Tailored CV

On any posting, press **Tailor my CV**.

| Check | Expected |
| --- | --- |
| The explanation appears **above** the document | Deliberate — the document is the easy part to trust |
| **Brought forward for this posting** | Each skill names the posting term and the role evidencing it |
| The unevidenced skill from §5 | **Not in the document**, listed under *left out for having no role behind them* |
| **Asked for, and not on your profile** | Named as gaps, and **never written into the CV** |
| The document itself | Every line traceable to your profile |
| Press Tailor again | Identical output |

### The substitution transform

Only if you added `Postgres`, `K8s` or `JS` in §5, against a posting using the long form:

| Check | Expected |
| --- | --- |
| **Your words, in the posting's spelling** | e.g. `Postgres → PostgreSQL` |
| The document | Uses the posting's spelling |
| A skill outside software | **Never** substituted, whatever the posting shouts |

> This only fires where the alias map asserts two spellings name one thing — 37 software
> terms. That is also why it never fires outside software: there is no equivalence data,
> so it refuses rather than guessing.

**Verify a gap is never smuggled in.** Pick a posting demanding something you do not
have. It must appear in the gap list and **nowhere in the document**. If you ever find a
skill in your generated CV that is not on your profile, stop and record it — that is the
most serious defect this app can have.

---

## 11. Exports

| Step | Expected |
| --- | --- |
| **Copy** | Markdown on the clipboard |
| **.docx** | Downloads as `CV - <Company> - <Role>.docx` |
| Open it in Word or LibreOffice | Single column, real headings, contact details in the body |
| **.pdf** | Downloads as `CV - <Company> - <Role>.pdf` |
| Open it | One page for a short profile, selectable text |
| **Select the text in the PDF and copy it** | Real text, not an image |

| Check | Expected |
| --- | --- |
| Neither file has anything in a page header or footer | Parsers routinely drop those |
| No tables anywhere | Same reason |
| Dates read `Jan 2022 - Present` | Machine-readable form |
| The *parses N/100* line says nothing blocking | Our own checker, on our own output |

> **Submit the `.docx` where a portal accepts either.** It is structured data a parser
> reads directly; a PDF is a page description it must reconstruct. The PDF is for humans.

---

## 12. Cover letter and the self-similarity check

**This is the section most worth your attention**, because the honest answer to "is this
useful?" is genuinely unknown.

| Step | Expected |
| --- | --- |
| On a posting, **Draft one** | A letter assembled from your profile |
| Read the warning above it | Says plainly this is a **scaffold, not a letter** |
| Find the `[Write one paragraph here: …]` prompt | The part nothing can write for you |
| Similarity | **0%** — nothing kept yet to compare against |
| **Keep this letter** | Saved |
| Go to a *different* posting, **Draft one** | Similarity **~60%, warned** |
| Replace the body with something you actually wrote | — |
| **Keep this letter** | Similarity drops to near **0%** |

| Check | Expected |
| --- | --- |
| Every fact in the letter is yours | Evidence lines name the role behind each claim |
| The evidence lines match the tailored CV | The two must not disagree |
| Nothing lowers the similarity except real writing | It is not shaped to be gamed |

**The judgement call to make:** does the scaffold save you time, or would you rather
start from an empty box? Both are legitimate answers and the answer changes what gets
built next. Say which.

---

## 13. LinkedIn, and the AI review

### LinkedIn (no model needed)

| Step | Expected |
| --- | --- |
| Import your LinkedIn profile PDF | Parsed — name, headline, roles |
| Read the review | Per-section completeness, keyword coverage against your target roles |
| If you imported the PDF | A note that it is lossy, with the menu path to request the full export |
| Request LinkedIn's data export, import the ZIP when it arrives | **Richer data must not be overwritten by a later PDF import** |

The PDF route carries only your top three skills and no role descriptions. Recruiter
search filters on skills, so that is the section that matters most.

### AI review (needs a model — §1d, or Ollama locally)

| Step | Expected |
| --- | --- |
| With **no** provider configured | The screen says so plainly rather than failing oddly |
| With one configured, review a CV | Text suggestions you can accept or reject |

---

## 14. Known and deliberate — do not report these

Time saved is the point of this section.

| You will see | Why |
| --- | --- |
| **Several near-identical postings** from one company in different cities | They *are* distinct postings. Dedupe is exact by content hash; fuzzy dedupe is a real feature, not yet built |
| A LinkedIn or careers-page link **refused** | There is no general URL fetcher, on purpose: fetching a user-supplied URL server-side is a request-forgery primitive on a self-hosted box |
| **No way to view an uploaded CV's text** | Known gap since session 26. Parseability findings point at text you cannot see |
| **Documents**, **AI Tools** and **Dashboard** are thin | Not rebuilt since the API landed |
| A Remotive category returning **nothing** | ~30 roles rotating daily; quiet categories are normal |
| Some **noise still in gap lists** | Vocabulary tuning is incremental — but do record the specific words |
| The **cover letter reads like a template** | It is one. That is what the similarity check exists to tell you |
| `Remote · Brazil` ranked but not blocked | Only blocked if you set locations *and* marked them non-negotiable |

---

## 15. What to record

Append findings to the bottom of this file, or open one issue per finding. For each:

1. **Which section and step.**
2. **What you did** — including the posting or profile data, if it matters.
3. **What happened** vs what this document said would happen.
4. **The evidence**: the browser console, `docker compose logs backend`, or the DevTools
   Network entry (status, or `CORS error` / `Failed to fetch`).

Two judgements are worth writing down even when nothing breaks, because they decide what
gets built next:

- **§10** — would you send the generated CV as-is, after an edit, or not at all?
- **§12** — does the letter scaffold save you time, or waste it?

And one number: **how long the whole pass took.** If this document takes two hours, it is
too long to run often, and that is itself a finding.

---

## Results

> _Record findings below. Date each pass._

### Pass 1 — <date>

| § | Step | Expected | Actual | Notes |
| --- | --- | --- | --- | --- |
|   |   |   |   |   |
