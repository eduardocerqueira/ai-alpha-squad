#!/usr/bin/env bash
# Enable Email Sending + Routing and create contact@ forwarding on SQUAD_DOMAIN.
#
# Prerequisites:
#   - Domain active on Cloudflare (SQUAD_DOMAIN in .env)
#   - CONTACT_EMAIL_FORWARD_TO = inbox that receives contact@ mail
#   - CLOUDFLARE_API_TOKEN with zone DNS + Email Routing Rules + account Email Addresses
#
# Usage:
#   ./scripts/verify-cloudflare-token.sh   # diagnose token first
#   ./scripts/setup-squad-email.sh
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

DOMAIN="${SQUAD_DOMAIN:-}"
FORWARD_TO="${CONTACT_EMAIL_FORWARD_TO:-}"
ZONE_ID="${CLOUDFLARE_ZONE_ID:-}"
ACCOUNT_ID="${CLOUDFLARE_ACCOUNT_ID:-}"

if [[ -z "$DOMAIN" || -z "$FORWARD_TO" || -z "$ZONE_ID" || -z "$ACCOUNT_ID" ]]; then
  echo "Set SQUAD_DOMAIN, CONTACT_EMAIL_FORWARD_TO, CLOUDFLARE_ZONE_ID, CLOUDFLARE_ACCOUNT_ID in .env"
  exit 1
fi

if [[ -z "${CLOUDFLARE_API_TOKEN:-}" ]]; then
  echo "Set CLOUDFLARE_API_TOKEN in .env"
  exit 1
fi

export CLOUDFLARE_ACCOUNT_ID
export CLOUDFLARE_API_TOKEN

API="https://api.cloudflare.com/client/v4"
AUTH=(-H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}" -H "Content-Type: application/json")

api_ok() {
  python3 -c "import sys,json; print(json.load(sys.stdin).get('success', False))"
}

api_err() {
  python3 -c "import sys,json; e=json.load(sys.stdin).get('errors',[{}])[0]; print(e.get('code','?'), '-', e.get('message','?'))"
}

CONTACT_ADDR="contact@${DOMAIN}"

echo "=== Preflight: ./scripts/verify-cloudflare-token.sh ==="
if ! "$ROOT/scripts/verify-cloudflare-token.sh" 2>/dev/null; then
  echo ""
  echo "Token missing zone permissions — fix token then rerun this script."
  exit 1
fi

echo ""
echo "=== Email Routing: enable ${DOMAIN} ==="
body=$(curl -sS -X POST "${API}/zones/${ZONE_ID}/email/routing/enable" "${AUTH[@]}" -d '{}')
if [[ $(echo "$body" | api_ok) != "True" ]]; then
  echo "  enable failed:" $(echo "$body" | api_err)
  exit 1
fi
echo "  enabled"

echo ""
echo "=== Email Routing: sync DNS (MX/TXT) ==="
body=$(curl -sS -X POST "${API}/zones/${ZONE_ID}/email/routing/dns" "${AUTH[@]}" -d '{}')
if [[ $(echo "$body" | api_ok) != "True" ]]; then
  echo "  dns sync failed:" $(echo "$body" | api_err)
  echo "  Add records manually in dashboard if needed."
else
  echo "  dns records requested"
fi

echo ""
echo "=== Destination: ${FORWARD_TO} ==="
body=$(curl -sS -X POST "${API}/accounts/${ACCOUNT_ID}/email/routing/addresses" \
  "${AUTH[@]}" -d "{\"email\":\"${FORWARD_TO}\"}")
if [[ $(echo "$body" | api_ok) != "True" ]]; then
  echo "  (already exists or pending verification)"
else
  echo "  created — check inbox to verify if new"
fi

echo ""
echo "=== Routing rule: ${CONTACT_ADDR} → ${FORWARD_TO} ==="
payload=$(CONTACT_ADDR="$CONTACT_ADDR" FORWARD_TO="$FORWARD_TO" python3 - <<'PY'
import json, os
print(json.dumps({
  "enabled": True,
  "name": "Contact forward",
  "matchers": [{"type": "literal", "field": "to", "value": os.environ["CONTACT_ADDR"]}],
  "actions": [{"type": "forward", "value": [os.environ["FORWARD_TO"]]}],
  "priority": 1,
}))
PY
)
body=$(curl -sS -X POST "${API}/zones/${ZONE_ID}/email/routing/rules" "${AUTH[@]}" -d "$payload")
if [[ $(echo "$body" | api_ok) != "True" ]]; then
  err=$(echo "$body" | api_err)
  if echo "$body" | grep -qi "already exists\|duplicate"; then
    echo "  rule already exists"
  else
    echo "  create failed: $err"
    exit 1
  fi
else
  echo "  rule created"
fi

echo ""
echo "=== Email Sending: enable ${DOMAIN} ==="
body=$(curl -sS -X POST "${API}/zones/${ZONE_ID}/email/sending/enable" "${AUTH[@]}" -d '{}')
if [[ $(echo "$body" | api_ok) != "True" ]]; then
  echo "  sending enable failed:" $(echo "$body" | api_err)
  echo "  Enable in dashboard: https://dash.cloudflare.com/${ACCOUNT_ID}/${DOMAIN}/email/sending"
else
  echo "  sending enabled"
fi

echo ""
echo "Done."
echo "  ${CONTACT_ADDR} → ${FORWARD_TO}"
echo "  Contact form → ${CONTACT_TO_EMAIL:-contact@${DOMAIN}} via Worker EMAIL binding"
echo "  Test: send email to ${CONTACT_ADDR} from an external mailbox"
