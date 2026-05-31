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

See work in columns per squad role.

> **GitHub quirk:** On **Board** layout, vertical columns use **Column field**, not **Group**.  
> **Group** on a board creates horizontal *rows* (secondary). Our docs previously said "Group by" — use **Column field** below.

1. Open the **Pipeline by agent** tab (Board layout).
2. Click **View** (top-right menu on the project).
3. **Fields** → enable **Active agent**, **Lifecycle**, **Needs Director** (must be visible before they appear in column picker).
4. **Column field** → **Active agent** (replace default **Status**).
5. **Save** the view (GitHub shows an unsaved-changes banner until you save).

Optional: **Filter** → `is:issue is:open repo:eduardocerqueira/ai-alpha-squad`  
Optional: **Sort** → Updated ↓

Columns: Director, business-owner, architect, developer, qa, security, devops, tech-writer, release-manager, Blocked, Done, plus **No value** for items not synced yet.

**Table alternative:** Layout **Table** → **Group** → **Active agent** (true "group by" works on table views).

### 3. Pipeline by phase (Board)

Classic SDLC swimlanes.

- **Layout:** Board
- **Filter:** `is:issue is:open repo:eduardocerqueira/ai-alpha-squad`
- **Column field:** Lifecycle (not Group)
- **Sort:** Updated ↓

### 4. Needs you (Board) — optional

Narrow view for approvals only.

- **Filter:** `is:issue is:open repo:eduardocerqueira/ai-alpha-squad label:awaiting-approval,release-candidate`
- **Column field:** Lifecycle

## Troubleshooting

| Problem | Fix |
| ------- | --- |
| **Active agent** missing from Column field / Group menu | View menu → **Fields** → show **Active agent** first |
| Board still shows Status columns | View menu → **Column field** → **Active agent** (not Status) |
| Cards stuck in wrong column after sync | Drag card once in UI (known GitHub Projects API quirk) or re-save Column field |
| Most items in **No value** | Run `./scripts/setup-squad-project-board.sh sync-all` (only open queue issues get squad fields) |

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
