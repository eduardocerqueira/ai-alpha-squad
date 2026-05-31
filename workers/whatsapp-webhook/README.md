# WhatsApp webhook Worker

Receives Meta WhatsApp webhooks, classifies Director replies, and posts to GitHub Issues.

## Deploy

From repo root (requires `.env` with secrets):

```bash
./scripts/deploy-whatsapp-webhook.sh
```

Or manually:

```bash
cd workers/whatsapp-webhook
npm install
npx wrangler secret put WHATSAPP_WEBHOOK_VERIFY_TOKEN
npx wrangler secret put WHATSAPP_DIRECTOR_PHONE
npx wrangler secret put GITHUB_TOKEN
# Optional but recommended:
npx wrangler secret put WHATSAPP_APP_SECRET
npm run deploy
```

Note the Worker URL from deploy output, e.g. `https://ai-alpha-squad-whatsapp-webhook.<subdomain>.workers.dev/webhook`

## Meta configuration

In app → WhatsApp → Configuration:

| Field | Value |
| ----- | ----- |
| Callback URL | `https://…/webhook` |
| Verify token | Same as `WHATSAPP_WEBHOOK_VERIFY_TOKEN` |
| Webhook fields | `messages` |

Set **App Secret** in Meta → App settings → Basic → use as `WHATSAPP_APP_SECRET` on the Worker.

## Environment

| Variable | Secret | Description |
| -------- | ------ | ----------- |
| `WHATSAPP_WEBHOOK_VERIFY_TOKEN` | yes | Meta webhook verify |
| `WHATSAPP_DIRECTOR_PHONE` | yes | E.164 Director number |
| `GITHUB_TOKEN` | yes | `repo` scope for comments/labels |
| `WHATSAPP_APP_SECRET` | yes | Validates `X-Hub-Signature-256` on POST |
| `GITHUB_OWNER` | var | Default `eduardocerqueira` |
| `SQUAD_WORK_QUEUE_REPO` | var | Default `ai-alpha-squad` |
| `WHATSAPP_DEFAULT_ISSUE_NUMBER` | var | Issue to update until KV correlation exists |

## Test

```bash
npm test
```
