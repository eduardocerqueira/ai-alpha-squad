# Squad domain — Cloudflare Registrar

Buy a domain on the **ai-alpha-squad** Cloudflare account (`CLOUDFLARE_ACCOUNT_ID` in `.env`), then attach `whatsapp-webhook.<domain>` to the Worker.

## Dashboard prerequisites (one-time)

On [dash.cloudflare.com](https://dash.cloudflare.com) → **Eduardomcerqueira@gmail.com's Account**:

1. **Billing** → add a default payment method  
   https://dash.cloudflare.com/profile/billing
2. **Domain registration** → set default **registrant contact** and accept the registration agreement  
   https://dash.cloudflare.com/?to=/:account/domains/registrations
3. **API token** (if using scripts): **Account** → **Cloudflare Registrar** → **Edit**  
   Recreate or extend `CLOUDFLARE_API_TOKEN` in `.env`.

## Available names (checked via API)

| Domain | Register (USD/yr) | Notes |
|--------|---------------------|--------|
| **aialphasquad.com** | ~$10.46 | Recommended — clean, no hyphens |
| **aialphasquad.org** | ~$7.50 | Cheapest |
| **ai-alpha-squad.dev** | ~$12.20 | Matches GitHub repo name |
| **aialphasquad.dev** | ~$12.20 | Short `.dev` |
| alphasquad.dev | taken | — |

Re-check anytime:

```bash
chmod +x scripts/cf-domain-check.sh scripts/cf-domain-register.sh
./scripts/cf-domain-check.sh aialphasquad.com ai-alpha-squad.dev aialphasquad.org
```

## Option A — Dashboard (no API token changes)

1. Go to **Domain registration** → **Register domains**.
2. Search for e.g. `aialphasquad.com`.
3. Complete checkout (uses billing + registrant contact above).
4. The zone is added to this account automatically.

## Option B — API / script (after token has Registrar Edit)

```bash
./scripts/cf-domain-check.sh aialphasquad.com
CONFIRM_REGISTER=yes ./scripts/cf-domain-register.sh aialphasquad.com
```

Registration is **billable and non-refundable** once it succeeds.

## After the domain is active

1. In `.env`:

   ```bash
   SQUAD_DOMAIN=aialphasquad.com
   WHATSAPP_WEBHOOK_HOSTNAME=whatsapp-webhook.aialphasquad.com
   ```

2. Deploy webhook with custom domain:

   ```bash
   ./scripts/deploy-whatsapp-webhook.sh
   ./scripts/check-whatsapp-webhook-url.sh
   ```

3. Meta WhatsApp → **Callback URL:**  
   `https://whatsapp-webhook.aialphasquad.com/webhook`

## Account

Use only **Eduardomcerqueira@gmail.com's Account** (`3f44f51e37ea6bdeddef740bd381b452`). Bmhp is a separate project.
