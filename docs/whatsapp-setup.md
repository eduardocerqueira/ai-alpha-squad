# WhatsApp Director channel — setup guide

Get Business Owner and Release Manager agents notifying you on WhatsApp and understanding replies. Protocol: [.agents/whatsapp-director-channel.md](../.agents/whatsapp-director-channel.md).

## Overview

| Piece | Purpose |
| ----- | ------- |
| Meta WhatsApp Cloud API | Send messages to Director; receive replies via webhook |
| `.env` / GitHub Secrets | Tokens and phone IDs (never commit real values) |
| Cloudflare Worker (recommended) | Public HTTPS webhook for inbound messages |
| `src/ai_alpha_squad/whatsapp/` | Reply classification + webhook helpers (unit tested) |

Alternative: [Kapso](https://kapso.ai) — skill `integrate-whatsapp` if you prefer managed onboarding.

---

## Step 1 — Meta Business and WhatsApp app

1. Go to [Meta for Developers](https://developers.facebook.com/) → **My Apps** → **Create App** → type **Business**.
2. Add product **WhatsApp** → **API Setup**.
3. Note:
   - **Phone number ID** → `WHATSAPP_PHONE_NUMBER_ID`
   - **WhatsApp Business Account ID** (for support docs)
4. Add a test number or production business number (Meta guides you through verification).
5. Create a **System User** in Business Settings → assign WhatsApp assets → generate a **permanent token** with `whatsapp_business_messaging` and `whatsapp_business_management` → `WHATSAPP_ACCESS_TOKEN`.

Official docs: [WhatsApp Cloud API get started](https://developers.facebook.com/docs/whatsapp/cloud-api/get-started).

---

## Step 2 — Director phone number

1. Set your personal WhatsApp (E.164) in `.env`:

   ```bash
   WHATSAPP_DIRECTOR_PHONE=+1XXXXXXXXXX
   ```

2. For **sandbox/test**, add your number under API Setup → “To” field so Meta allows outbound to you.

---

## Step 3 — Local environment

```bash
cd ai-alpha-squad
cp .env.example .env
```

Fill at minimum:

```bash
WHATSAPP_API_PROVIDER=meta
WHATSAPP_DIRECTOR_PHONE=+1...
WHATSAPP_PHONE_NUMBER_ID=...
WHATSAPP_ACCESS_TOKEN=...
WHATSAPP_WEBHOOK_VERIFY_TOKEN=choose-a-long-random-string
GITHUB_TOKEN=...   # for posting issue comments from automation
GITHUB_OWNER=eduardocerqueira
SQUAD_WORK_QUEUE_REPO=ai-alpha-squad
```

Verify:

```bash
./scripts/verify-prerequisites.sh
python3 -m pytest tests/ -q
```

---

## Step 4 — Webhook (inbound replies)

Meta must reach a public **HTTPS** URL.

### Option A — Cloudflare Worker (recommended)

1. Ensure `wrangler login` or `CLOUDFLARE_API_TOKEN` + `CLOUDFLARE_ACCOUNT_ID` in `.env`.
2. Deploy the squad webhook Worker (DevOps deliverable; scaffold in `workers/whatsapp-webhook/` when added).
3. In Meta → WhatsApp → **Configuration** → **Webhook**:
   - **Callback URL:** `https://<your-worker>.workers.dev/webhook`
   - **Verify token:** same as `WHATSAPP_WEBHOOK_VERIFY_TOKEN`
   - Subscribe to **messages** (and **message_echoes** if needed).
4. Click **Verify and save** — Meta sends `hub.mode=subscribe`; Worker must return `hub.challenge`.

### Option B — Kapso

Use skill `integrate-whatsapp`: `kapso login`, `kapso setup`, configure project webhook to your endpoint.

---

## Step 5 — GitHub Secrets (cloud / Actions)

When the Worker or Actions workflow runs in CI:

```bash
gh secret set WHATSAPP_ACCESS_TOKEN --repo eduardocerqueira/ai-alpha-squad
gh secret set WHATSAPP_PHONE_NUMBER_ID --repo eduardocerqueira/ai-alpha-squad
gh secret set WHATSAPP_WEBHOOK_VERIFY_TOKEN --repo eduardocerqueira/ai-alpha-squad
gh variable set WHATSAPP_DIRECTOR_PHONE --repo eduardocerqueira/ai-alpha-squad --body "+1..."
```

See [.github/SECRETS_AND_VARIABLES.md](../.github/SECRETS_AND_VARIABLES.md).

---

## Step 6 — Test outbound (manual)

Send a test text via curl (replace IDs and token):

```bash
curl -s "https://graph.facebook.com/v21.0/${WHATSAPP_PHONE_NUMBER_ID}/messages" \
  -H "Authorization: Bearer ${WHATSAPP_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{
    \"messaging_product\": \"whatsapp\",
    \"to\": \"${WHATSAPP_DIRECTOR_PHONE}\",
    \"type\": \"text\",
    \"text\": { \"body\": \"[AI Alpha Squad] Test — reply APPROVE to confirm inbound.\" }
  }"
```

Reply from your phone; confirm webhook logs the payload (or paste reply on issue #1 for manual classification until Worker is live).

---

## Step 7 — Wire agents

1. Business Owner posts BA → sends template from [whatsapp-director skill](../.agents/skills/whatsapp-director/SKILL.md).
2. You reply `APPROVE` / `REJECT: reason` / `CHANGES: question`.
3. Automation classifies with `classify_director_reply()` (see unit tests) and posts audit comment on the issue.

---

## Troubleshooting

| Problem | Check |
| ------- | ----- |
| Message not delivered | Number in Meta test list; token scopes; E.164 format |
| Webhook verify fails | `WHATSAPP_WEBHOOK_VERIFY_TOKEN` matches Meta UI exactly |
| Wrong issue updated | Outbound messages must include `Issue #N` for correlation |
| 401 from Graph API | Regenerate token; clock skew rare |

Skill references: `whatsapp-cloud-api`, `observe-whatsapp` (Kapso).

---

## Next implementation tasks

- [ ] Cloudflare Worker: webhook + optional auto-comment on GitHub issue
- [ ] GitHub Action: smoke test on PR (pytest + optional dry-run send)
- [ ] Issue context store (KV/D1) mapping last outbound → issue number
