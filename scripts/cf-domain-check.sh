#!/usr/bin/env bash
# Check Cloudflare Registrar availability and pricing (up to 20 domains).
# Usage: ./scripts/cf-domain-check.sh domain1.dev domain2.com
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

if [[ -z "${CLOUDFLARE_ACCOUNT_ID:-}" || -z "${CLOUDFLARE_API_TOKEN:-}" ]]; then
  echo "Set CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN in .env"
  exit 1
fi

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <domain> [domain ...]"
  exit 1
fi

domains_json="$(python3 -c 'import json,sys; print(json.dumps(sys.argv[1:]))' "$@")"

curl -sS --request POST \
  "https://api.cloudflare.com/client/v4/accounts/${CLOUDFLARE_ACCOUNT_ID}/registrar/domain-check" \
  -H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}" \
  -H "Content-Type: application/json" \
  --data "{\"domains\": ${domains_json}}" \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
if not d.get('success'):
    print('API error:', d.get('errors'))
    sys.exit(1)
for x in d.get('result', {}).get('domains', []):
    name = x['name']
    if x.get('registrable'):
        p = x.get('pricing', {})
        print(f'{name:32} AVAILABLE  \${p.get(\"registration_cost\")}/yr register  \${p.get(\"renewal_cost\")}/yr renew')
    else:
        print(f'{name:32} not available  ({x.get(\"reason\", \"unknown\")})')
"
