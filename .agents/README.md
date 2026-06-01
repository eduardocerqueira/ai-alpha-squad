# AI Alpha Squad — Agent Documentation

All squad documentation lives in this directory. The former `doc/` folder has been removed; use the paths below.

## Start here

| Document | Description |
| -------- | ----------- |
| [project-specification.md](project-specification.md) | System overview, agents, workflow, labels |
| [squad-orchestrator.md](squad-orchestrator.md) | Collaboration rules (read before any task) |
| [issue-lifecycle.md](issue-lifecycle.md) | GitHub issue states and transitions |
| [definition-of-done.md](definition-of-done.md) | Quality gates and mandatory artifacts |
| [templates/README.md](templates/README.md) | Fill-in templates by phase |
| [skills/README.md](skills/README.md) | Installed agent skills (VS Code, iOS, Cloudflare, CI, …) |
| [whatsapp-director-channel.md](whatsapp-director-channel.md) | Director WhatsApp approvals (Business Owner, Release Manager) |
| [infrastructure-prerequisites.md](infrastructure-prerequisites.md) | Credentials, Cloudflare, GitHub, job-specific secrets (before first job) |
| [agent-runtime-strategy.md](agent-runtime-strategy.md) | Cloud (GitHub Copilot agent) vs local Cursor |

**Research:** [GitAgent Protocol (GAP) vs AI Alpha Squad](../docs/gap-comparison.md) — comparison and optional adoption path.

## Agent definitions

| Label | Agent file |
| ----- | ---------- |
| `business-owner` | [agent-business-owner.md](agent-business-owner.md) |
| `architect` | [agent-architect.md](agent-architect.md) |
| `developer` | [agent-developer.md](agent-developer.md) |
| `qa` | [agent-qa.md](agent-qa.md) |
| `security` | [agent-security.md](agent-security.md) |
| `devops` | [agent-devops.md](agent-devops.md) |
| `tech-writer` | [agent-tech-writer.md](agent-tech-writer.md) |
| `release-manager` | [agent-release-manager.md](agent-release-manager.md) |

Director (human) is described in [project-specification.md](project-specification.md#4-agent-structure).
