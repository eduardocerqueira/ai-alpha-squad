# AI Alpha Squad landing (`aialphasquad.com`)

The public face of the squad: the marketing landing page at [aialphasquad.com](https://aialphasquad.com) **and** the authenticated [Director Dashboard](https://aialphasquad.com/director/) — both served from one Cloudflare Worker. The landing page pitches the project and routes people to the three ways to reach the squad (GitHub Issues, REST API, WhatsApp); the dashboard is the live control room for the Director.

Static site + contact API + Director Dashboard on Cloudflare Workers.

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
