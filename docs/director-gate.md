# Director approval gate

Only the **Director** may advance an issue from `awaiting-approval` to architecture. Agents, collaborators, and the public cannot set the trigger label directly.

## Trigger label

| Label | Who may set it | Effect |
| ----- | -------------- | ------ |
| `awaiting-approval` | Business Owner agent / workflow | Notifies Director (WhatsApp + issue) |
| `director-approved` | Director only (see paths below) | Starts **Architect** via squad orchestrator |
| `approved` | Legacy alias | Converted to `director-approved` if Director; otherwise **reverted** |

## Approval paths

| Path | How |
| ---- | --- |
| **WhatsApp** | Reply `APPROVE` from `WHATSAPP_DIRECTOR_PHONE` (Worker allowlist) |
| **GitHub comment** | Director comments `APPROVE` on the issue (login must match `SQUAD_DIRECTOR_LOGIN`) |
| **GitHub label** | Director adds `approved` or `director-approved` in the UI |
| **CLI** | `./scripts/director-approve.sh <issue_number>` (uses your `gh auth` user) |

Non-Director attempts to add `approved` / `director-approved` are removed and logged on the issue.

## Configuration

Repository **variables** (Settings → Secrets and variables → Actions → Variables):

| Variable | Example | Required |
| -------- | ------- | -------- |
| `SQUAD_DIRECTOR_LOGIN` | `eduardocerqueira` | Yes |
| `SQUAD_WHATSAPP_APPROVAL_LOGIN` | same as Director or machine user | No |
| `WHATSAPP_DIRECTOR_PHONE` | `+15551234567` | For WhatsApp notify/approve |

```bash
gh variable set SQUAD_DIRECTOR_LOGIN --repo eduardocerqueira/ai-alpha-squad --body "eduardocerqueira"
gh label create director-approved --repo eduardocerqueira/ai-alpha-squad --color C2E0C6 \
  --description "Director approved — ready for architecture" --force
```

WhatsApp Worker `GITHUB_TOKEN` PAT owner must match `SQUAD_DIRECTOR_LOGIN` or `SQUAD_WHATSAPP_APPROVAL_LOGIN`.

## Workflows

| Workflow | Role |
| -------- | ---- |
| [director-gate.yml](../.github/workflows/director-gate.yml) | Validates label/comment; grants or revokes `director-approved` |
| [squad-orchestrator.yml](../.github/workflows/squad-orchestrator.yml) | Dispatches Architect only on authorized `director-approved` |

## Agent rules

- **Business Owner:** may set `awaiting-approval` only — never `approved` or `director-approved`.
- **Architect:** starts when `director-approved` is present; sets `designed` when done.

## Related

- [whatsapp-director-channel.md](../.agents/whatsapp-director-channel.md)
- [issue-lifecycle.md](../.agents/issue-lifecycle.md)
- [squad-orchestrator-automation.md](squad-orchestrator-automation.md)
