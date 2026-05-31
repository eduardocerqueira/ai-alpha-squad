# WhatsApp webhook — HTTPS / custom domain

## Why `workers.dev` shows `ERR_SSL_VERSION_OR_CIPHER_MISMATCH`

The URL `https://<worker>.<account-subdomain>.workers.dev` depends on Cloudflare issuing a certificate for `*.<account-subdomain>.workers.dev`.

On **new** Cloudflare accounts (including **Eduardomcerqueira@gmail.com's Account**), that certificate can take **minutes to 24 hours** to become active. Until then, browsers and Meta show:

- `ERR_SSL_VERSION_OR_CIPHER_MISMATCH`
- `unsupported protocol`

The Worker is deployed; only edge TLS for `workers.dev` is not ready yet.

Check:

```bash
chmod +x scripts/check-whatsapp-webhook-url.sh
./scripts/check-whatsapp-webhook-url.sh
```

Cloudflare also recommends **custom domains** for production webhooks instead of `workers.dev`.

## Recommended fix: custom domain (same CF account)

Prerequisites:

1. A domain (or subdomain) added to **the same** Cloudflare account as `CLOUDFLARE_ACCOUNT_ID` in `.env`.
2. API token with **Workers Scripts Edit** and **Zone DNS Edit** (or Zone Edit).

Steps:

1. [dash.cloudflare.com](https://dash.cloudflare.com) → **Add a site** → onboard the domain (Free plan is enough).
2. In `.env`:

   ```bash
   WHATSAPP_WEBHOOK_HOSTNAME=whatsapp-webhook.yourdomain.com
   ```

   Use a **dedicated hostname** (not your main marketing site apex unless intentional).

3. Deploy:

   ```bash
   ./scripts/deploy-whatsapp-webhook.sh
   ```

   Wrangler attaches the custom domain and provisions TLS automatically.

4. Verify:

   ```bash
   ./scripts/check-whatsapp-webhook-url.sh
   ```

5. Meta → WhatsApp → Configuration → Webhook:

   - **Callback URL:** `https://whatsapp-webhook.yourdomain.com/webhook`
   - **Verify token:** `WHATSAPP_WEBHOOK_VERIFY_TOKEN`

## Optional: disable `workers.dev` after custom domain works

In `workers/whatsapp-webhook/wrangler.jsonc` set `"workers_dev": false` so only the custom hostname is public.

## Account reminder

Use **ai-alpha-squad** Cloudflare account (`3f44f51e37ea6bdeddef740bd381b452` / Eduardomcerqueira@gmail.com's Account). **Bmhp** is a different project — do not use that account or zone here.
