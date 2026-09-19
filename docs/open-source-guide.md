# Running this as an open source repo, for someone new to GitHub

You already have the boring-but-essential parts: `LICENSE`, `CONTRIBUTING.md`,
`CODE_OF_CONDUCT.md`, `SECURITY.md`, and CI at `.github/workflows/ci.yml`. This doc is
the missing piece — what actually happens day to day once the repo is public, and how
much of it you have to do yourself vs. GitHub doing for you.

## 1. Making it public

Repo → Settings → General → Danger Zone → Change visibility → Public.

Before you flip it:

- `git log --all -p | grep -iE "secret|password|api[_-]?key"` (or just skim
  `git log --stat` for anything that shouldn't be there) — once public, history is
  public too. A force-push doesn't undo exposure; assume anything ever committed is
  burned if it's a real credential, and rotate it instead of trying to scrub it.
- Check `.env` / `.env.example` aren't tracked with real values (`git ls-files | grep env`).

## 2. Branch protection (do this once, immediately after going public)

Settings → Branches → Add rule → `main`:

- **Require a pull request before merging** — stops anyone (including you, from a
  stray `git push`) from landing straight on `main`.
- **Require status checks to pass** — tick the three CI jobs (`backend`, `frontend`,
  `containers`) once they've run at least once on a PR, so GitHub has seen them.
- **Require approval before running workflows for first-time contributors** — this
  one is Settings → Actions → General → "Fork pull request workflows from outside
  collaborators" → **Require approval for first-time contributors**. This is the
  single most important setting for you specifically: without it, anyone can open a
  PR and your CI will run their arbitrary code with access to your repo's secrets and
  compute. With it, you click "Approve and run" the first time a given person
  contributes; after that they're trusted automatically. You have no secrets in CI
  today (the `CV_PAL_SECRET_KEY` in `ci.yml` is a hardcoded placeholder, not a real
  one), but leave this on anyway — it's the default and it's free insurance.

Don't bother with required reviewers or CODEOWNERS yet — that's for when you have
other maintainers. Solo, it just means you approving your own PRs, which is friction
with no payoff.

## 3. What an external PR looks like, end to end

1. Someone forks the repo, pushes a branch to their fork, opens a PR against your
   `main`. You get a notification (email + GitHub notifications tab).
2. If they're a first-time contributor, CI shows "waiting for approval to run" — go to
   the Actions tab or the PR's checks section and approve it. Read the diff first;
   approving CI runs their code.
3. Review the diff on the PR's **Files changed** tab. Leave inline comments by
   clicking the `+` next to a line. `CONTRIBUTING.md` already states your bar (typed,
   tested, thin routers, etc.) — you can just point at it: "see CONTRIBUTING.md re:
   service layer" is a complete review comment.
4. Once CI is green and you're happy: **Squash and merge** (top pick in the merge
   dropdown) is the easiest default — collapses their commits into one on `main`, so a
   messy WIP history on their branch doesn't pollute yours. You write the final commit
   message at merge time.
5. Delete the branch (GitHub offers a button right after merge).

You are never obligated to merge anything. "Thanks, but this doesn't fit the project's
scope (see docs/PLANNING.md)" and closing the PR is a normal, complete response.

## 4. Issues

Someone will eventually file a bug report or a feature request as an Issue, not a PR.
You don't need issue templates for a solo project — they add process for a population
of one. If it gets noisy later, add `.github/ISSUE_TEMPLATE/` then, not now.

Useful default labels (Issues tab → Labels, GitHub seeds a few already):
`bug`, `enhancement`, `question`, `wontfix` — wontfix + a closing comment is a fine way
to close something out of scope without being rude about it.

## 5. Things GitHub does for you that you don't need to build

- **Dependabot alerts** (Settings → Code security → enable) — flags vulnerable
  dependencies automatically, no config needed beyond the toggle.
- **Private vulnerability reporting** (same page) — matches what `SECURITY.md`
  already promises ("open a private security advisory"); enabling it is what makes
  that link in `SECURITY.md` actually work.
- **CI status on PRs** — already wired, shows up automatically as checks on every PR
  once branch protection requires it.

## 6. The one habit that matters more than any setting

Never merge a PR whose CI you haven't personally watched go green, and never approve
a CI run for a contributor without reading their diff first. Everything else here is
optional polish; that one is the actual security boundary.
