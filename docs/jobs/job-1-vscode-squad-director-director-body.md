## Summary

Ship **Squad Director** — a VS Code extension that connects to my GitHub account and gives visibility into the AI Alpha Squad work queue, lifecycle phases, and approval gates from inside the editor.

## Business Context

**Current situation:** I manage squad jobs via GitHub Issues, WhatsApp (when available), and CLI. There is no in-IDE view of pending approvals or active job phases.

**Desired outcome:** A Director console extension published to VS Code Marketplace and Open VSX — the first real end-to-end squad product run.

**Users:** Director (primary).

## Constraints

| Type | Detail |
| ---- | ------ |
| Budget / cost | GitHub Actions minutes only; Marketplace + Open VSX accounts |
| Timeline | First squad job — learn the pipeline; v1 scope frozen |
| Compliance / legal | No telemetry; GitHub API only; tokens in VS Code SecretStorage / auth session |
| Technical | TypeScript extension; `@vscode/test-electron`; code in target repo |

## Success Criteria

- Extension installs from VS Code Marketplace and Open VSX
- GitHub sign-in; sidebar shows `ai-alpha-squad` issues grouped by lifecycle
- Status bar shows pending approval count
- Director can open issue and approve BA from the extension
- CI passes: compile, lint, tests, smoke test, `.vsix`
- Full squad artifacts on this issue; Director release approval before ship

## References

| Resource | Link |
| -------- | ---- |
| Job pack | https://github.com/eduardocerqueira/ai-alpha-squad/blob/main/docs/jobs/job-1-vscode-squad-director.md |
| Squad orchestrator | https://github.com/eduardocerqueira/ai-alpha-squad/blob/main/.agents/squad-orchestrator.md |
| Target repo | https://github.com/eduardocerqueira/vscode-squad-director |

## Out of Scope (initial)

- WebView dashboard
- Creating jobs from VS Code
- Target-repo PR/CI status
- WhatsApp in extension
- Orchestrator / Actions triggers

## Director Notes

- **Target repo:** `vscode-squad-director` for all implementation PRs
- **Extension id:** `eduardocerqueira.squad-director`
- **Publisher:** `eduardocerqueira`
- Supersedes closed issue #15 (Squad Status Bar)
- Business Owner: post `# Business Analysis` on this issue and set `awaiting-approval`
