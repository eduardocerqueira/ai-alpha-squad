# Agent Runtime Strategy — Local vs Cloud

The squad was designed around **GitHub Issues as source of truth**. Agents can run on your laptop (Cursor) or in the cloud (GitHub Copilot coding agent, Cursor Cloud, Workers). **Full autonomy does not require your machine**, but no single product replaces the entire multi-agent workflow today.

## Short answer

| Goal | Recommendation |
| ---- | ---------------- |
| Stop using your Mac for coding work | **Yes** — run implementation on **GitHub Copilot cloud agent** on **target product repos** |
| Run Business Owner + Architect + QA as separate cloud agents | **Partial** — use **custom agents** in `.github/agents/` (this repo + product repos); orchestration between phases still needs Issues + labels (and optionally a workflow) |
| True end-to-end autonomy (issue → release, no human) | **Not yet** — keep **Director gates**; add automation to *invoke* the next agent when labels change |
| WhatsApp approvals | **Cloud Worker** (Cloudflare) for webhooks; not GitHub Copilot |

Repository agents UI: [github.com/eduardocerqueira/ai-alpha-squad/agents](https://github.com/eduardocerqueira/ai-alpha-squad/agents) (Copilot sessions for this repo).

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
| Business Owner | Copilot custom `business-owner` **or** Cursor cloud | Issue `new` → assign session / `@copilot` with agent; post BA; `awaiting-approval` |
| Architect | Copilot `architect` (read/edit docs) **or** Cursor | Issue `approved` → tech spec + sub-issues on queue repo |
| Developer | **Copilot cloud on target repo** | Sub-issue on product repo → assign Copilot `developer` |
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

## Path to stronger autonomy (later)

1. **Phase 1 (now):** Cloud Copilot on target repos; queue repo for BA/spec; Director approvals unchanged.
2. **Phase 2:** GitHub Action on `issues: labeled` — comment checklist, optionally call Cursor API or re-assign Copilot with next custom agent.
3. **Phase 3:** Cloudflare Workflow coordinates WhatsApp + issue state + dispatch.
4. **Phase 4:** Metrics (lead time, failure rate) from Issues/Actions.

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
