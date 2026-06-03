#!/usr/bin/env bash
# Enforce Director-only approval labels on squad issues.
# Usage:
#   director-gate.sh label <owner/repo> <issue_number> <label_name> <sender_login>
#   director-gate.sh comment <owner/repo> <issue_number> <comment_author> <comment_body>
set -euo pipefail

MODE="${1:?mode: label or comment}"
REPO="${2:?owner/repo required}"
ISSUE="${3:?issue number required}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORMAT_COMMENT="${ROOT}/scripts/format-squad-comment.py"
export SQUAD_ICON_REPO="${SQUAD_ICON_REPO:-$REPO}"
export SQUAD_ICON_REF="${SQUAD_ICON_REF:-main}"

DIRECTOR="${SQUAD_DIRECTOR_LOGIN:?SQUAD_DIRECTOR_LOGIN required}"
WHATSAPP_ACTOR="${SQUAD_WHATSAPP_APPROVAL_LOGIN:-$DIRECTOR}"
ACTIONS_BOT="${SQUAD_ACTIONS_APPROVAL_LOGIN:-github-actions[bot]}"

is_authorized_approver() {
  local login="$1"
  [[ "$login" == "$DIRECTOR" || "$login" == "$WHATSAPP_ACTOR" || "$login" == "$ACTIONS_BOT" ]]
}

issue_labels() {
  gh issue view "$ISSUE" --repo "$REPO" --json labels -q '.labels[].name'
}

has_label() {
  issue_labels | grep -qx "$1"
}

grant_director_approval() {
  local source="$1"
  gh issue edit "$ISSUE" --repo "$REPO" \
    --add-label "director-approved" \
    --remove-label "awaiting-approval" \
    --remove-label "approved" 2>/dev/null || true
  if ! has_label "director-approved"; then
    gh issue edit "$ISSUE" --repo "$REPO" --add-label "director-approved"
  fi
  local msg
  if [[ "${SQUAD_V2:-}" == "1" ]]; then
    msg="**Director gate:** \`director-approved\` recorded (${source}). Developer dispatch follows (Squad v2)."
  else
    msg="**Director gate:** \`director-approved\` recorded (${source}). Architect dispatch follows."
  fi
  local body
  body="$(python3 "$FORMAT_COMMENT" notice --message "$msg" --repo "$SQUAD_ICON_REPO" --ref "$SQUAD_ICON_REF")"
  gh issue comment "$ISSUE" --repo "$REPO" --body "$body"
}

revoke_label() {
  local label="$1"
  gh issue edit "$ISSUE" --repo "$REPO" --remove-label "$label" 2>/dev/null || true
}

post_unauthorized() {
  local label="$1"
  local sender="$2"
  local msg="**Director gate:** Unauthorized attempt to add \`${label}\` by \`${sender}\`. Only the Director may approve (GitHub login, WhatsApp, or \`./scripts/director-approve.sh\`)."
  local body
  body="$(python3 "$FORMAT_COMMENT" notice --message "$msg" --repo "$SQUAD_ICON_REPO" --ref "$SQUAD_ICON_REF")"
  gh issue comment "$ISSUE" --repo "$REPO" --body "$body"
  if [[ -x "${ROOT}/scripts/notify-director-lifecycle.sh" ]] && [[ -n "${WHATSAPP_ACCESS_TOKEN:-}" ]]; then
    "${ROOT}/scripts/notify-director-lifecycle.sh" unauthorized-approval "$ISSUE" "$REPO" \
      "Attempted label: ${label} by ${sender}." || true
  fi
}

classify_approve_comment() {
  local body="$1"
  local normalized
  normalized="$(printf '%s' "$body" | tr '[:upper:]' '[:lower:]' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
  case "$normalized" in
    approve | approved | yes | lgtm | "go" | "ship it" | "ok to release" | release | accept | accepted) return 0 ;;
    *) return 1 ;;
  esac
}

classify_reject_comment() {
  local body="$1"
  local normalized
  normalized="$(printf '%s' "$body" | tr '[:upper:]' '[:lower:]' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
  case "$normalized" in
    reject | rejected | no | decline | declined | "request changes" | changes) return 0 ;;
    *) return 1 ;;
  esac
}

reject_delivery() {
  local source="$1"
  local reason="${2:-}"
  export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
  local reject_body
  reject_body="$(python3 -c "
from ai_alpha_squad.squad_v2 import format_director_delivery_reject_comment, reset_comment
import sys
reason = sys.argv[1] if len(sys.argv) > 1 else ''
print(format_director_delivery_reject_comment(reason))
" "$reason")"
  gh issue comment "$ISSUE" --repo "$REPO" --body "$reject_body"
  gh issue edit "$ISSUE" --repo "$REPO" \
    --remove-label "release-candidate" \
    --add-label "director-approved" 2>/dev/null || true
  gh issue comment "$ISSUE" --repo "$REPO" --body "$(python3 -c "from ai_alpha_squad.squad_v2 import reset_comment; print(reset_comment('developer'))")"
  gh issue comment "$ISSUE" --repo "$REPO" --body "$(python3 -c "from ai_alpha_squad.squad_v2 import reset_comment; print(reset_comment('qa'))")"
  local msg="**Director gate:** Delivery rejected (${source}). Developer and QA will rework."
  local body
  body="$(python3 "$FORMAT_COMMENT" notice --message "$msg" --repo "$SQUAD_ICON_REPO" --ref "$SQUAD_ICON_REF")"
  gh issue comment "$ISSUE" --repo "$REPO" --body "$body"
  if [[ "${SQUAD_V2:-}" == "1" ]] && gh workflow run squad-v2-orchestrator.yml --repo "$REPO" \
    -f issue_number="$ISSUE" -f lifecycle_label="director-approved" 2>/dev/null; then
    echo "Triggered squad-v2-orchestrator for rework on #${ISSUE}"
  fi
}

accept_delivery() {
  local source="$1"
  gh issue edit "$ISSUE" --repo "$REPO" \
    --add-label "released" --remove-label "release-candidate" 2>/dev/null || true
  export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
  local accept_body
  accept_body="$(python3 -c "from ai_alpha_squad.squad_v2 import format_director_delivery_accept_comment; print(format_director_delivery_accept_comment())")"
  if gh issue view "$ISSUE" --repo "$REPO" --json state -q '.state' 2>/dev/null | grep -qi open; then
    gh issue close "$ISSUE" --repo "$REPO" --comment "$accept_body"
  else
    gh issue comment "$ISSUE" --repo "$REPO" --body "$accept_body"
  fi
  echo "Director delivery accepted (${source}) — #${ISSUE} released and closed"
}

handle_label() {
  local label="$4"
  local sender="$5"

  case "$label" in
    approved)
      if is_authorized_approver "$sender"; then
        grant_director_approval "legacy label \`approved\` from \`${sender}\`"
      else
        revoke_label "approved"
        post_unauthorized "approved" "$sender"
      fi
      ;;
    director-approved)
      if is_authorized_approver "$sender"; then
        echo "Authorized director-approved from ${sender}"
      else
        revoke_label "director-approved"
        post_unauthorized "director-approved" "$sender"
      fi
      ;;
    *)
      echo "Director gate: no action for label ${label}"
      ;;
  esac
}

handle_comment() {
  local author="$4"
  local body="$5"

  if [[ "$author" != "$DIRECTOR" ]]; then
    if classify_approve_comment "$body"; then
      local msg="**Director gate:** Ignored approval comment from \`${author}\`. Only \`${DIRECTOR}\` may approve on GitHub."
      local comment
      comment="$(python3 "$FORMAT_COMMENT" notice --message "$msg" --repo "$SQUAD_ICON_REPO" --ref "$SQUAD_ICON_REF")"
      gh issue comment "$ISSUE" --repo "$REPO" --body "$comment"
    fi
    exit 0
  fi

  if has_label "release-candidate"; then
    if classify_reject_comment "$body"; then
      reject_delivery "GitHub comment from \`${DIRECTOR}\`" "$body"
      exit 0
    fi
    if classify_approve_comment "$body"; then
      accept_delivery "GitHub comment from \`${DIRECTOR}\`"
      exit 0
    fi
    echo "Director comment on release-candidate — not accept/reject; skip"
    exit 0
  fi

  if ! classify_approve_comment "$body"; then
    echo "Director comment — not an approval phrase; skip"
    exit 0
  fi

  if has_label "awaiting-approval"; then
    grant_director_approval "GitHub comment from \`${DIRECTOR}\`"
  else
    echo "Director APPROVE comment but issue not awaiting-approval; skip"
  fi
}

case "$MODE" in
  label) handle_label "$@" ;;
  comment) handle_comment "$@" ;;
  *)
    echo "Unknown mode: $MODE" >&2
    exit 1
    ;;
esac
