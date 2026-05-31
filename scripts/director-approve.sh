#!/usr/bin/env bash
# Director CLI: approve an issue awaiting Business Analysis review.
# Usage: ./scripts/director-approve.sh <issue_number> [owner/repo]
# Requires: gh auth as SQUAD_DIRECTOR_LOGIN (or repo owner).
set -euo pipefail

ISSUE="${1:?issue number required}"
REPO="${2:-${GITHUB_OWNER:-eduardocerqueira}/${SQUAD_WORK_QUEUE_REPO:-ai-alpha-squad}}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "${ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ROOT}/.env"
  set +a
fi

DIRECTOR="${SQUAD_DIRECTOR_LOGIN:-${GITHUB_DIRECTOR_LOGIN:-eduardocerqueira}}"
ME="$(gh api user -q .login 2>/dev/null || true)"
if [[ -n "$ME" && "$ME" != "$DIRECTOR" ]]; then
  echo "Warning: gh auth user is ${ME}, expected SQUAD_DIRECTOR_LOGIN=${DIRECTOR}" >&2
fi

if ! gh issue view "$ISSUE" --repo "$REPO" --json labels -q '.labels[].name' | grep -qx 'awaiting-approval'; then
  echo "Issue #${ISSUE} is not in awaiting-approval — add label manually or wait for Business Owner." >&2
  exit 1
fi

export SQUAD_DIRECTOR_LOGIN="$DIRECTOR"
export SQUAD_WHATSAPP_APPROVAL_LOGIN="${SQUAD_WHATSAPP_APPROVAL_LOGIN:-$DIRECTOR}"
chmod +x "${ROOT}/scripts/director-gate.sh"
"${ROOT}/scripts/director-gate.sh" comment "$REPO" "$ISSUE" "$DIRECTOR" "APPROVE"

echo "Director approval recorded on ${REPO}#${ISSUE}"
