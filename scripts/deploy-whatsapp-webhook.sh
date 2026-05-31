#!/usr/bin/env bash
# Deploy WhatsApp webhook Worker using secrets from repo-root .env
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/workers/whatsapp-webhook"

if [[ ! -f "$ROOT/.env" ]]; then
  echo "Missing $ROOT/.env — copy from .env.example first."
  exit 1
fi

set -a
# shellcheck disable=SC1091
source "$ROOT/.env"
set +a

if [[ -z "${CLOUDFLARE_ACCOUNT_ID:-}" ]]; then
  echo "Set CLOUDFLARE_ACCOUNT_ID in .env to the Cloudflare account that should host this Worker."
  exit 1
fi
export CLOUDFLARE_ACCOUNT_ID
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

for key in WHATSAPP_WEBHOOK_VERIFY_TOKEN WHATSAPP_DIRECTOR_PHONE GITHUB_TOKEN; do
  if [[ -z "${!key:-}" ]]; then
    echo "Missing $key in .env"
    exit 1
  fi
done

npm install
echo "$WHATSAPP_WEBHOOK_VERIFY_TOKEN" | npx wrangler secret put WHATSAPP_WEBHOOK_VERIFY_TOKEN
echo "$WHATSAPP_DIRECTOR_PHONE" | npx wrangler secret put WHATSAPP_DIRECTOR_PHONE
echo "$GITHUB_TOKEN" | npx wrangler secret put GITHUB_TOKEN
if [[ -n "${WHATSAPP_APP_SECRET:-}" ]]; then
  echo "$WHATSAPP_APP_SECRET" | npx wrangler secret put WHATSAPP_APP_SECRET
fi

if [[ -n "${WHATSAPP_WEBHOOK_HOSTNAME:-}" ]]; then
  echo "Custom domain: ${WHATSAPP_WEBHOOK_HOSTNAME}"
  npm run deploy -- --domain "${WHATSAPP_WEBHOOK_HOSTNAME}"
else
  npm run deploy
fi

echo ""
if [[ -n "${WHATSAPP_WEBHOOK_HOSTNAME:-}" ]]; then
  echo "Meta webhook Callback URL: https://${WHATSAPP_WEBHOOK_HOSTNAME}/webhook"
else
  echo "Configure Meta webhook Callback URL (append /webhook to the URL wrangler printed above)"
fi
echo "Verify token: same as WHATSAPP_WEBHOOK_VERIFY_TOKEN in .env"
if [[ -z "${WHATSAPP_APP_SECRET:-}" ]]; then
  echo "Warning: WHATSAPP_APP_SECRET not set — POST webhooks will not verify X-Hub-Signature-256"
fi

if [[ -x "$ROOT/scripts/check-whatsapp-webhook-url.sh" ]]; then
  echo ""
  "$ROOT/scripts/check-whatsapp-webhook-url.sh" || true
fi
