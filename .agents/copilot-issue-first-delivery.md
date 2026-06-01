# Copilot issue-first delivery (planning agents)

Business Owner and Architect on **ai-alpha-squad** deliver on the **GitHub issue**, not via pull request.

## Copilot coding agent limitation

[GitHub Copilot coding agent](https://docs.github.com/en/copilot/concepts/agents/coding-agent/about-coding-agent) works through **branches and pull requests**. It often **does not post issue comments** even when instructed. For Business Owner / Architect on this queue repo:

- **Preferred:** Cursor (local/cloud) agent posts `# Business Analysis` / `# Technical Specification` via `gh issue comment`
- **Fallback:** Director or Cursor posts using `./scripts/squad-post-issue-deliverable.sh`
- **Automated recovery:** Orchestrator and PR guard copy substantive deliverables from the **PR body or branch `.md` files** onto the issue (no Director `gh` commands). See `squad-reconcile-planning-deliverables.py`.
- **Not sufficient:** Copilot PR on `ai-alpha-squad` with only a summary stub (no full `# Business Analysis` section)

Developer, QA, Security, DevOps, and Tech Writer on **target product repos** remain Copilot-first (PR-based).

## Rule

| Order | Action |
| ----- | ------ |
| 1 | Post the full artifact as an **issue comment** (template headings required). |
| 2 | Apply lifecycle **labels** (and create **sub-issues** for Architect). |
| 3 | Comment on the issue: `Squad deliverable complete on this issue.` |
| 4 | **Do not open a PR** on ai-alpha-squad for planning-only work. |

If you already opened a draft PR by mistake: post the artifact on the issue, complete labels/sub-issues, then **close the PR** with a comment that the issue is the source of truth.

## Required issue comment markers

| Agent | Phase labels | Comment must include |
| ----- | ------------ | -------------------- |
| Business Owner | → `awaiting-approval` | `# Business Analysis` |
| Architect | `director-approved` → `designed` | `# Technical Specification` |

## Architect checklist (before `designed`)

- [ ] Tech spec comment on parent issue (`FR-*` → `BR-*`)
- [ ] Sub-issues created for Developer, QA, Security, DevOps, Tech Writer (real GitHub issues, not only markdown drafts)
- [ ] Label `designed` added; `director-approved` removed
- [ ] No open Copilot PR on ai-alpha-squad for this handoff

## Business Owner checklist (before `awaiting-approval`)

- [ ] Full BA comment on issue (`BR-*`, user stories, acceptance criteria)
- [ ] Label `awaiting-approval` added; `new` removed
- [ ] No open Copilot PR on ai-alpha-squad for this handoff

## Enforcement

[`.github/workflows/squad-copilot-pr-guard.yml`](../.github/workflows/squad-copilot-pr-guard.yml) closes Copilot planning PRs on this repo when the issue deliverable is missing or redundant. It also closes **product/extension PRs** on `ai-alpha-squad` (e.g. `package.json`, `src/extension.ts`, WIP VS Code extension titles) — implementation belongs on the **target product repo**, not the work queue.

For planning PRs, the guard **polls the issue for up to ~1 minute** when the PR body also lacks the marker, **approves pending workflow runs** when possible, then **nudges** the agent on the issue thread if the marker is still missing. Product/extension PRs close **immediately** (no wait).

A **scheduled scan every 5 minutes** (runs on `main`) closes matching PRs, promotes deliverables, and reconciles open `new` / `director-approved` issues even if you never approve workflows on the Copilot branch. The `pull_request` trigger is optional for faster cleanup when workflows are already approved.

**Orchestrator reconcile job:** After dispatching Business Owner or Architect, [`squad-orchestrator.yml`](../.github/workflows/squad-orchestrator.yml) runs `reconcile-planning` for up to **35 minutes** (poll every 3 minutes): promote from PR → sync labels → project board.

Custom agents `business-owner` and `architect` use **read/search tools only** (no `edit`) to reduce spurious draft PRs on this repo.

**PR guard recovery:** Closing a planning or product PR does **not** force-nudge Copilot. The guard prefers **open** linked issues (e.g. #57 over closed #15), skips closed issues, never re-dispatches on product/extension closes, and only re-assigns when Copilot is **not** already on the issue. **Squad phase watch** runs `squad-recover-architect.sh` for `director-approved` jobs missing Copilot.

**PR → issue promotion:** If the PR **body or changed markdown on the branch** (e.g. `business-analysis.md`, `ba.md`) contains a full `# Business Analysis` or `# Technical Specification` (not a stub with `...`), the guard **copies it onto the issue**, runs `squad-sync-planning-labels.sh`, updates the project board, and unassigns Copilot after BA (Director gate next).

**Project board:** While `new` or `director-approved` but the required heading is **missing on the issue**, Active agent shows **blocked — post on issue** (not “business-owner still working”).

[`.github/workflows/squad-phase-watch.yml`](../.github/workflows/squad-phase-watch.yml) runs `squad-nudge-stuck.sh` on a schedule and when issue comments arrive.
