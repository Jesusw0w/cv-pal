# Running CV Pal on your own machine

For anyone who wants to *use* CV Pal rather than develop it. No Python, no Node, no
command-line tooling beyond Docker.

Everything stays on your computer: your CV, your career history, and — if you use the
local model option — the AI processing too.

---

## 1. Install Docker

- **Windows / macOS:** [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- **Linux:** Docker Engine and the Compose plugin from your package manager

Check it works — this should print a version:

```bash
docker compose version
```

## 2. Download CV Pal

```bash
git clone https://github.com/Jesusw0w/cv-pal.git
cd cv-pal
```

No git? Download the ZIP from the repository page and unpack it.

## On Windows: skip to the end

Double-click **`start-cv-pal.cmd`** in the folder you just downloaded. It does steps 3
and 4 for you — starts Docker Desktop if it is not running, writes the configuration
file, generates the secret key, checks your local model, and opens the app when it is
ready. Run it again any time you want to start CV Pal.

If something goes wrong, run it from a terminal with `-CheckOnly`: it reports what is
missing without waiting for anything to build.

The rest of this page is the manual path, and is worth reading for the backup and
troubleshooting sections whichever way you start it.

## 3. Create your configuration

```bash
cp .env.docker.example .env
```

Open `.env` in any text editor. You need to fill in **one** value — a secret key, which
signs your login sessions. Generate one:

```bash
openssl rand -hex 32
```

Paste the result after `CV_PAL_SECRET_KEY=`. It should look like:

```
CV_PAL_SECRET_KEY=8f2a9c1d4e6b8a0f2c4e6a8d0b2f4c6e8a0d2b4f6c8e0a2d4b6f8c0e2a4d6b8f
```

Keep this file private. It is ignored by git and will not be committed.

## 4. Start it

**With a local AI model** (nothing leaves your computer, needs about 8 GB of free RAM):

```bash
docker compose --profile ollama up -d
docker compose exec ollama ollama pull llama3
```

**With Ollama already installed on this computer** — the better option if you have a
graphics card, because the container above cannot use it on Windows and would download
its own copy of every model:

```bash
docker compose up -d
```

and in `.env`, set:

```
CV_PAL_LLM_BASE_URL=http://host.docker.internal:11434/v1
CV_PAL_LLM_MODEL=<one of the models `ollama list` shows you>
```

**Without AI for now** (upload and manage CVs; analysis will report the model as
unavailable):

```bash
docker compose up -d
```

Then open **<http://localhost:8080>** and create an account.

The first start takes a few minutes while the images download. Later starts take seconds.

---

## Using a hosted AI model instead

A local model is private but slower and less capable. To use OpenAI instead, edit `.env`,
comment out the four Ollama lines, and uncomment the hosted block:

```
CV_PAL_LLM_PROVIDER=openai
CV_PAL_LLM_API_KEY=sk-...your key...
CV_PAL_LLM_MODEL=gpt-4o-mini
CV_PAL_LOCAL_ONLY=false
```

Then `docker compose up -d` again. **Your CV text is sent to OpenAI** in this mode. If
that is not acceptable, keep `CV_PAL_LOCAL_ONLY=true` and the app will refuse to contact
any hosted provider at all.

---

## Everyday commands

| What | Command |
| --- | --- |
| Start | `docker compose up -d` |
| Stop | `docker compose stop` |
| Stop and remove containers (data is kept) | `docker compose down` |
| View logs | `docker compose logs -f` |
| Update to a new version | `docker compose pull && docker compose up -d` |

Updating is always something you asked for: nothing downloads a new version on its own,
so the app cannot change between the evening you drafted an application and the morning
you sent it. To stay on a known version instead of the newest, set `CV_PAL_VERSION` in
`.env` — `CV_PAL_VERSION=0.1.0` pins it, and the released versions are listed on the
[releases page](https://github.com/Jesusw0w/cv-pal/releases).

Your data lives in a Docker volume called `cv-pal_cv-pal-data` and survives `down` and
updates. It is deleted only if you run `docker compose down -v`.

## Backing up

Your CVs and account live in one volume. Copy it somewhere safe:

```bash
docker run --rm -v cv-pal_cv-pal-data:/data -v "$PWD":/backup alpine \
  tar czf /backup/cv-pal-backup.tar.gz -C /data .
```

Restore it into a fresh volume:

```bash
docker run --rm -v cv-pal_cv-pal-data:/data -v "$PWD":/backup alpine \
  tar xzf /backup/cv-pal-backup.tar.gz -C /data
```

## Removing it completely

```bash
docker compose down -v
```

This deletes the containers **and your data**. There is no undo.

---

## If something goes wrong

| What you see | What to do |
| --- | --- |
| `CV_PAL_SECRET_KEY` error, backend keeps restarting | The key is empty in `.env`. Generate one as in step 3. |
| Browser shows "connection refused" | Give it a minute — the UI waits for the backend to report healthy. Then `docker compose logs backend`. |
| Analysis returns "language model is unavailable" | Most often the model named in `CV_PAL_LLM_MODEL` is not installed — `ollama list` shows what is. Otherwise check Ollama is running (`docker compose ps`), or that the hosted API key is valid. Nothing checks this at start-up yet, so the stack reports healthy either way. |
| `local_only is enabled; llm_base_url ... is not on this machine` | `CV_PAL_LOCAL_ONLY=true` and the base URL points somewhere public. Either point it at a local address, or set `CV_PAL_LOCAL_ONLY=false` and accept that your CV text leaves the machine. |
| Locked out — you have forgotten your password | There is no reset email, because a self-hosted instance usually has no mail server and a link that cannot be delivered is worse than none. Reset it from a terminal on this machine instead: `docker compose exec backend python -m cv_pal.admin reset-password you@example.com`. It asks for the new password twice and signs out every device. |
| A blank page after updating | A browser tab left open across the update is running the old app. Reload the page. |
| "port is already allocated" | Something else uses 8080. Change the `ports` line in `docker-compose.yml` to `"127.0.0.1:9090:8080"` and use port 9090. |
| Ollama is very slow, or the machine freezes | The model is too large for your RAM. Try a smaller one: `docker compose exec ollama ollama pull llama3.2:3b`, then set `CV_PAL_LLM_MODEL=llama3.2:3b` in `.env`. |

## A note on access

By default CV Pal listens only on `127.0.0.1`, meaning **only your own computer can
reach it** — not other devices on your network, and not the internet. That is
deliberate: your CV is one of the most sensitive documents you own.

Exposing it more widely (to use it from your phone, say) means editing the `ports` line
in `docker-compose.yml`. Do that only on a network you trust, and put HTTPS in front of
it if it will be reachable from the internet.
