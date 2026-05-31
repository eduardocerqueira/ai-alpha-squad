# Job 1 — VS Code extension: Squad Director

Director job pack for the first end-to-end AI Alpha Squad delivery.

| Field | Value |
| ----- | ----- |
| Queue repo | `eduardocerqueira/ai-alpha-squad` |
| Target repo | `eduardocerqueira/vscode-squad-director` |
| Extension id | `eduardocerqueira.squad-director` |
| Publisher | `eduardocerqueira` |
| Supersedes | Issue #15 (Squad Status Bar — closed) |

## Summary

Ship a VS Code extension that connects to the Director's GitHub account and surfaces the AI Alpha Squad **work queue**, **lifecycle phases**, and **approval gates** without leaving the editor.

## Business context

**Current situation:** The Director manages squad jobs via GitHub Issues, WhatsApp (when Meta credentials work), and CLI scripts. There is no unified in-IDE view of what needs approval or what phase each job is in.

**Desired outcome:** A daily-use Director console published to VS Code Marketplace and Open VSX, proving the squad can deliver production-ready software through the full issue lifecycle.

**Users:** Director (primary); squad agents benefit indirectly via faster approvals.

## v1 scope (frozen)

### UI

| Surface | Behavior |
| ------- | -------- |
| Activity Bar view **Squad** | Tree of issues from queue repo, grouped by lifecycle |
| Status bar | Compact summary, e.g. `Squad: 1 approve · 2 active` |
| Issue row | `#N` title, labels, age, assignee |

**Tree groups:**

1. **Needs you** — `awaiting-approval`, `release-candidate`
2. **Intake / analysis** — `new`, `business-owner`
3. **Build** — `director-approved`, `designed`, `implemented`
4. **Validation** — `validation`
5. **Done / blocked** — `released`, `blocked`

### Commands / actions

- Sign in with GitHub (`vscode.authentication` preferred)
- Refresh queue
- Open issue in browser
- **Approve BA** — authorized Director only: post `APPROVE` comment or add `director-approved` (same semantics as [director-gate.md](../../docs/director-gate.md))
- Setting: `squadDirector.queueRepo` (default `eduardocerqueira/ai-alpha-squad`)

### Auth & security

- Use GitHub auth session or fine-grained PAT via VS Code `SecretStorage`
- Scopes: `read:user`, `repo` on queue repo (read issues; write for approve actions)
- **No telemetry**, no third-party APIs, no secrets in repo

## Out of scope (v1)

- WebView dashboard / charts
- Creating new jobs from the extension
- Target-repo PR/CI monitoring
- WhatsApp send/receive in VS Code
- Triggering GitHub Actions / orchestrator from the extension

## Success criteria

- [ ] Extension installs from VS Code Marketplace and Open VSX
- [ ] Director signs in with GitHub from VS Code
- [ ] Sidebar lists queue issues by lifecycle group
- [ ] Status bar shows pending approval count
- [ ] One-click open issue + Approve BA (Director-only)
- [ ] CI: compile, lint, unit tests, extension host smoke test, package `.vsix`
- [ ] All squad artifacts on parent issue (BA, tech spec, QA/security reports, release plan)
- [ ] Director approval before release (`release-candidate` → `released`)

## References

- [Squad orchestrator](../../.agents/squad-orchestrator.md)
- [Issue lifecycle](../../.agents/issue-lifecycle.md)
- [Director gate](../../docs/director-gate.md)
- [Copilot issue-first delivery](../../.agents/copilot-issue-first-delivery.md)
- [VS Code extension expert skill](../../.agents/skills/vscode-extension-expert/SKILL.md)

## Director notes

- Business Owner: post full `# Business Analysis` **on the parent issue** and set `awaiting-approval` — no planning PR on `ai-alpha-squad`
- All implementation PRs go to **`vscode-squad-director`**
- v1 scope is frozen; defer WebView, target-repo PR column, and job creation to a follow-up issue
