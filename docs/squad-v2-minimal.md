# Squad v2 — minimal autonomous pipeline

Canonical spec from [TODO.md](../TODO.md) (lines 40–54). Restore point before this work: tag [`pre-simplify-2026-06-01`](https://github.com/eduardocerqueira/ai-alpha-squad/releases/tag/pre-simplify-2026-06-01).

## Principles

| Rule | Detail |
|------|--------|
| Source of truth | One **parent** GitHub issue per job (Director opens it) |
| Agents | **Business Owner** → **Developer** → **QA** (acceptance gate) |
| Deliverables | **Comments on the same issue** — no sub-issues |
| AI | **Hugging Face** inference only (no Copilot assign API) |
| Runner | **GitHub Actions** (`SQUAD_ORCHESTRATOR_TOKEN`) |
| Director gates | `awaiting-approval`, `release-candidate` only |
| Concurrency | **Sequential** — one agent run at a time per issue |
| Labels | Lifecycle labels only — **no priority** (`medium`, etc.) |
| Reliability | Phase watch + stale-run recovery + explicit failure comments + reset marker |

## Lifecycle (labels)

```text
new
  → Business Owner (HF) posts # Business Analysis
  → awaiting-approval

awaiting-approval
  → Director replies APPROVE on issue
  → director-approved

director-approved
  → Developer (Actions: target-repo branch + PR) posts # Developer Deliverable
  → QA (HF) reviews the PR vs the issue's success criteria, posts # QA Report:
       squad-v2-qa:pass → release-candidate
       squad-v2-qa:fail → Developer reworks (up to MAX_QA_ROUNDS=3), then re-QA;
                          after the cap the issue is blocked for the Director
  → release-candidate (when QA passes)

release-candidate
  → Director APPROVE / REJECT
  → released

blocked — optional manual pause
```

Removed from v2: `designed`, `implemented`, `validation`, architect, QA/Security/DevOps/Tech Writer sub-issues, parallel validation matrix, Copilot routing.

## Orchestration

| Component | Role |
|-----------|------|
| `squad-v2-orchestrator.yml` | Dispatch on `new`, `director-approved` |
| `squad-v2-phase-watch.yml` | Cron + manual tick; nudge; label sync |
| `scripts/squad-v2-dispatch.sh` | Next agent for issue; **chains dev→QA→rework→gate inline** (orchestrator) |
| `scripts/squad-v2-tick.sh` | Scan open jobs; dispatch or nudge |
| `src/ai_alpha_squad/squad_v2.py` | Phase logic, deliverables, in-progress guard |

Enable v2 on the repo:

```bash
gh variable set SQUAD_V2 --repo eduardocerqueira/ai-alpha-squad --body "1"
```

While `SQUAD_V2=1`, prefer v2 workflows; legacy orchestrator steps should no-op (guard added in follow-up PRs).

## Reliability & recovery

The pipeline is sequential and self-healing within these bounds:

- **Retry cap** — an agent gets `MAX_RUN_ATTEMPTS` (3) failures before the issue is
  labelled `blocked`. Failures are counted **since the last reset marker**, not for
  the issue's whole lifetime, so historical failures from since-fixed bugs don't
  permanently wedge a job.
- **Stale-run recovery** — an `in_progress` marker with no terminal marker, older
  than `SQUAD_V2_STALE_MINUTES` (120m; must stay above the 90m orchestrator
  timeout), is auto-recovered by the phase-watch tick (posts a failure marker so
  the issue stops looking "active"). This handles runs cancelled or timed out
  before they could report.
- **No mid-run cancellation** — the orchestrator uses `cancel-in-progress: false`
  so an unrelated `labeled` event can't kill a 90m inline developer build and
  orphan its branch/PR.

**Manual recovery** — to retry a `blocked` issue (or one that hit the retry cap),
re-run the orchestrator. A `workflow_dispatch` run clears the failure count
(posts `squad-v2-run:reset:<agent>`) and removes `blocked` automatically:

```bash
gh workflow run "Squad v2 orchestrator" --repo eduardocerqueira/ai-alpha-squad \
  -f issue_number=<n> -f lifecycle_label=director-approved
```

To reset by hand without re-running, comment `squad-v2-run:reset:developer`
(or `:all`) on the issue and remove the `blocked` label.

## Director

```bash
./scripts/squad-director-now.sh
```

Unchanged intent: **Your move** = gates; **Attention** = open jobs in active phases.

## Testing a job

1. Director opens issue with `new` + target repo in body.
2. BO runs → `# Business Analysis` → `awaiting-approval`.
3. Director `APPROVE` → `director-approved`.
4. Developer runs → **one PR** on target repo (branch `squad/developer-issue-<n>`) + `# Developer Deliverable` on issue.
5. QA runs → reviews the PR against the issue success criteria → `# QA Report` with `squad-v2-qa:pass`/`:fail`. On fail, Developer reworks until QA passes (cap 3) → `release-candidate`.
6. Director release approval → `released`.

## Implementation checklist

- [x] Spec (this doc) + `squad_v2.py`
- [x] `squad-v2-dispatch.sh`, `squad-v2-tick.sh`
- [x] Workflows `squad-v2-orchestrator.yml`, `squad-v2-phase-watch.yml`
- [x] Gate legacy `squad-orchestrator.yml` / `squad-phase-watch.yml` when `SQUAD_V2=1` (job-level `if: vars.SQUAD_V2 != '1'`)
- [x] Retry-count reset marker + stale-run recovery + no mid-run cancellation
- [ ] Remove unused Copilot workflows after one green E2E
- [ ] Update `.agents/issue-lifecycle.md` to v2 as default
- [ ] New test job issue after merge
