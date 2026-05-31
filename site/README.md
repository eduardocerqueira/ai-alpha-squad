# AI Alpha Squad landing (`aialphasquad.com`)

Static site + contact API on Cloudflare Workers.

| Path | Purpose |
| ---- | ------- |
| `public/` | HTML, CSS, `robots.txt`, `sitemap.xml`, `llms.txt`, `assets/images/squad-flow.svg` |
| `VERSION` | Semver shown in page footers; patch auto-increments on each `./scripts/deploy-landing.sh` |
| `src/index.ts` | `/api/contact`, Turnstile, Email Sending |
| `wrangler.jsonc` | Assets binding, `send_email` |

## Deploy

```bash
cp ../.env.example ../.env   # set CLOUDFLARE_*, TURNSTILE_*, SQUAD_DOMAIN
./scripts/verify-cloudflare-token.sh
./scripts/deploy-landing.sh   # or: cd site && npm run deploy
```

`npm run deploy` runs `predeploy` first (version bump, flow diagram embed, sitemap). Footer semver is stored in `site/VERSION`.

Contact inbox: `./scripts/setup-squad-email.sh` (requires zone email routing permissions).
