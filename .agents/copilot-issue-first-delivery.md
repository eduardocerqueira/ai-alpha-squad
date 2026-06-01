# Copilot issue-first delivery (planning agents)

Business Owner and Architect on **ai-alpha-squad** deliver on the **GitHub issue**, not via pull request.

## Copilot coding agent limitation

[GitHub Copilot coding agent](https://docs.github.com/en/copilot/concepts/agents/coding-agent/about-coding-agent) works through **branches and pull requests**. It often **does not post issue comments** even when instructed. For Business Owner / Architect on this queue repo:

- **Preferred:** Cursor (local/cloud) agent posts `# Business Analysis` / `# Technical Specification` via `gh issue comment`
- **Fallback:** Director or Cursor posts using `./scripts/squad-post-issue-deliverable.sh`
- **Not sufficient:** Copilot PR on `ai-alpha-squad` with BA only in the PR body (Squad PR guard closes it)

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

[`.github/workflows/squad-copilot-pr-guard.yml`](../.github/workflows/squad-copilot-pr-guard.yml) closes Copilot planning PRs on this repo when the issue deliverable is missing or redundant. A **scheduled scan every 10 minutes** (runs on `main`) closes planning PRs even if you never approve workflows on the Copilot branch. The `pull_request` trigger is optional for faster cleanup when workflows are already approved.

Custom agents `business-owner` and `architect` use **read/search tools only** (no `edit`) to reduce spurious draft PRs on this repo.

[`.github/workflows/squad-phase-watch.yml`](../.github/workflows/squad-phase-watch.yml) runs `squad-nudge-stuck.sh` on a schedule and when issue comments arrive.
