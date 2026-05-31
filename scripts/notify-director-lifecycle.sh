#!/usr/bin/env bash
# Notify Director on WhatsApp for a squad lifecycle step.
# Usage: notify-director-lifecycle.sh <step> <issue_number> [owner/repo]
# Steps: new, awaiting-approval, director-approved, designed, implemented,
#        validation, release-candidate, released, blocked,
#        dispatched-business-owner, dispatched-architect,
#        inbound-approve, inbound-reject, inbound-changes, unauthorized-approval
set -euo pipefail

STEP="${1:?lifecycle step required}"
ISSUE="${2:?issue number required}"
REPO="${3:-${GITHUB_OWNER:-eduardocerqueira}/${SQUAD_WORK_QUEUE_REPO:-ai-alpha-squad}}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

for key in WHATSAPP_ACCESS_TOKEN WHATSAPP_PHONE_NUMBER_ID WHATSAPP_DIRECTOR_PHONE; do
  if [[ -z "${!key:-}" ]]; then
    echo "WhatsApp notify ($STEP): missing $key" >&2
    if [[ -n "${GITHUB_ACTIONS:-}" ]]; then
      echo "Run ./scripts/setup-squad-whatsapp-github.sh from a machine with .env configured." >&2
      exit 1
    fi
    exit 0
  fi
done

TITLE="$(gh issue view "$ISSUE" --repo "$REPO" --json title -q .title 2>/dev/null || echo "Issue #${ISSUE}")"

export STEP ISSUE TITLE REPO EXTRA="${4:-}"
python3 -c "
import os, sys
sys.path.insert(0, 'src')
from ai_alpha_squad.whatsapp.lifecycle import format_lifecycle_message
from ai_alpha_squad.whatsapp.send import send_text_message

step = os.environ['STEP']
issue = int(os.environ['ISSUE'])
repo = os.environ['REPO']
title = os.environ['TITLE']
extra = os.environ.get('EXTRA') or None
body = format_lifecycle_message(step, issue, title, repo=repo, extra=extra)
result = send_text_message(
    phone_number_id=os.environ['WHATSAPP_PHONE_NUMBER_ID'],
    access_token=os.environ['WHATSAPP_ACCESS_TOKEN'],
    to_phone=os.environ['WHATSAPP_DIRECTOR_PHONE'],
    body=body,
)
mid = result.get('messages', [{}])[0].get('id', '?')
print(f'Sent {step} for #{issue}. message_id: {mid}')
"
