# Director

## Reliable CLI (use this)

```bash
./scripts/squad-director-now.sh
```

1. **Your move** — `awaiting-approval` or `release-candidate` (you must reply on GitHub).  
2. **Attention** — open jobs in `validation`, `implemented`, etc. If listed here for hours with no comments, the pipeline is stuck (not an approval gate).

## Stop a job

```bash
./scripts/squad-close-job.sh eduardocerqueira/ai-alpha-squad <parent#> "reason"
```

## Web dashboard

A two-column React dashboard (served at `/director/` by the site Worker):

- **80% — timeline.** A timeline19-style vertical timeline of the selected job's
  lifecycle (`new → awaiting-approval → … → released`). Each step shows its owning
  agent and status (done / current / blocked / pending). When a job is **awaiting a
  Director decision**, that step renders as a highlighted "request for Director" node
  with the message and an **Open issue & respond** action link.
- **20% — squad.** Every agent assigned to the job with an SVG status indicator
  (idle / working / blocked / done) and a link to its sub-issue.
- **Job tabs** group jobs by status: **Open** (needs-you / stuck) · **In progress** ·
  **Done** (released/closed). Each tab shows a count; the Open tab flags when an
  approval is waiting. A job switcher under the tabs picks which job's timeline shows.
  Deep-link a tab with `?tab=done` (also `in_progress`, `open`).

### Where the data comes from (and how it refreshes)

The dashboard reads `/api/director/jobs`. The deployed Worker serves the
**live** copy CI publishes to the `director-jobs-json` branch (edge-cached ~60s),
falling back to the `jobs.json` bundled at deploy time. The page also
**auto-refreshes every 60s**, and **Refresh** reloads the latest status:

- **Deployed:** Refresh re-pulls the CI-maintained branch copy. The
  `Director dashboard` workflow regenerates it on issue events (labeled / closed /
  reopened) and every 15 min.
- **Local `--serve --live`:** Refresh rebuilds **live from GitHub** via `gh`
  (`?live=1&refresh=1`).

### Sign-in (magic link)

The dashboard is gated by a self-contained magic-link login (Cloudflare Email +
signed session cookie). The job-data API (`/api/director/jobs`) returns `401`
without a valid session; the static shell is public but shows only the login form
until you sign in.

- **Who can sign in:** the `DIRECTOR_ALLOWED_EMAILS` var (comma-separated) in
  [`site/wrangler.jsonc`](../site/wrangler.jsonc).
- **Secret:** tokens/cookies are signed by `AUTH_SECRET` — set it once before deploy:
  ```bash
  cd site && wrangler secret put AUTH_SECRET   # use: openssl rand -hex 32
  ```
- **Flow:** enter your email → click the emailed link (15-min expiry) → a 7-day
  HttpOnly session cookie is set → **Sign out** clears it.
- **Local `wrangler dev`:** copy `site/.dev.vars.example` → `site/.dev.vars` and set
  `AUTH_SECRET`.

> The Python `--serve` preview below has **no login** — it's the read-only local
> snapshot view. The `npm run dev` server stubs auth so you see the dashboard
> directly.

### Local preview

```bash
# Static snapshot (no GitHub calls, no login):
./scripts/squad-director-dashboard.py --serve

# Live: the Refresh button rebuilds from GitHub on demand:
./scripts/squad-director-dashboard.py --serve --live
```

### Develop / build the dashboard

Source lives in [`site/dashboard/`](../site/dashboard) (Vite + React + TypeScript +
Tailwind, shadcn-style components). It builds to `site/public/director/` so the
existing Cloudflare Worker serves it as static assets — no extra routing.

```bash
cd site/dashboard
npm install
npm run dev        # hot-reload dev server (fetches /director/jobs.json)
npm run build      # → site/public/director/ (preserves jobs.json)
```

`wrangler deploy` from `site/` builds the dashboard automatically (`predeploy` →
`build:dashboard`).

The `Director dashboard` workflow regenerates `jobs.json` and force-pushes it to
the `director-jobs-json` branch, which the Worker reads live. It runs on issue
events and every 15 min (`main` itself is branch-protected, so the data lives on
its own branch rather than being committed to `main`).

## Autonomous target

Director only acts on approval labels. Everything else: `squad-phase-watch.yml` + nudges. See [Job 1 retrospective](retrospectives/job-1-2026-06-01.md).
