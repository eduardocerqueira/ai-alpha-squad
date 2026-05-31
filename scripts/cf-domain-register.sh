#!/usr/bin/env bash
# Register a domain on Cloudflare Registrar (BILLABLE — non-refundable after success).
#
# Prerequisites (dashboard, same account as CLOUDFLARE_ACCOUNT_ID):
#   - Billing → default payment method
#   - Domain registration → default registrant contact + agreement accepted
#   - API token with Account → Cloudflare Registrar → Edit
#
# Usage:
#   ./scripts/cf-domain-check.sh aialphasquad.com
#   CONFIRM_REGISTER=yes ./scripts/cf-domain-register.sh aialphasquad.com
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [[ "${CONFIRM_REGISTER:-}" != "yes" ]]; then
  echo "Refusing to charge your account without CONFIRM_REGISTER=yes"
  echo "Example:"
  echo "  ./scripts/cf-domain-check.sh aialphasquad.com"
  echo "  CONFIRM_REGISTER=yes ./scripts/cf-domain-register.sh aialphasquad.com"
  exit 1
fi

if [[ $# -ne 1 ]]; then
  echo "Usage: CONFIRM_REGISTER=yes $0 <fqdn>"
  exit 1
fi

DOMAIN="$1"
"$ROOT/scripts/cf-domain-check.sh" "$DOMAIN" | rg -q "AVAILABLE" || {
  echo "Domain not available for registration: $DOMAIN"
  exit 1
}

if [[ ! -f "$ROOT/.env" ]]; then
  echo "Missing $ROOT/.env"
  exit 1
fi
set -a
# shellcheck disable=SC1091
source "$ROOT/.env"
set +a

echo "Registering ${DOMAIN} on account ${CLOUDFLARE_ACCOUNT_ID} ..."
response="$(curl -sS --request POST \
  "https://api.cloudflare.com/client/v4/accounts/${CLOUDFLARE_ACCOUNT_ID}/registrar/registrations" \
  -H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}" \
  -H "Content-Type: application/json" \
  --data "{\"domain_name\": \"${DOMAIN}\"}")"

echo "$response" | python3 -c "
import sys, json
d = json.load(sys.stdin)
if not d.get('success'):
    print('Registration failed:', json.dumps(d.get('errors'), indent=2))
    sys.exit(1)
r = d.get('result', {})
print('state:', r.get('state'))
print('completed:', r.get('completed'))
print('domain:', r.get('domain_name'))
if r.get('context', {}).get('registration'):
    reg = r['context']['registration']
    print('expires_at:', reg.get('expires_at'))
"

echo ""
echo "Next: set in .env"
echo "  SQUAD_DOMAIN=${DOMAIN}"
echo "  WHATSAPP_WEBHOOK_HOSTNAME=whatsapp-webhook.${DOMAIN}"
echo "Then: ./scripts/deploy-whatsapp-webhook.sh"
