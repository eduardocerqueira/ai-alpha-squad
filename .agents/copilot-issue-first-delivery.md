# Copilot issue-first delivery (planning agents)

Business Owner and Architect on **ai-alpha-squad** deliver on the **GitHub issue**, not via pull request.

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

[`.github/workflows/squad-copilot-pr-guard.yml`](../.github/workflows/squad-copilot-pr-guard.yml) closes Copilot planning PRs on this repo when the issue deliverable is missing or redundant, then **nudges** the agent to retry on the issue thread.

[`.github/workflows/squad-phase-watch.yml`](../.github/workflows/squad-phase-watch.yml) runs `squad-nudge-stuck.sh` on a schedule and when issue comments arrive.
