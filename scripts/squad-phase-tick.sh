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

tick_parent() {
  local parent="$1"
  "$SYNC" "$REPO" "$parent" || true
  "$ADVANCE_DEV" "$REPO" "$parent" || true
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
