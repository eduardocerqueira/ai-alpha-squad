# Project Agent Skills

Skills extend Cursor (and other agents) with domain workflows. Installed under this directory via [Skills CLI](https://skills.sh/) (`npx skills`).

## Restore on a new machine

From the repository root:

```bash
npx skills experimental_install -y --agent cursor
```

Or run [.agents/skills-install.sh](../skills-install.sh).

Lock file: [skills-lock.json](../../skills-lock.json).

## Mapping to example jobs (TODO)

| Job | Primary skills | Also used |
| --- | -------------- | --------- |
| **1. VS Code extension** (Marketplace + [Open VSX](https://open-vsx.org/)) | `vscode-extension-expert`, `typescript-advanced-types` | `github-actions-docs`, `playwright-best-practices`, `changelog-automation` |
| **2. Modernize legacy repos** ([seeker](https://github.com/eduardocerqueira/seeker), [cloudbitsgo](https://github.com/eduardocerqueira/cloudbitsgo)) | `refactor`, `review-and-refactor`, `request-refactor-plan` | `typescript-advanced-types`, `playwright-best-practices`, `web-perf` |
| **3. Simple game → Apple App Store** | `swiftui-expert-skill`, `appstore-readiness`, `game-development` | `changelog-automation`, `github-actions-docs` |

## Squad infrastructure (TODO Infra)

| Need | Skills |
| ---- | ------ |
| Cloudflare (Workers, D1, R2, DNS) | `cloudflare`, `wrangler`, `workers-best-practices`, `agents-sdk`, `durable-objects`, `sandbox-sdk` |
| GitHub Actions / releases | `github-actions-docs`, `changelog-automation` |
| Hugging Face / LLMs | `hf-cli` |
| QA / E2E | `playwright-best-practices` |
| **WhatsApp → Director** (Business Owner, Release Manager) | `whatsapp-director` (squad), `whatsapp-cloud-api`, `integrate-whatsapp`, `observe-whatsapp` — [whatsapp-director-channel.md](../whatsapp-director-channel.md) |

## Installed skills

Squad-local (not on skills.sh): `whatsapp-director` — committed in this repo.

### External (skills.sh)

| Skill | Source | Installs (skills.sh) |
| ----- | ------ | -------------------- |
| vscode-extension-expert | s-hiraoku/vscode-sidebar-terminal | ~84 |
| typescript-advanced-types | wshobson/agents | ~44K |
| refactor | github/awesome-copilot | ~17K |
| review-and-refactor | github/awesome-copilot | ~10K |
| request-refactor-plan | mattpocock/skills | ~15K |
| swiftui-expert-skill | avdlee/swiftui-agent-skill | ~22K |
| appstore-readiness | jmsktm/claude-settings | ~150 |
| game-development | sickn33/antigravity-awesome-skills | ~2.7K |
| github-actions-docs | xixu-me/skills | ~184K |
| changelog-automation | wshobson/agents | ~8.9K |
| playwright-best-practices | currents-dev/playwright-best-practices-skill | ~45K |
| hf-cli | huggingface/skills | ~1.1K |
| cloudflare, wrangler, workers-best-practices, agents-sdk, durable-objects, sandbox-sdk, web-perf | cloudflare/skills | 8K–18K each |
| find-skills | vercel-labs/skills | ~1.8M |
| whatsapp-cloud-api | bellopushon/whatsapp-cloud-api | ~294 |
| integrate-whatsapp | gokapso/agent-skills | ~2.1K |
| observe-whatsapp | gokapso/agent-skills | ~1.4K |

## Add more skills

```bash
npx skills find <keyword>
npx skills add <owner/repo@skill-name> --agent cursor -y
```

Browse: https://skills.sh/

**Note:** No dedicated Open VSX skill was found; `vscode-extension-expert` covers Marketplace publishing—add Open VSX steps to your release checklist when packaging for https://open-vsx.org/.
