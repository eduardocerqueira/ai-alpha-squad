#!/usr/bin/env bash
# Notify Director on WhatsApp for a squad lifecycle step (optional — never blocks the pipeline).
# Usage: notify-director-lifecycle.sh <step> <issue_number> [owner/repo] [extra]
# Steps: new, awaiting-approval, director-approved, designed, implemented,
#        validation, release-candidate, released, blocked,
#        dispatched-business-owner, dispatched-architect,
#        inbound-approve, inbound-reject, inbound-changes, unauthorized-approval
#
# Exit 0 always from CI when WhatsApp is disabled, misconfigured, or send fails.
# Set SQUAD_WHATSAPP_NOTIFY=0 (repo variable or env) to skip without attempting send.
# See https://github.com/eduardocerqueira/ideas/issues/1 (Meta migration — GitHub approval still works).
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

whatsapp_notify_enabled() {
  case "${SQUAD_WHATSAPP_NOTIFY:-auto}" in
    0 | false | False | FALSE | no | NO | off | OFF)
      return 1
      ;;
    1 | true | True | TRUE | yes | YES | on | ON)
      return 0
      ;;
    auto | "")
      for key in WHATSAPP_ACCESS_TOKEN WHATSAPP_PHONE_NUMBER_ID WHATSAPP_DIRECTOR_PHONE; do
        if [[ -z "${!key:-}" ]]; then
          return 1
        fi
      done
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

skip_notify() {
  local reason="$1"
  echo "WhatsApp notify ($STEP): skipped — ${reason}" >&2
  exit 0
}

if ! whatsapp_notify_enabled; then
  if [[ "${SQUAD_WHATSAPP_NOTIFY:-auto}" == "auto" ]]; then
    skip_notify "not configured (approve on GitHub issue; optional channel per ideas#1)"
  else
    skip_notify "SQUAD_WHATSAPP_NOTIFY disabled"
  fi
fi

for key in WHATSAPP_ACCESS_TOKEN WHATSAPP_PHONE_NUMBER_ID WHATSAPP_DIRECTOR_PHONE; do
  if [[ -z "${!key:-}" ]]; then
    skip_notify "missing ${key}"
  fi
done

TITLE="$(gh issue view "$ISSUE" --repo "$REPO" --json title -q .title 2>/dev/null || echo "Issue #${ISSUE}")"

export STEP ISSUE TITLE REPO EXTRA="${4:-}"
if ! python3 -c "
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
"; then
  skip_notify "send failed (pipeline continues; use GitHub issue for approvals)"
fi
