#!/usr/bin/env bash
# Poll open squad jobs and advance SDLC phases (dev merge, validation complete).
# Usage: squad-phase-tick.sh <queue_repo> [parent_issue_number]
set -euo pipefail

REPO="${1:?queue repo required}"
PARENT_FILTER="${2:-}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ADVANCE_DEV="${ROOT}/scripts/squad-advance-implemented.sh"
ADVANCE_VAL="${ROOT}/scripts/squad-advance-validation.sh"
NUDGE="${ROOT}/scripts/squad-nudge-stuck.sh"
SYNC="${ROOT}/scripts/squad-sync-planning-labels.sh"
VALIDATION="${ROOT}/scripts/squad-dispatch-validation.sh"

dispatch_missing_validation() {
  local parent="$1"
  if ! gh issue view "$parent" --repo "$REPO" --json labels -q '.labels[].name' | grep -qx 'implemented'; then
    return 0
  fi
  if gh issue view "$parent" --repo "$REPO" --json labels -q '.labels[].name' | grep -qx 'validation'; then
    return 0
  fi
  chmod +x "$VALIDATION" "${ROOT}/scripts/squad-dispatch-subissue.sh" "${ROOT}/scripts/squad-find-subissues.py"
  export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
  local role
  for role in qa security devops tech-writer; do
    "$VALIDATION" "$REPO" "$parent" "$role" || true
  done
}

tick_parent() {
  local parent="$1"
  "$SYNC" "$REPO" "$parent" || true
  "$ADVANCE_DEV" "$REPO" "$parent" || true
  dispatch_missing_validation "$parent" || true
  "$ADVANCE_VAL" "$REPO" "$parent" || true
}

if [[ -n "$PARENT_FILTER" ]]; then
  tick_parent "$PARENT_FILTER"
  chmod +x "$NUDGE" "$SYNC"
  "$NUDGE" "$REPO" "$PARENT_FILTER" || true
  exit 0
fi

for parent in $(gh issue list --repo "$REPO" --label designed --state open --json number -q '.[].number'); do
  [[ -n "$parent" ]] && tick_parent "$parent"
done

for parent in $(gh issue list --repo "$REPO" --label implemented --state open --json number -q '.[].number'); do
  [[ -n "$parent" ]] && tick_parent "$parent"
done

chmod +x "$NUDGE" "$SYNC"
"$NUDGE" "$REPO" || true

echo "Phase tick complete for $REPO"
