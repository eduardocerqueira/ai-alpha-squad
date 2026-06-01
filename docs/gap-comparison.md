# GitAgent Protocol (GAP) vs AI Alpha Squad

Research note for evaluating [GitAgent Protocol](https://www.gitagent.sh/) ([open spec](https://github.com/open-gitagent/gitagent-protocol/blob/main/spec/SPECIFICATION.md), [`gapman` CLI](https://www.npmjs.com/package/@open-gitagent/gapman)) alongside the squad delivery model.

**Status:** exploratory — no adoption committed. Use this doc when comparing standards, exporting roles, or designing interoperability.

---

## Executive summary

| | GitAgent Protocol (GAP) | AI Alpha Squad |
|---|------------------------|----------------|
| **What it is** | Open, framework-agnostic **agent packaging** standard | **Multi-agent SDLC organization** on GitHub Issues |
| **Primary artifact** | `agent.yaml` + `SOUL.md` in an agent repo | Parent issue + labels + phase templates on work-queue repo |
| **Execution** | `gapman` / adapters (Claude, CrewAI, OpenAI, …) | GitHub Actions orchestrator, Copilot custom agents, optional Cursor/WhatsApp |
| **Multi-agent** | Composable via `agents/`, `delegation`, `workflows/` | Fixed phase pipeline + parallel validation (see [squad-orchestrator.md](../.agents/squad-orchestrator.md)) |
| **Human gates** | Compliance / SOD in spec (`DUTIES.md`, `compliance/`) | Director labels + [director-gate.md](director-gate.md) + WhatsApp |

GAP does **not** replace squad orchestration. It could **standardize how each squad role is defined** and exported to other runtimes.

---

## Architecture (two layers)

```text
┌──────────────────────────────────────────────────────────────────┐
│  AI Alpha Squad — delivery organization (this repo)                 │
│  • GitHub Issues = work queue (ai-alpha-squad)                    │
│  • Target repos = product code (vscode-squad-director, seeker, …) │
│  • Labels = lifecycle state machine                               │
│  • Actions: orchestrator, phase-watch, PR guard, project-sync     │
│  • Director gates: awaiting-approval, release-candidate           │
└────────────────────────────┬─────────────────────────────────────┘
                             │ optional: each role as GAP package
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│  GitAgent Protocol — per-agent definition (future / research)     │
│  • agent.yaml manifest + SOUL.md identity                         │
│  • RULES.md / DUTIES.md boundaries                              │
│  • skills/, tools/, hooks/, memory/                               │
│  • gapman validate | export | run -a <adapter>                    │
└──────────────────────────────────────────────────────────────────┘
```

Squad flow diagram: [site/public/assets/images/squad-flow.svg](../site/public/assets/images/squad-flow.svg).  
Automation map: [squad-orchestrator-automation.md](squad-orchestrator-automation.md).

---

## Concept mapping

### GAP required / recommended files → Squad equivalents

| GAP (spec v0.1) | AI Alpha Squad today | Notes |
|-----------------|----------------------|-------|
| `agent.yaml` | `.github/agents/<role>.agent.md` frontmatter | Copilot custom agent profile; not full GAP schema |
| `SOUL.md` | Tone/role in `agent-<role>.md` backstory sections | Could be extracted verbatim for GAP export |
| `RULES.md` | `agent-*.md` constraints + [copilot-issue-first-delivery.md](../.agents/copilot-issue-first-delivery.md) | Squad adds **issue-first** rules GAP does not define |
| `DUTIES.md` | [squad-orchestrator.md](../.agents/squad-orchestrator.md) decision rules | GAP SOD matrix is richer for regulated industries |
| `AGENTS.md` | [AGENTS.md](../AGENTS.md) (repo root) | Similar “read this first” pattern |
| `skills/` | [.agents/skills/](../.agents/skills/) | Compatible idea; squad uses Cursor/Copilot skill layout |
| `tools/` (YAML + impl) | MCP servers, `gh`, Copilot tools in agent profiles | Squad is runtime-specific, not declarative YAML tools |
| `workflows/` | GitHub Actions + label transitions | Squad workflows are **org-level**, not per-agent repo |
| `hooks/` | `.github/workflows/*`, shell scripts in `scripts/` | PR guard, nudge, sync-labels = lifecycle hooks |
| `memory/` | Issue comments + GitHub history | Squad state is **issue-thread**, not agent MEMORY.md |
| `agents/` sub-agents | Sub-issues per role on parent job | Same roles, different linking model (issues vs dirs) |
| `compliance/` | Security agent, [definition-of-done.md](../.agents/definition-of-done.md) | GAP targets FINRA/SEC-style packs; squad is lighter |

### GAP “14 git-native patterns” → Squad

Reference: [GitAgent — 14 patterns](https://medium.com/@shreyas.kapale/gitagent-all-ai-agents-should-follow-these-14-patterns-ffc0a79bac0e).

| Pattern (summary) | Squad alignment |
|-------------------|-----------------|
| Version control for agent definition | `.agents/` + templates versioned on `main` |
| Live agent memory in git | Job memory = issue + comments; not per-agent `memory/` |
| Agent versioning (tags, branches) | Template/agent doc changes via normal PRs to ai-alpha-squad |
| Stateless compute, git as state | Actions runners stateless; **labels on issues** = state |
| Branch-based deployment | Product code on target repo branches/PRs |
| Knowledge tree | `.agents/skills/`, `references/` in skills |
| Agent diff / audit trail | Issue comments, PR history, project board |
| Secrets outside repo | `.env` local; GitHub Secrets for Actions/Copilot |
| Lifecycle + segregation of duties | Phase owners + Director-only labels |

---

## Per-role GAP mapping (spike layout)

Future experiment: one directory per role under `gap-agents/` (or separate repos) without changing runtime yet.

| Squad label | GAP `name` | Primary squad source | Export target (research) |
|-------------|------------|----------------------|---------------------------|
| `business-owner` | `business-owner` | `agent-business-owner.md`, BA template | Copilot `business-owner`, Cursor |
| `architect` | `architect` | `agent-architect.md`, tech-spec template | Copilot `architect` |
| `developer` | `developer` | `agent-developer.md`, target repo profile | Copilot on **target repo** |
| `qa` | `qa` | `agent-qa.md`, qa-report template | Copilot `qa` |
| `security` | `security` | `agent-security.md`, security-report template | Cursor / manual + tools |
| `devops` | `devops` | `agent-devops.md`, deployment checklist | Copilot + Actions |
| `tech-writer` | `tech-writer` | `agent-tech-writer.md`, release-notes template | Copilot |
| `release-manager` | `release-manager` | `agent-release-manager.md`, release-plan template | Copilot + WhatsApp skill |

Example minimal GAP layout for **architect** (illustrative only):

```text
gap-agents/architect/
├── agent.yaml          # name, version, model hints, skills: [architect]
├── SOUL.md             # extracted from agent-architect.md persona
├── RULES.md            # issue-first, no queue-repo PR, FR→BR traceability
├── DUTIES.md           # may design; must not implement product code
└── skills/
    └── architect/      # symlink or copy of relevant .agents/skills
```

Validation (when adopted): `npx @open-gitagent/gapman validate gap-agents/architect`.

---

## What GAP would not solve (squad-specific)

Documented production friction — **keep squad automation** even if GAP is adopted for role packaging:

| Problem | Squad mitigation | GAP alone |
|---------|------------------|-----------|
| Copilot opens planning PRs on queue repo | [copilot-issue-first-delivery.md](../.agents/copilot-issue-first-delivery.md), PR guard, read-only BO/Architect tools | Needs explicit `RULES.md` + enforcement runtime |
| Actions “workflow awaiting approval” on Copilot branches | Scheduled PR guard, [copilot-workflow-approval.md](copilot-workflow-approval.md) | Not addressed |
| Board shows wrong phase vs Copilot sessions | [director-project-board.md](director-project-board.md), Copilot×N active agent | Not addressed |
| Phase 4 parallel validation | Matrix job on `implemented` label | Custom `workflows/` only |
| Queue vs target repo split | Orchestrator + sub-issues + target-repo hook | Not in GAP core |

---

## What GAP could add (future value)

1. **Portable role definitions** — `gapman export -a claude` / `crewai` for experiments in [AI-sandbox](https://github.com/eduardocerqueira/AI-sandbox) without rewriting prompts.
2. **CI validation** — `gapman validate` on PRs that touch agent definitions (schema in [spec/schemas](https://github.com/open-gitagent/gitagent-protocol/tree/main/spec/schemas)).
3. **Compliance pack** — if squad jobs touch regulated domains, map Security + Director gates to GAP `compliance.segregation_of_duties` and `DUTIES.md` handoffs.
4. **Sub-agent composition** — GAP `agents/` + `delegation.router` as an alternative mental model to sub-issues (research only; Issues remain source of truth unless explicitly changed).
5. **Cross-framework skills** — align `.agents/skills/` discovery with GAP skill layout for publish/subscribe between repos.

---

## Adoption phases (proposed, not scheduled)

| Phase | Scope | Risk |
|-------|--------|------|
| **0 — Research** | This document; watch [open-gitagent/gitagent-protocol](https://github.com/open-gitagent/gitagent-protocol) releases | None |
| **1 — Mirror** | Add `docs/gap-agents/` with read-only GAP exports generated from existing `agent-*.md` | Low; no runtime change |
| **2 — Validate** | Optional CI job: `gapman validate` on `gap-agents/**` | Low |
| **3 — Dual profile** | Keep `.github/agents/*.agent.md`; generate or sync from GAP manifest | Medium; drift if not automated |
| **4 — Runtime** | Try `gapman run` for one role (e.g. Business Owner) vs Copilot | Medium; Director gates unchanged |

**Non-goal:** Replace GitHub Issues label orchestration with GAP `workflows/` as the sole state machine.

---

## References

| Resource | URL |
|----------|-----|
| GAP website | https://www.gitagent.sh/ |
| GAP specification | https://github.com/open-gitagent/gitagent-protocol/blob/main/spec/SPECIFICATION.md |
| GAP manager CLI (`gapman`) | https://www.npmjs.com/package/@open-gitagent/gapman |
| GitAgent repo (runtime / SDK) | https://github.com/open-gitagent/gitagent |
| Squad orchestrator | [../.agents/squad-orchestrator.md](../.agents/squad-orchestrator.md) |
| Squad automation | [squad-orchestrator-automation.md](squad-orchestrator-automation.md) |
| Issue lifecycle | [../.agents/issue-lifecycle.md](../.agents/issue-lifecycle.md) |
| Runtime strategy | [../.agents/agent-runtime-strategy.md](../.agents/agent-runtime-strategy.md) |

---

## Open questions (for next research pass)

1. Does `gapman` support a **GitHub Copilot** adapter that respects issue-only delivery (no PR on queue repo)?
2. Can GAP `hooks/` invoke squad scripts (`squad-sync-planning-labels.sh`, `squad-dispatch-copilot.sh`) without duplicating Actions?
3. Should each **target product repo** carry a GAP `developer` agent package while the queue repo carries planning roles only?
4. Is there a community mapping from GAP `compliance.segregation_of_duties` to squad labels for audit exports?
5. Version pinning: `spec_version` in `agent.yaml` vs squad template versions (`BR-*`, `FR-*` IDs).

---

*Last updated: 2026-06-01 — created for Director / architect research; revise when GAP spec or squad orchestration changes.*
