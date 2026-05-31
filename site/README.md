# AI Alpha Squad landing (`aialphasquad.com`)

Static site + contact API on Cloudflare Workers.

| Path | Purpose |
| ---- | ------- |
| `public/` | HTML, CSS, `assets/images/squad-flow.svg` |
| `src/index.ts` | `/api/contact`, Turnstile, Email Sending |
| `wrangler.jsonc` | Assets binding, `send_email` |

## Deploy

```bash
cp ../.env.example ../.env   # set CLOUDFLARE_*, TURNSTILE_*, SQUAD_DOMAIN
./scripts/verify-cloudflare-token.sh
./scripts/deploy-landing.sh
```

Contact inbox: `./scripts/setup-squad-email.sh` (requires zone email routing permissions).
