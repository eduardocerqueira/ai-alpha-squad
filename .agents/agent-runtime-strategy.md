# Agent Runtime Strategy — Local vs Cloud

The squad was designed around **GitHub Issues as source of truth**. Cloud delivery uses **GitHub Actions** workflows plus **Hugging Face** models — not GitHub Copilot coding agent (legacy optional). Local **Cursor** remains available for the Director.

## Short answer

| Goal | Recommendation |
| ---- | ---------------- |
| Default cloud runtime | **`SQUAD_AI_PROVIDER=huggingface`** + **`SQUAD_CODE_RUNTIME=actions`** — see [docs/agent-ai-providers.md](../docs/agent-ai-providers.md) |
| Stop using your Mac for coding work | **Yes** — **Squad Actions agent** clones the target repo, runs an HF tool loop, opens a PR |
| Planning (BA, architect, reports) | **HF inference** → issue comments; architect sub-issues via script |
| Copilot | **Legacy** — set `SQUAD_CODE_RUNTIME=copilot` only if you still use assign API |
| Director gates | Unchanged — WhatsApp/GitHub approval |

Implementation: [issue #85](https://github.com/eduardocerqueira/ai-alpha-squad/issues/85).

---

## What GitHub Copilot cloud agent is

[Copilot coding agent](https://docs.github.com/en/copilot/concepts/agents/coding-agent/about-coding-agent) runs in a **GitHub Actions–backed VM**, clones **one repo**, commits to a branch, and opens a **draft PR**. It is a strong fit for **Developer** work (and specialized custom agents for tests, planning, docs).

**Requirements:** Copilot Pro+, Business, or Enterprise; [enable the agent](https://docs.github.com/en/copilot/how-tos/use-copilot-agents/coding-agent/enable-coding-agent) per repository; consumes **Actions minutes** and **premium requests**.

**Custom agents:** Markdown profiles in `.github/agents/*.agent.md` — see [creating custom agents](https://docs.github.com/en/copilot/how-tos/use-copilot-agents/coding-agent/create-custom-agents). This repo includes squad-aligned profiles that **point at** `.agents/agent-*.md`.

**Limits for AI Alpha Squad:**

- One repo per session — implementation happens on the **product repo**, not only `ai-alpha-squad`
- Does not natively run your 8-agent phase machine — you assign **which custom agent** handles **which issue/sub-issue**
- WhatsApp, Apple signing, VSCE publish secrets — still need **Actions + secrets** or a **Worker** (DevOps)
- Business approval remains **Director** — WhatsApp/GitHub, not Copilot-only

---

## Recommended architecture (hybrid)

```text
┌─────────────────────────────────────────────────────────────┐
│  ai-alpha-squad (work queue)                                 │
│  GitHub Issues + labels + templates + .agents/ docs          │
│  Custom agents: business-owner, architect (planning/docs)    │
└───────────────────────────┬─────────────────────────────────┘
                            │ sub-issues link to target repo
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Target repo (extension / seeker / game / …)                 │
│  Copilot cloud agent: developer, qa, devops-oriented agents  │
│  GH Actions: CI, publish, deploy (DevOps agent deliverable)   │
└───────────────────────────┬─────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
  Cloudflare Worker    Cursor Cloud API     (optional) HF Jobs
  WhatsApp webhook     orchestration        training/inference
```

### Role → runtime mapping

| Squad agent | Primary runtime | How to trigger |
| ----------- | --------------- | -------------- |
| Business Owner | **Cursor** (local/cloud) **preferred**; Copilot `business-owner` only if it posts `# Business Analysis` on the issue via `gh issue comment` | Issue `new` → BA comment; `awaiting-approval` — **not** a planning PR on queue repo |
| Architect | Copilot `architect` (read/edit docs) **or** Cursor | Issue `director-approved` → tech spec + sub-issues on queue repo |
| Developer | **Squad Actions agent** on target repo | Sub-issue → `squad-actions-agent.yml` (HF + git + PR) |
| QA | Copilot `qa` on target repo | Sub-issue after PR exists |
| Security | Cursor / manual + tools | Review PR; security-report on issue |
| DevOps | Actions + Copilot `devops` stub | First job: pipelines; Worker for WhatsApp |
| Tech Writer | Copilot or Cursor | Docs/PR on target or queue repo |
| Release Manager | Issue + WhatsApp + Actions release | `release-candidate`; GH Release workflow |
| Director | Human | GitHub + WhatsApp |

---

## Alternatives to local Cursor

| Platform | Best for | Squad fit |
| -------- | -------- | ----------- |
| [GitHub Copilot cloud agent](https://github.com/features/copilot/agents) | Issue → branch → PR in GitHub | **Default for code** on product repos |
| [Cursor Cloud Agents](https://cursor.com/docs/sdk) (`@cursor/sdk`, `CURSOR_API_KEY`) | API-driven runs, same prompts as IDE | Orchestrator script: label change → `Agent.prompt` with `agent-*.md` |
| Cloudflare **Agents SDK** | Stateful webhooks, WhatsApp, queues | WhatsApp Director channel + future orchestrator DO |
| Hugging Face **Inference** (`SQUAD_AI_PROVIDER=huggingface`) | Issue-first deliverables (BA, reports) via router API | Per-agent model in `.agents/agent-*.md` **## AI Model** |
| Hugging Face **Jobs** | GPU training/batch | Optional per tech spec |
| Copilot **CLI agent** | Long tasks from terminal/CI | `gh copilot` / copilot-cli in Actions |

---

## Enable GitHub Copilot agents on this repo

1. Confirm plan: **Copilot Pro+**, **Business**, or **Enterprise** ([pricing](https://github.com/features/copilot/plans)).
2. Repo **Settings → Copilot → Coding agent** → enable for `ai-alpha-squad`.
3. Enterprise: org policy must allow coding agent.
4. Open [Agents tab](https://github.com/eduardocerqueira/ai-alpha-squad/agents) → create/select custom agent from `.github/agents/`.
5. Assign an issue to Copilot or start a session with prompt + agent dropdown.

Merge `.github/agents/*.agent.md` to `main` so agents appear in the dropdown.

---

## Path to stronger autonomy

1. **Phase 1:** Cloud Copilot on target repos; queue repo for BA/spec; Director approvals unchanged.
2. **Phase 2a–2d (implemented):** [director-gate.yml](../.github/workflows/director-gate.yml), [squad-orchestrator.yml](../.github/workflows/squad-orchestrator.yml), [squad-phase-watch.yml](../.github/workflows/squad-phase-watch.yml) — full label-driven SDLC through Release Manager; Director gates on approval and release only. See [docs/squad-orchestrator-automation.md](../docs/squad-orchestrator-automation.md).
3. **Phase 3:** Cloudflare Workflow durable orchestration (optional).
4. **Phase 4:** Metrics from Issues/Actions.

Do not skip Director gates until you explicitly trust full auto-release.

---

## Credentials in cloud runtimes

| Runtime | Where secrets live |
| ------- | ------------------ |
| Copilot cloud agent | Repo **GitHub Secrets**; Copilot can use configured MCP/tools per agent profile |
| GitHub Actions | `SECRETS_AND_VARIABLES.md` |
| Cursor Cloud | Cursor dashboard + env in API |
| Cloudflare Worker | `wrangler secret` |

Local `.env` is for **Director/dev bootstrap only**, not required for Copilot cloud sessions if secrets are in GitHub.

See [infrastructure-prerequisites.md](infrastructure-prerequisites.md).

---

## Related files

- Custom agent profiles: [.github/agents/](../.github/agents/)
- Orchestrator: [squad-orchestrator.md](squad-orchestrator.md)
- Enable checklist: [infrastructure-prerequisites.md](infrastructure-prerequisites.md)
