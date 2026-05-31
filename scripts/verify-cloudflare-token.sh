#!/usr/bin/env bash
# Verify CLOUDFLARE_API_TOKEN can manage Workers, DNS, and Email for ai-alpha-squad.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [[ ! -f "$ROOT/.env" ]]; then
  echo "Missing $ROOT/.env"
  exit 1
fi
set -a
# shellcheck disable=SC1091
source "$ROOT/.env"
set +a

for key in CLOUDFLARE_API_TOKEN CLOUDFLARE_ACCOUNT_ID CLOUDFLARE_ZONE_ID SQUAD_DOMAIN; do
  if [[ -z "${!key:-}" ]]; then
    echo "Missing $key in .env"
    exit 1
  fi
done

API="https://api.cloudflare.com/client/v4"
AUTH=(-H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}")

check() {
  local name="$1" url="$2" method="${3:-GET}"
  local body
  if [[ "$method" == "POST" ]]; then
    body=$(curl -sS -X POST "$url" "${AUTH[@]}" -H "Content-Type: application/json" -d '{}')
  else
    body=$(curl -sS "$url" "${AUTH[@]}")
  fi
  local ok
  ok=$(echo "$body" | python3 -c "import sys,json; print(json.load(sys.stdin).get('success', False))")
  if [[ "$ok" == "True" ]]; then
    echo "  OK   $name"
    return 0
  fi
  local err
  err=$(echo "$body" | python3 -c "import sys,json; e=json.load(sys.stdin).get('errors',[{}])[0]; print(e.get('code','?'), e.get('message','?'))")
  echo "  FAIL $name ($err)"
  return 1
}

echo "Cloudflare API token check — ${SQUAD_DOMAIN}"
echo "Account: ${CLOUDFLARE_ACCOUNT_ID}"
echo "Zone:    ${CLOUDFLARE_ZONE_ID}"
echo ""

if [[ "${CLOUDFLARE_API_TOKEN}" == cfat_* ]]; then
  echo "Token type: Account API Token (cfat_…)"
  verify_url="${API}/accounts/${CLOUDFLARE_ACCOUNT_ID}/tokens/verify"
else
  echo "Token type: User API Token"
  verify_url="${API}/user/tokens/verify"
fi

fail=0
check "Token verify" "$verify_url" || fail=1
check "Account read" "${API}/accounts/${CLOUDFLARE_ACCOUNT_ID}" || fail=1
check "Zone read" "${API}/zones/${CLOUDFLARE_ZONE_ID}" || fail=1
check "DNS list (zone)" "${API}/zones/${CLOUDFLARE_ZONE_ID}/dns_records?per_page=1" || fail=1
check "Email routing addresses (account)" "${API}/accounts/${CLOUDFLARE_ACCOUNT_ID}/email/routing/addresses" || fail=1
check "Email routing rules (zone)" "${API}/zones/${CLOUDFLARE_ZONE_ID}/email/routing/rules" || fail=1
check "Email routing DNS (zone)" "${API}/zones/${CLOUDFLARE_ZONE_ID}/email/routing/dns" || fail=1

echo ""
if [[ $fail -eq 0 ]]; then
  echo "All checks passed. Run: ./scripts/setup-squad-email.sh"
  exit 0
fi

echo "Some checks failed."
echo ""
if [[ "${CLOUDFLARE_API_TOKEN}" == cfat_* ]]; then
  cat <<EOF
Account API Tokens need ZONE-scoped permissions for ${SQUAD_DOMAIN}, not only account-wide.

Edit the token:
  https://dash.cloudflare.com/${CLOUDFLARE_ACCOUNT_ID}/api-tokens

Add permissions for zone "${SQUAD_DOMAIN}" (or All zones):
  • Zone → DNS → Edit
  • Zone → Email Routing Rules → Edit
  • Account → Email Routing Addresses → Edit  (likely already OK)
  • Account → Email Sending → Edit            (contact form outbound)

Keep existing Workers permissions. Update CLOUDFLARE_API_TOKEN in .env if you recreate the token.

Then rerun:
  ./scripts/verify-cloudflare-token.sh
  ./scripts/setup-squad-email.sh
EOF
else
  echo "Add Email Routing + DNS + Email Sending permissions to the user API token, then rerun."
fi
exit 1
