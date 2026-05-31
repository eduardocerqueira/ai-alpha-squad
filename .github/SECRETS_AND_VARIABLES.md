# GitHub Secrets and Variables

Reference for DevOps when adding Actions on **ai-alpha-squad** or **target product repos**. Do not store values in this file.

Setup guide: [.agents/infrastructure-prerequisites.md](../.agents/infrastructure-prerequisites.md).

## Repository secrets (typical)

| Name | Required when |
| ---- | ------------- |
| `CLOUDFLARE_API_TOKEN` | Deploying Workers / Pages |
| `VSCE_PAT` | VS Code Marketplace publish |
| `OPENVSX_PAT` | Open VSX publish |
| `HF_TOKEN` | HF Jobs or model access in CI |
| `WHATSAPP_ACCESS_TOKEN` | WhatsApp send/receive automation |
| `WHATSAPP_WEBHOOK_VERIFY_TOKEN` | WhatsApp webhook Worker |
| `APP_STORE_CONNECT_API_KEY` | Base64 or JSON key for ASC API (prefer OIDC/env file in secure runner) |

Use environment-specific secrets (`production`, `staging`) once workflows exist.

## Repository variables (non-secret)

| Name | Example |
| ---- | ------- |
| `GITHUB_OWNER` | `eduardocerqueira` |
| `CLOUDFLARE_ACCOUNT_ID` | From Cloudflare dashboard |
| `VSCE_PUBLISHER` | Marketplace publisher name |

## Configure via CLI

```bash
gh secret set CLOUDFLARE_API_TOKEN --repo eduardocerqueira/ai-alpha-squad
gh variable set CLOUDFLARE_ACCOUNT_ID --repo eduardocerqueira/ai-alpha-squad --body "your-account-id"
```

Target repos (`seeker`, `cloudbitsgo`, extension repo) get their own secrets when DevOps wires per-repo CI.
