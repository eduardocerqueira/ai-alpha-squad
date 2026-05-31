#!/usr/bin/env bash
# Test HTTPS reachability for the WhatsApp webhook (workers.dev or custom domain).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

if [[ -n "${WHATSAPP_WEBHOOK_HOSTNAME:-}" ]]; then
  BASE="https://${WHATSAPP_WEBHOOK_HOSTNAME}"
else
  SUBDOMAIN="${WORKERS_DEV_SUBDOMAIN:-eduardomcerqueira}"
  WORKER_NAME="${WORKER_NAME:-ai-alpha-squad-whatsapp-webhook}"
  BASE="https://${WORKER_NAME}.${SUBDOMAIN}.workers.dev"
fi

URL="${BASE}/webhook"
ROOT_URL="${BASE}/"

echo "Testing: ${ROOT_URL}"
if curl -fsS --max-time 15 "${ROOT_URL}" >/dev/null 2>&1; then
  echo "OK — HTTPS works. Meta callback URL: ${URL}"
  exit 0
fi

echo "FAIL — TLS/HTTP error (custom domain cert may take a few minutes after first deploy)."
echo ""
echo "Fix options:"
echo "  1. Wait 5–15 minutes, then re-run: ./scripts/check-whatsapp-webhook-url.sh"
echo "  2. Cloudflare dashboard → SSL/TLS → Edge Certificates (hostname should show Active)"
echo "  3. See docs/whatsapp-webhook-hostname.md"
exit 1
