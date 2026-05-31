#!/usr/bin/env bash
# Return 0 if sender may set director-approved; 1 otherwise.
# Usage: director-gate-is-authorized.sh <sender_login>
set -euo pipefail

SENDER="${1:?sender login required}"
DIRECTOR="${SQUAD_DIRECTOR_LOGIN:?SQUAD_DIRECTOR_LOGIN required}"
WHATSAPP_ACTOR="${SQUAD_WHATSAPP_APPROVAL_LOGIN:-$DIRECTOR}"
ACTIONS_BOT="${SQUAD_ACTIONS_APPROVAL_LOGIN:-github-actions[bot]}"

if [[ "$SENDER" == "$DIRECTOR" || "$SENDER" == "$WHATSAPP_ACTOR" || "$SENDER" == "$ACTIONS_BOT" ]]; then
  exit 0
fi
exit 1
