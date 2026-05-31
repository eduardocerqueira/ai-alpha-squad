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
  local msg="**Director gate:** \`director-approved\` recorded (${source}). Architect dispatch follows."
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
    approve | approved | yes | lgtm | "go" | "ship it" | "ok to release" | release) return 0 ;;
    *) return 1 ;;
  esac
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

  if ! classify_approve_comment "$body"; then
    echo "Director comment — not an approval phrase; skip"
    exit 0
  fi

  if ! has_label "awaiting-approval"; then
    echo "Director APPROVE comment but issue not awaiting-approval; skip"
    exit 0
  fi

  grant_director_approval "GitHub comment from \`${DIRECTOR}\`"
}

case "$MODE" in
  label) handle_label "$@" ;;
  comment) handle_comment "$@" ;;
  *)
    echo "Unknown mode: $MODE" >&2
    exit 1
    ;;
esac
