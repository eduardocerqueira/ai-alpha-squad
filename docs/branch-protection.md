# Branch protection — `main`

Protects [ai-alpha-squad](https://github.com/eduardocerqueira/ai-alpha-squad) `main` from direct pushes while keeping squad automation working.

## Why this is squad-safe

| Component | Touches `main`? | Notes |
| --------- | --------------- | ----- |
| [squad-orchestrator.yml](../.github/workflows/squad-orchestrator.yml) | No | Issues + Copilot dispatch only |
| [director-gate.yml](../.github/workflows/director-gate.yml) | No | Issue labels and comments |
| [squad-phase-watch.yml](../.github/workflows/squad-phase-watch.yml) | No | Phase advancement via issues |
| [squad-copilot-pr-guard.yml](../.github/workflows/squad-copilot-pr-guard.yml) | No | Closes mistaken Copilot PRs |
| Copilot planning agents (BO, Architect) | No | Deliver on **issues**, not PRs — [copilot-issue-first-delivery.md](../.agents/copilot-issue-first-delivery.md) |
| Developer / Release Manager | Target repos | Code and releases ship from **product repos**, not the work-queue repo |
| Landing deploy | No | `./scripts/deploy-landing.sh` → Cloudflare Workers |

Branch protection only blocks **git pushes and merges to `main`**. It does not restrict issue labels, comments, Copilot assignment, WhatsApp notify, or cross-repo orchestration.

## What is enforced

Default ruleset (`Protect main (AI Alpha Squad)`):

- Pull request required before merge (no direct push to `main`)
- Force push and branch deletion blocked
- Optional: `ci-test` status check (after [ci.yml](../.github/workflows/ci.yml) is on `main`)
- Optional: one approving review (`--require-review`)

Repository admins (Director) can bypass rulesets when needed for emergencies.

## Setup

```bash
# Basic protection (solo Director — no review count required)
./scripts/setup-branch-protection.sh

# After CI workflow is merged to main
./scripts/setup-branch-protection.sh --require-ci

# If you add collaborators and want review before merge
./scripts/setup-branch-protection.sh --require-ci --require-review
```

Verify in GitHub: **Settings → Rules → Rulesets**.

## Merging changes to this repo

1. Open a PR targeting `main` (Copilot, Cursor, or local branch).
2. Wait for **ci-test** if enabled.
3. Director merges the PR (squash or merge commit — both allowed).

Planning-only Copilot sessions should **not** open PRs here; if they do, [squad-copilot-pr-guard](../.github/workflows/squad-copilot-pr-guard.yml) closes them when the issue deliverable is missing.

## Target product repos

Apply similar protection on **target repos** (`seeker`, `vscode-squad-director`, etc.) separately. Use [install-target-repo-orchestrator-hook.sh](../scripts/install-target-repo-orchestrator-hook.sh) so merge events still notify the queue repo.

## Related

- [squad-orchestrator-automation.md](squad-orchestrator-automation.md)
- [infrastructure-prerequisites.md](../.agents/infrastructure-prerequisites.md)
