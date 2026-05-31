# Copilot workflow approval — reduce "1 workflow awaiting approval"

When Copilot opens a pull request, GitHub may require a maintainer to **approve workflow runs** before Actions execute. That blocks CI and makes the squad look stuck.

## What the squad does automatically

| Mechanism | When |
| --------- | ---- |
| [squad-copilot-pr-guard.yml](../.github/workflows/squad-copilot-pr-guard.yml) | Closes mistaken **planning PRs** on `ai-alpha-squad` (Business Owner / Architect deliver on issues) |
| `scripts/squad-approve-copilot-workflows.sh` | Called from the PR guard — attempts to **approve pending workflow runs** on the PR head SHA |
| Issue-first agents | `business-owner` and `architect` custom agents use **read/search tools only** (no branch/PR on the queue repo) |

## One-time repo settings (Director)

1. **Settings → Actions → General**
   - Under *Fork pull request workflows*, allow workflows from collaborators where appropriate.
   - If you use *Require approval for all outside collaborators*, ensure `SQUAD_ORCHESTRATOR_TOKEN` (or the Director account) can approve runs — or disable that rule for trusted Copilot sessions.

2. **Merge workflow files to `main` before relying on Copilot**
   - New workflow files introduced only inside a Copilot PR always need first-time approval.
   - Keep orchestration workflows on `main` (this repo already does).

3. **Target product repos**
   - Copy [.agents/templates/target-repo-copilot-ci-bridge.yml](../.agents/templates/target-repo-copilot-ci-bridge.yml) so `copilot/**` pushes run CI without waiting on PR approval.

## Token permissions

`SQUAD_ORCHESTRATOR_TOKEN` must include **`actions:write`** (or classic `repo` scope) so `squad-approve-copilot-workflows.sh` can approve pending runs.

## If planning agents still open draft PRs

That is expected Copilot behavior when `edit` is enabled. The squad:

1. Closes the PR via PR guard
2. Nudges the agent on the **issue** thread
3. Recommends **Cursor** for Business Owner / Architect on the queue repo — see [.agents/copilot-issue-first-delivery.md](../.agents/copilot-issue-first-delivery.md)

## Related

- [squad-orchestrator-automation.md](squad-orchestrator-automation.md)
- [PR #30](https://github.com/eduardocerqueira/ai-alpha-squad/pull/30) — example closed by squad PR guard (issue-first)
