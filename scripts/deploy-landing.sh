#!/usr/bin/env bash
# Deploy aialphasquad.com landing page (Workers static assets).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/site"

if [[ ! -f "$ROOT/.env" ]]; then
  echo "Missing $ROOT/.env — copy from .env.example first."
  exit 1
fi

set -a
# shellcheck disable=SC1091
source "$ROOT/.env"
set +a

if [[ -z "${CLOUDFLARE_ACCOUNT_ID:-}" ]]; then
  echo "Set CLOUDFLARE_ACCOUNT_ID in .env"
  exit 1
fi
export CLOUDFLARE_ACCOUNT_ID
# Optional separate token with Account → Workers Scripts → Edit
if [[ -n "${CLOUDFLARE_DEPLOY_TOKEN:-}" ]]; then
  export CLOUDFLARE_API_TOKEN="${CLOUDFLARE_DEPLOY_TOKEN}"
elif [[ -n "${CLOUDFLARE_API_TOKEN:-}" ]]; then
  export CLOUDFLARE_API_TOKEN
fi

cf_account_name() {
  curl -sS "https://api.cloudflare.com/client/v4/accounts/${CLOUDFLARE_ACCOUNT_ID}" \
    -H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}" \
    | python3 -c "
import sys, json
data = json.load(sys.stdin)
result = data.get('result')
if isinstance(result, dict) and result.get('name'):
    print(result['name'])
else:
    print('(zone-scoped token)')
"
}

ACCOUNT_NAME="$(cf_account_name)"
echo "Cloudflare target account: ${ACCOUNT_NAME} (${CLOUDFLARE_ACCOUNT_ID})"
if [[ -n "${CLOUDFLARE_EXPECT_ACCOUNT_NAME:-}" && "${ACCOUNT_NAME}" != "${CLOUDFLARE_EXPECT_ACCOUNT_NAME}" ]]; then
  echo "Refusing deploy: CLOUDFLARE_EXPECT_ACCOUNT_NAME=${CLOUDFLARE_EXPECT_ACCOUNT_NAME} does not match ${ACCOUNT_NAME}"
  exit 1
fi

python3 "$ROOT/scripts/embed-flow-diagram.py"
npm install

if [[ -n "${TURNSTILE_SECRET_KEY:-}" ]]; then
  if ! echo "$TURNSTILE_SECRET_KEY" | npx wrangler secret put TURNSTILE_SECRET_KEY 2>/dev/null; then
    echo "Warning: could not update TURNSTILE_SECRET_KEY (token needs Workers Scripts secrets or use existing secret)"
  fi
else
  echo "Warning: TURNSTILE_SECRET_KEY not set — contact form uses secret from prior deploy"
fi

DOMAIN="${SQUAD_DOMAIN:-}"
DEPLOY_ARGS=()
if [[ -n "${TURNSTILE_SITE_KEY:-}" ]]; then
  DEPLOY_ARGS+=(--var "TURNSTILE_SITE_KEY:${TURNSTILE_SITE_KEY}")
fi
if [[ -n "${CONTACT_TO_EMAIL:-}" ]]; then
  DEPLOY_ARGS+=(--var "CONTACT_TO_EMAIL:${CONTACT_TO_EMAIL}")
fi
if [[ -n "${CONTACT_FROM_EMAIL:-}" ]]; then
  DEPLOY_ARGS+=(--var "CONTACT_FROM_EMAIL:${CONTACT_FROM_EMAIL}")
fi
if [[ -n "$DOMAIN" ]]; then
  echo "Custom domain: ${DOMAIN} (+ www.${DOMAIN})"
  DEPLOY_ARGS+=(--domain "${DOMAIN}" --domain "www.${DOMAIN}")
else
  echo "SQUAD_DOMAIN not set — deploying to *.workers.dev only"
fi

if ! npm run deploy -- "${DEPLOY_ARGS[@]}"; then
  if [[ ${#DEPLOY_ARGS[@]} -gt 0 ]]; then
    echo ""
    echo "Custom domain attach failed (token may lack Workers Routes). Retrying without --domain …"
    npm run deploy
  else
    exit 1
  fi
fi

echo ""
if [[ -n "$DOMAIN" ]]; then
  echo "Landing page: https://${DOMAIN}/"
else
  echo "Set SQUAD_DOMAIN in .env and re-run to attach aialphasquad.com"
fi
