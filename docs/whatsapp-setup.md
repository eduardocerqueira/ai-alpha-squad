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

### HTTPS / `ERR_SSL_VERSION_OR_CIPHER_MISMATCH`

If `*.eduardomcerqueira.workers.dev` TLS is not ready yet (new account) or the browser shows **unsupported protocol**, use a **custom domain** on this same Cloudflare account. See [whatsapp-webhook-hostname.md](whatsapp-webhook-hostname.md).

```bash
./scripts/check-whatsapp-webhook-url.sh
```

### Option A — Cloudflare Worker (recommended)

1. Ensure `wrangler login` or `CLOUDFLARE_API_TOKEN` + `CLOUDFLARE_ACCOUNT_ID` in `.env`.
2. Deploy:

   ```bash
   chmod +x scripts/deploy-whatsapp-webhook.sh
   ./scripts/deploy-whatsapp-webhook.sh
   ```

   See [workers/whatsapp-webhook/README.md](../workers/whatsapp-webhook/README.md).

3. In Meta → WhatsApp → **Configuration** → **Webhook**:
   - **Callback URL:** `https://whatsapp-webhook.aialphasquad.com/webhook` (set `WHATSAPP_WEBHOOK_HOSTNAME` in `.env`, then deploy)
   - **Verify token:** same as `WHATSAPP_WEBHOOK_VERIFY_TOKEN`
   - Subscribe to **messages**
4. Set Meta **App secret** in App settings → Basic → add as `WHATSAPP_APP_SECRET` (Worker secret + `.env`).
5. Click **Verify and save** — Meta sends `hub.mode=subscribe`; Worker returns `hub.challenge`.

### Unpublished app / Development mode

Meta may show:

> *Apps will only be able to receive test webhooks sent from the app dashboard while the app is unpublished…*

That warning applies to the **generic App → Webhooks → Test** button. It does **not** mean WhatsApp `messages` webhooks are disabled entirely.

For **AI Alpha Squad (pilot)** while the app is still **Development**:

| Works without App Review | Requires publish / Live mode |
| ------------------------ | ---------------------------- |
| Callback URL verify (subscribe) | Messaging arbitrary customers at scale |
| Director number listed under **WhatsApp → API Setup → test recipients** | Production traffic from anyone not on the test list |
| Inbound text from that Director to your **test / business number** → your Worker | Some advanced permissions if you add more products |

**Pilot checklist (Development):**

1. App mode: **Development** (default) is fine for now.
2. **WhatsApp → API Setup** → add Director phone as allowed **test recipient**.
3. Subscribe webhook field **`messages`** (not every field in the list).
4. Director sends a **text** to the Meta test business number (not only “Send test” from dashboard).
5. Confirm issue comment on GitHub (default issue `#1` until KV correlation exists).

**When to publish:** before treating WhatsApp as production for non-test users, or if webhooks never arrive despite correct URL + `messages` subscription. Publishing usually means **App Review** for `whatsapp_business_messaging` (and related) permissions — plan that as a separate milestone.

### Outbound message types

Outside the 24-hour customer window, use a **template** (e.g. `hello_world`). Free-form `text` works after the Director messages the business number or within the session window.

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

Or from `.env` (validates token before upload):

```bash
./scripts/setup-squad-whatsapp-github.sh
```

See [.github/SECRETS_AND_VARIABLES.md](../.github/SECRETS_AND_VARIABLES.md).

---

## Step 6 — Business Owner notifies Director

When `awaiting-approval` is set on an issue:

```bash
./scripts/notify-director-awaiting-approval.sh <issue_number> "Short summary for WhatsApp"
```

Requires an open **24-hour session** (Director has messaged the business number recently) or an approved template for first contact.

## Step 7 — Test outbound (manual)

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

- [x] Cloudflare Worker: webhook + GitHub issue comment ([workers/whatsapp-webhook](../workers/whatsapp-webhook/))
- [ ] Issue context store (KV/D1) mapping last outbound → issue number (replace `WHATSAPP_DEFAULT_ISSUE_NUMBER`)
- [ ] GitHub Action: smoke test on PR (pytest + worker tests)
