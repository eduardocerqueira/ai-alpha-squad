#!/usr/bin/env bash
# Sync WhatsApp credentials from .env to GitHub repo secrets/variables for Actions.
#
# Usage:
#   ./scripts/setup-squad-whatsapp-github.sh [owner/repo]
#
# Requires: gh auth, WHATSAPP_* in .env (see docs/whatsapp-setup.md)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO="${1:-${GITHUB_OWNER:-eduardocerqueira}/${SQUAD_WORK_QUEUE_REPO:-ai-alpha-squad}}"

if [[ ! -f "$ROOT/.env" ]]; then
  echo "Missing $ROOT/.env — copy from .env.example first."
  exit 1
fi

set -a
# shellcheck disable=SC1091
source "$ROOT/.env"
set +a

missing=()
for key in WHATSAPP_ACCESS_TOKEN WHATSAPP_PHONE_NUMBER_ID WHATSAPP_DIRECTOR_PHONE; do
  if [[ -z "${!key:-}" ]]; then
    missing+=("$key")
  fi
done

if ((${#missing[@]})); then
  echo "Missing in .env: ${missing[*]}"
  echo "See docs/whatsapp-setup.md"
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "Run: gh auth login"
  exit 1
fi

echo "Validating WhatsApp access token against Graph API..."
token_check="$(curl -sS "https://graph.facebook.com/v21.0/${WHATSAPP_PHONE_NUMBER_ID}" \
  -H "Authorization: Bearer ${WHATSAPP_ACCESS_TOKEN}")"
if ! python3 -c "
import json, sys
data = json.loads(sys.argv[1])
if data.get('id'):
    sys.exit(0)
msg = data.get('error', {}).get('message', 'unknown error')
print(msg, file=sys.stderr)
sys.exit(1)
" "$token_check"; then
  echo ""
  echo "Token invalid or expired. Regenerate in Meta Business → System User → permanent token,"
  echo "update WHATSAPP_ACCESS_TOKEN in .env, then rerun this script."
  exit 1
fi
echo "Token OK."

echo "Syncing WhatsApp credentials to $REPO (values not printed)..."

gh secret set WHATSAPP_ACCESS_TOKEN --repo "$REPO" --body "$WHATSAPP_ACCESS_TOKEN"
gh secret set WHATSAPP_PHONE_NUMBER_ID --repo "$REPO" --body "$WHATSAPP_PHONE_NUMBER_ID"

if [[ -n "${WHATSAPP_WEBHOOK_VERIFY_TOKEN:-}" ]]; then
  gh secret set WHATSAPP_WEBHOOK_VERIFY_TOKEN --repo "$REPO" --body "$WHATSAPP_WEBHOOK_VERIFY_TOKEN"
fi

gh variable set WHATSAPP_DIRECTOR_PHONE --repo "$REPO" --body "$WHATSAPP_DIRECTOR_PHONE"

echo "Done."
echo "  secrets: WHATSAPP_ACCESS_TOKEN, WHATSAPP_PHONE_NUMBER_ID${WHATSAPP_WEBHOOK_VERIFY_TOKEN:+, WHATSAPP_WEBHOOK_VERIFY_TOKEN}"
echo "  variable: WHATSAPP_DIRECTOR_PHONE"
echo ""
echo "Verify: gh secret list --repo $REPO && gh variable list --repo $REPO"
