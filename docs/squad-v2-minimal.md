# Squad v2 — minimal autonomous pipeline

Canonical spec from [TODO.md](../TODO.md) (lines 40–54). Restore point before this work: tag [`pre-simplify-2026-06-01`](https://github.com/eduardocerqueira/ai-alpha-squad/releases/tag/pre-simplify-2026-06-01).

## Principles

| Rule | Detail |
|------|--------|
| Source of truth | One **parent** GitHub issue per job (Director opens it) |
| Agents | **Business Owner** → **Developer** only |
| Deliverables | **Comments on the same issue** — no sub-issues |
| AI | **Hugging Face** inference only (no Copilot assign API) |
| Runner | **GitHub Actions** (`SQUAD_ORCHESTRATOR_TOKEN`) |
| Director gates | `awaiting-approval`, `release-candidate` only |
| Concurrency | **Sequential** — one agent run at a time per issue |
| Labels | Lifecycle labels only — **no priority** (`medium`, etc.) |
| Reliability | Phase watch + nudges + explicit failure comments |

## Lifecycle (labels)

```text
new
  → Business Owner (HF) posts # Business Analysis
  → awaiting-approval

awaiting-approval
  → Director replies APPROVE on issue
  → director-approved

director-approved
  → Developer (HF planning comment + Actions for target-repo PR when needed)
  → release-candidate (when dev deliverable + PR recorded on issue)

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
| `scripts/squad-v2-dispatch.sh` | Single entry: next agent for issue |
| `scripts/squad-v2-tick.sh` | Scan open jobs; dispatch or nudge |
| `src/ai_alpha_squad/squad_v2.py` | Phase logic, deliverables, in-progress guard |

Enable v2 on the repo:

```bash
gh variable set SQUAD_V2 --repo eduardocerqueira/ai-alpha-squad --body "1"
```

While `SQUAD_V2=1`, prefer v2 workflows; legacy orchestrator steps should no-op (guard added in follow-up PRs).

## Director

```bash
./scripts/squad-director-now.sh
```

Unchanged intent: **Your move** = gates; **Attention** = open jobs in active phases.

## Testing a job

1. Director opens issue with `new` + target repo in body.
2. BO runs → `# Business Analysis` → `awaiting-approval`.
3. Director `APPROVE` → `director-approved`.
4. Developer runs → **one PR** on target repo (branch `squad/developer-issue-<n>`) + `# Developer Deliverable` on issue → `release-candidate`.
5. Director release approval → `released`.

## Implementation checklist

- [x] Spec (this doc) + `squad_v2.py`
- [x] `squad-v2-dispatch.sh`, `squad-v2-tick.sh`
- [x] Workflows `squad-v2-orchestrator.yml`, `squad-v2-phase-watch.yml`
- [ ] Gate legacy `squad-orchestrator.yml` when `SQUAD_V2=1`
- [ ] Remove unused Copilot workflows after one green E2E
- [ ] Update `.agents/issue-lifecycle.md` to v2 as default
- [ ] New test job issue after merge
