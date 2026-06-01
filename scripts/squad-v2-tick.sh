#!/usr/bin/env bash
# v2 phase watch: sync labels from deliverables, dispatch next agent, nudge stale runs.
# Usage: squad-v2-tick.sh <queue_repo> [issue_number]
set -euo pipefail

REPO="${1:?queue repo}"
ISSUE_FILTER="${2:-}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
export SQUAD_V2=1
DISPATCH="${ROOT}/scripts/squad-v2-dispatch.sh"
SYNC="${ROOT}/scripts/squad-sync-planning-labels.sh"

sync_labels() {
  local issue="$1"
  chmod +x "$SYNC" 2>/dev/null || true
  "$SYNC" "$REPO" "$issue" || true
  # v2: after developer deliverable, move to release-candidate
  if gh issue view "$issue" --repo "$REPO" --json labels,comments -q '.labels[].name' 2>/dev/null \
    | grep -qx 'director-approved'; then
    if gh issue view "$issue" --repo "$REPO" --json comments -q '.comments[].body' 2>/dev/null \
      | grep -qi '# developer deliverable'; then
      gh issue edit "$issue" --repo "$REPO" \
        --add-label "release-candidate" --remove-label "director-approved" 2>/dev/null || true
    fi
  fi
}

tick_issue() {
  local issue="$1"
  sync_labels "$issue"
  chmod +x "$DISPATCH"
  "$DISPATCH" "$REPO" "$issue" || true
}

if [[ -n "$ISSUE_FILTER" ]]; then
  tick_issue "$ISSUE_FILTER"
  exit 0
fi

for issue in $(gh issue list --repo "$REPO" --state open --json number,labels \
  -q '.[] | select([.labels[].name] | any(. == "new" or . == "director-approved" or . == "awaiting-approval" or . == "release-candidate")) | .number'); do
  [[ -n "$issue" ]] && tick_issue "$issue"
done

echo "v2 phase tick complete for $REPO"
