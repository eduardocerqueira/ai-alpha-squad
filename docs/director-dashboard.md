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

A [shadcn/ui](https://ui.shadcn.com) sidebar dashboard (brand dark + green), served
at `/director/` by the site Worker. Live at [aialphasquad.com/director](https://aialphasquad.com/director/).

- **Sidebar.** Status nav with live counts — **Open** (needs you) · **In progress** ·
  **Blocked** · **Done** — plus the signed-in account and the site version (matching
  the marketing-site footer). The Open/Blocked counts glow when they want attention.
  Deep-link a status with `?tab=done` (also `in_progress`, `blocked`, `open`).
- **Job switcher.** Horizontally scrollable cards for the selected status; each shows
  the issue number, a status badge, and `needs human` / `blocked` flags.
- **Timeline.** The selected job's lifecycle (`new → awaiting-approval → … → released`)
  as a vertical timeline. Each step carries its owning agent, status
  (done / current / blocked / pending), **and the date/time it happened** (left gutter).
  A step **awaiting a Director decision** renders as a highlighted node with the message
  and an **Open issue & respond** action.
- **Squad panel.** Every agent on the job with a status indicator
  (idle / working / blocked / done) and a link to its issue.
- **Model history.** Per-agent timeline of the AI models each agent ran on, including
  developer **escalations** (fast model → stronger coder after QA pushback) — the story
  of how the work actually got done.
- **Actions.** **Stop execution** halts an in-progress job (cancels the in-flight
  Actions run and holds it in Blocked); **Retry** / **Re-open & re-run** resumes a
  stuck, blocked, or done job, optionally on a chosen model from the ladder. PR status
  (open / merged) links straight to the target repo.

### Where the data comes from (and how it refreshes)

The dashboard reads `/api/director/jobs`. The deployed Worker **computes the snapshot
live** (TypeScript port of the Python builder, in `site/src/director-data.ts`) from the
GitHub GraphQL API and caches it in KV; it falls back to the `director-jobs-json` branch
copy and then the bundled `jobs.json`. The page **auto-refreshes every 30s**, refetches
when the tab regains focus, and holds a **WebSocket** to the hub for instant push when CI
publishes new data. **Refresh** forces a recompute.

- **Deployed:** the `Director dashboard` workflow regenerates the snapshot on issue
  events (labeled / closed / reopened) and every 15 min, ingesting it to KV
  (`/api/director/ingest`) and force-pushing the `director-jobs-json` branch; GitHub
  issue webhooks also trigger a live recompute.
- **Local `--serve --live`:** Refresh rebuilds **live from GitHub** via `gh`
  (`?live=1&refresh=1`).

> Keep `site/src/director-data.ts` (live worker compute) and
> `src/ai_alpha_squad/director_dashboard.py` (CI snapshot + local `--serve`) in sync —
> both must emit the same fields (timeline `at`, agent `model_history`, …) or a feature
> will appear on one path but not the other.

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
Tailwind + [shadcn/ui](https://ui.shadcn.com)). It builds to `site/public/director/` so
the existing Cloudflare Worker serves it as static assets — no extra routing.

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
