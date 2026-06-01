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

## Optional web snapshot

```bash
git pull origin main
./scripts/squad-director-dashboard.py --serve
```

With **`SQUAD_V2=1`**, the Director dashboard workflow is skipped — use the CLI above. Legacy mode refreshes `jobs.json` via Actions (artifact + branch `director-jobs-json`; not `main` because of branch protection).

## Autonomous target

Director only acts on approval labels. Everything else: `squad-phase-watch.yml` + nudges. See [Job 1 retrospective](retrospectives/job-1-2026-06-01.md).
