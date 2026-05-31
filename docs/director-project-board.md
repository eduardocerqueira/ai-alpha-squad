# Director project board

Track **who is working on what**, what is **stuck**, and what **needs your approval** in [GitHub Project #6](https://github.com/users/eduardocerqueira/projects/6).

Issue labels alone are hard to read in a pipeline: an issue can carry both `business-owner` and `awaiting-approval`. This setup adds three **project fields** (synced from labels) and recommended **views** (tabs).

## Quick setup (5 minutes)

```bash
unset GITHUB_TOKEN
gh auth refresh -s read:project,project,repo,workflow
./scripts/setup-squad-project-github.sh
```

That updates `SQUAD_ORCHESTRATOR_TOKEN` (for CI sync), creates project fields, syncs open issues, and prints view instructions.

Manual only:

```bash
./scripts/setup-squad-project-board.sh setup
```

Requires `gh` authenticated with `read:project` and `project` scopes (not a bare `GITHUB_TOKEN` with repo-only scopes).

## Project fields (auto-synced)

| Field | Purpose | Example |
| ----- | ------- | ------- |
| **Lifecycle** | Current workflow phase | `awaiting-approval`, `designed`, `validation` |
| **Active agent** | Who owns work now | `Director`, `architect`, `developer`, `qa` |
| **Needs Director** | Your approval queue | `Yes` when BA or release needs sign-off |

Mapping rules (see `scripts/squad_project_sync.py`):

| Lifecycle | Active agent | Needs Director |
| --------- | ------------ | -------------- |
| `new` | business-owner | No |
| `awaiting-approval` | **Director** | **Yes** |
| `director-approved` | architect | No |
| `designed` | developer | No |
| `implemented` | developer (or sub-issue agent) | No |
| `validation` | release-manager | No |
| `release-candidate` | **Director** | **Yes** |
| `blocked` | Blocked | No |
| `released` | Done | No |

Sub-issues (QA, Security, etc.) show their agent label when in `implemented`.

## Recommended views (tabs)

Create these in the project UI after running setup.

### 1. Director inbox (Table)

Use this as your daily starting point.

- **Layout:** Table
- **Filter:** `is:issue is:open repo:eduardocerqueira/ai-alpha-squad label:awaiting-approval,release-candidate,blocked`
- **Sort:** Updated ↓
- **Columns:** Title, Assignees, Lifecycle, Active agent, Needs Director, Labels

### 2. Pipeline by agent (Board)

See work grouped by squad role.

- **Layout:** Board
- **Filter:** `is:issue is:open repo:eduardocerqueira/ai-alpha-squad`
- **Group by:** Active agent
- **Sort:** Updated ↓

Columns appear as: Director, business-owner, architect, developer, qa, security, devops, tech-writer, release-manager, Blocked, Done.

### 3. Pipeline by phase (Board)

Classic SDLC swimlanes.

- **Layout:** Board
- **Filter:** `is:issue is:open repo:eduardocerqueira/ai-alpha-squad`
- **Group by:** Lifecycle
- **Sort:** Updated ↓

### 4. Needs you (Board) — optional

Narrow view for approvals only.

- **Filter:** `is:issue is:open repo:eduardocerqueira/ai-alpha-squad label:awaiting-approval,release-candidate`
- **Group by:** Lifecycle

## Automation

| Trigger | Action |
| ------- | ------ |
| Issue opened / label changed | [squad-project-sync.yml](../.github/workflows/squad-project-sync.yml) updates project fields |
| Manual | `./scripts/setup-squad-project-board.sh sync-all` |
| Single issue | `./scripts/setup-squad-project-board.sh sync-issue 17` |

New issues are **added to the project** automatically on first sync.

## Prerequisites

1. Project #6 includes **ai-alpha-squad** as a data source (Project → ⚙ → Manage access / linked repos).
2. `gh` authenticated with `read:project` and `project` scopes.
3. For CI sync: PAT or `GITHUB_TOKEN` with project write on your user project (often requires `SQUAD_ORCHESTRATOR_TOKEN` with `project` scope).

## Related

- [Issue lifecycle](../.agents/issue-lifecycle.md)
- [Director gate](director-gate.md)
- [Squad orchestrator automation](squad-orchestrator-automation.md)
