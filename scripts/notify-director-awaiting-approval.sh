#!/usr/bin/env bash
# Business Owner: notify Director on WhatsApp when an issue has awaiting-approval.
# Usage: ./scripts/notify-director-awaiting-approval.sh <issue_number> [summary sentence]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <issue_number> [summary]"
  exit 1
fi

ISSUE="$1"
SUMMARY="${2:-Business Analysis is ready for your review.}"

if [[ ! -f .env ]]; then
  echo "Missing .env"
  exit 1
fi
set -a
# shellcheck disable=SC1091
source .env
set +a

for key in WHATSAPP_ACCESS_TOKEN WHATSAPP_PHONE_NUMBER_ID WHATSAPP_DIRECTOR_PHONE; do
  if [[ -z "${!key:-}" ]]; then
    echo "Missing $key in .env"
    exit 1
  fi
done

REPO="${GITHUB_OWNER:-eduardocerqueira}/${SQUAD_WORK_QUEUE_REPO:-ai-alpha-squad}"
TITLE="$(gh issue view "$ISSUE" --repo "$REPO" --json title -q .title)"

export ISSUE TITLE SUMMARY
python3 -c "
import os, sys
sys.path.insert(0, 'src')
from ai_alpha_squad.whatsapp.send import format_business_analysis_ready, send_text_message

issue = int(os.environ['ISSUE'])
body = format_business_analysis_ready(
    issue,
    os.environ['TITLE'],
    summary=os.environ['SUMMARY'],
)
result = send_text_message(
    phone_number_id=os.environ['WHATSAPP_PHONE_NUMBER_ID'],
    access_token=os.environ['WHATSAPP_ACCESS_TOKEN'],
    to_phone=os.environ['WHATSAPP_DIRECTOR_PHONE'],
    body=body,
)
mid = result.get('messages', [{}])[0].get('id', '?')
print('Sent. message_id:', mid)
"
