# Infrastructure Prerequisites

Director-owned setup **before** the first business-request issue moves past intake. Agents assume these exist; DevOps extends them per job tech spec.

**Secrets:** use local `.env` (from [.env.example](../.env.example)) and [GitHub repository secrets](#github-repository-secrets). Never commit tokens, PATs, or `.env`.

## Ready-for-first-job checklist

| # | Item | Owner | Verify |
| - | ---- | ----- | ------ |
| 1 | GitHub Issues + labels on work-queue repo | Director | [Issues](https://github.com/eduardocerqueira/ai-alpha-squad/issues) — templates work |
| 2 | `gh` authenticated with `repo` scope | Director | `gh auth status` |
| 3 | `.env` copied from `.env.example` and filled | Director | `./scripts/verify-prerequisites.sh` |
| 4 | `squad-config.yaml` from [squad-config.example.yaml](squad-config.example.yaml) (optional) | Director | — |
| 5 | WhatsApp Director channel (if using approvals via WhatsApp) | Director | [whatsapp-director-channel.md](whatsapp-director-channel.md) |
| 6 | Cloudflare account + API token (if any job uses Workers/R2/D1) | Director / DevOps | `wrangler whoami` |
| 7 | Hugging Face token (if agents use Hub/Jobs) | Director | `hf auth whoami` |
| 8 | Copilot coding agent enabled (cloud) **or** local Cursor | Director | [agent-runtime-strategy.md](agent-runtime-strategy.md) |
| 9 | Job-specific secrets identified below | Architect → DevOps | Documented on issue |

CI/CD pipelines: **deferred** until first job implementation (DevOps sub-issue).

---

## GitHub (all jobs)

### What agents need

- Create/update issues, comments, labels
- Open PRs on target repos (same org or fork)
- Releases, tags, changelog (Release Manager)
- Repository secrets when Actions exist (DevOps)

### Director setup

1. Ensure [ai-alpha-squad](https://github.com/eduardocerqueira/ai-alpha-squad) is the **work queue** (issues for every job).
2. Authenticate CLI: `gh auth login` (scopes: `repo`, `read:org` if using org).
3. For automation without interactive `gh`, create a fine-grained or classic PAT with repo access → `GITHUB_TOKEN` in `.env`.

### GitHub repository secrets

Configure when CI or GitHub Actions automation is added (first job). Standard names:

| Secret | Used by | Notes |
| ------ | ------- | ----- |
| `GITHUB_TOKEN` | Actions | Often `${{ secrets.GITHUB_TOKEN }}` default is enough for same-repo |
| `CLOUDFLARE_API_TOKEN` | Deploy Worker | From Cloudflare dashboard |
| `VSCE_PAT` | Publish VS Code extension | Marketplace **Manage** scope |
| `OPENVSX_PAT` | Publish to Open VSX | [open-vsx.org](https://open-vsx.org) profile → Access Tokens |
| `HF_TOKEN` | HF Jobs / model pull in CI | Hugging Face settings |
| `WHATSAPP_ACCESS_TOKEN` | WhatsApp webhook Worker | Meta or Kapso |
| `WHATSAPP_WEBHOOK_VERIFY_TOKEN` | Webhook verification | Random string you define |

Use **Environments** (`production`, `staging`) for release approvals when DevOps adds workflows.

### Non-secret variables (GitHub Variables)

| Variable | Example |
| -------- | ------- |
| `CLOUDFLARE_ACCOUNT_ID` | Cloudflare dashboard |
| `VSCE_PUBLISHER` | Marketplace publisher name |
| `GITHUB_OWNER` | `eduardocerqueira` |

---

## WhatsApp — Director channel

Required only if Business Owner / Release Manager should notify the Director outside GitHub.

### Meta WhatsApp Cloud API (default)

1. [Meta Business](https://business.facebook.com/) → WhatsApp → API setup.
2. Add a business phone number; note `phone_number_id`.
3. Permanent token or System User token → `WHATSAPP_ACCESS_TOKEN`.
4. Set `WHATSAPP_DIRECTOR_PHONE` (Director personal E.164).
5. Deploy inbound webhook (Cloudflare Worker recommended) — DevOps first-job deliverable if not done early.
6. `WHATSAPP_WEBHOOK_VERIFY_TOKEN` — random string for GET verification.

### Kapso (alternative)

1. `kapso login` or `KAPSO_API_KEY` + `KAPSO_API_BASE_URL`.
2. Skills: `integrate-whatsapp`, `observe-whatsapp`.

Protocol: [whatsapp-director-channel.md](whatsapp-director-channel.md).

---

## Cloudflare

Needed when tech spec includes Workers, R2, D1, DNS, or WhatsApp webhook hosting.

### Director setup

1. Account at [dash.cloudflare.com](https://dash.cloudflare.com).
2. Create API token: **Edit Cloudflare Workers** (+ R2/D1 if used) → `CLOUDFLARE_API_TOKEN`.
3. Account ID → `CLOUDFLARE_ACCOUNT_ID`.
4. Local: `npm i -g wrangler` then `wrangler login` **or** use token: `export CLOUDFLARE_API_TOKEN=...`

Agents use skills: `wrangler`, `cloudflare`, `workers-best-practices`, `agents-sdk`.

---

## Hugging Face

Needed when jobs use Hub models, Spaces, or HF Jobs for training/inference.

1. [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) → read/write as needed.
2. `HF_TOKEN` in `.env` and GitHub secret for CI.
3. CLI: `pip install huggingface_hub` → `hf auth login` or `HF_TOKEN`.

Skill: `hf-cli`.

---

## Job-specific credentials

### Job 1 — VS Code extension (Marketplace + Open VSX)

| Credential | Where | Purpose |
| ---------- | ----- | ------- |
| `VSCE_PAT` | `.env` + GitHub secret | `vsce publish` — Azure DevOps PAT with **Marketplace Manage** |
| `OPENVSX_PAT` | `.env` + GitHub secret | `ovsx publish` — Open VSX access token |
| Publisher ID | `squad-config` / issue | Marketplace publisher name (public) |
| Open VSX namespace | issue | Usually aligned with publisher |

Create publisher: [Visual Studio Marketplace](https://marketplace.visualstudio.com/manage), [open-vsx.org](https://open-vsx.org).

Extension **code repo** may differ from `ai-alpha-squad`; track delivery repo on the issue.

### Job 2 — Modernize seeker / cloudbitsgo

Credentials live in **each target repository**, not in ai-alpha-squad:

| Item | Notes |
| ---- | ----- |
| Clone access | `gh` auth must reach `eduardocerqueira/seeker`, `eduardocerqueira/cloudbitsgo` |
| Stack-specific | Read each repo README; Architect documents in tech spec |
| Deploy keys / cloud | Per-repo `.env.example` — DevOps adds CI secrets on **target repo** |
| No squad-wide PAT in git | Use GitHub Apps or repo-scoped tokens per project |

Work queue issue on `ai-alpha-squad` links to target repo PRs.

### Job 3 — iOS game → App Store

| Credential | Where | Purpose |
| ---------- | ----- | ------- |
| Apple Developer Program | Apple account | Membership active |
| App Store Connect API key | `.p8` file **outside repo** | CI/TestFlight/upload |
| `APP_STORE_CONNECT_KEY_ID`, `ISSUER_ID` | `.env` / secrets | API auth |
| `APPLE_TEAM_ID` | config | Signing |
| Certificates / profiles | Xcode or Fastlane Match | DevOps + Developer — **never commit** |
| App-specific password | `.env` only if using altool legacy | Prefer API key |

Skill: `appstore-readiness`, `swiftui-expert-skill`.

---

## Agent runtime (cloud vs local)

**Recommended:** [agent-runtime-strategy.md](agent-runtime-strategy.md) — use **GitHub Copilot cloud agent** on product repos for code; use **ai-alpha-squad** as the issue queue with custom agents in [.github/agents/](../.github/agents/).

| Check | Action |
| ----- | ------ |
| Copilot plan | Pro+, Business, or Enterprise |
| Coding agent enabled | Repo **Settings → Copilot** → enable for `ai-alpha-squad` and each target repo |
| Custom agents on `main` | Merge `.github/agents/*.agent.md` |
| Agents UI | [github.com/eduardocerqueira/ai-alpha-squad/agents](https://github.com/eduardocerqueira/ai-alpha-squad/agents) |

Cloud runs use **GitHub Secrets**, not your laptop `.env`. Local Cursor remains optional for Director or ad-hoc work.

---

## Local agent runtime (Cursor, optional)

1. Open workspace at repo root (or target project).
2. Load `.env` — use direnv or Cursor env settings.
3. Skills: `./.agents/skills-install.sh` or `npx skills experimental_install -y --agent cursor`.

Optional: [Cursor Cloud API](https://cursor.com/docs/sdk) (`CURSOR_API_KEY`) for scripted orchestration.

---

## Verify setup

```bash
cp .env.example .env
# edit .env
cp .agents/squad-config.example.yaml .agents/squad-config.yaml
# edit non-secret defaults

./scripts/verify-prerequisites.sh
```

---

## Agent responsibilities after first issue

| Agent | Infra action |
| ----- | ------------ |
| Architect | List required secrets/bindings in tech spec |
| DevOps | Target-repo Actions, Cloudflare deploy, webhook, environments |
| Security | Review secret handling, least privilege, no leaks in issues |
| Release Manager | GitHub Release permissions, changelog, WhatsApp release notify |

---

## Related docs

- [whatsapp-director-channel.md](whatsapp-director-channel.md)
- [agent-devops.md](agent-devops.md)
- [.github/SECRETS_AND_VARIABLES.md](../.github/SECRETS_AND_VARIABLES.md)
- [skills/README.md](skills/README.md)
