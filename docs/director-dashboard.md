# Director dashboard

**Single screen** for all squad jobs — not GitHub Project columns, not issue comment tables.

| Column | Meaning |
| ------ | ------- |
| **Needs your action** | `awaiting-approval`, `release-candidate`, or other Director-only gates |
| **In progress** | Squad is working; you do not need to act now (e.g. Job 1 at `designed` with an open target PR) |
| **Stuck** | Missing BA/spec on issue, `blocked` label, or agent blocked |
| **Completed** | `released` or closed |

## Use it (recommended)

Local live dashboard (always fresh, uses your `gh` auth):

```bash
cd ai-alpha-squad
./scripts/squad-director-dashboard.py --serve
```

Open **http://127.0.0.1:8788/** — refresh every 60s or click **Refresh**.

## Published site

After deploy, open:

**https://aialphasquad.com/director/**

Data file: `/director/jobs.json`, updated by [director-dashboard.yml](../.github/workflows/director-dashboard.yml) every 15 minutes and when queue issues change.

## Regenerate JSON manually

```bash
./scripts/squad-director-dashboard.py --write
```

## Unblock a stuck job

When the dashboard shows **Stuck** (e.g. PR merged but validation idle):

```bash
./scripts/squad-director-dashboard.py --tick 64
# or
./scripts/squad-phase-tick.sh eduardocerqueira/ai-alpha-squad 64
```

If validation was dispatched but no report appeared:

```bash
SQUAD_FORCE_NUDGE=1 ./scripts/squad-dispatch-validation.sh eduardocerqueira/ai-alpha-squad 64 qa
```

Each job card includes an **agent roster** (business-owner → release-manager) with status: `done`, `active`, `waiting`, or `stuck`.

## What we stopped doing

- Long **Squad Director status** comments on issues (disabled by default; set `SQUAD_DIRECTOR_STATUS_COMMENTS=1` only if you want them back).
- Relying on GitHub Project **Status = Backlog** — use this dashboard or configure Project **Column field = Lifecycle** (see [director-project-board.md](director-project-board.md)).

## VS Code extension

Job 1 (`vscode-squad-director`) will mirror these four buckets in the sidebar; until it ships, use this web dashboard.
