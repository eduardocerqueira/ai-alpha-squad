#!/usr/bin/env bash
# When all validation sub-issues deliver, advance parent to validation phase.
# Usage: squad-advance-validation.sh <queue_repo> <parent_issue_number>
set -euo pipefail

REPO="${1:?queue repo required}"
PARENT="${2:?parent issue number required}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIND="${ROOT}/scripts/squad-find-subissues.py"
FORMAT_COMMENT="${ROOT}/scripts/format-squad-comment.py"

if gh issue view "$PARENT" --repo "$REPO" --json labels -q '.labels[].name' | grep -qx 'validation'; then
  echo "Parent #$PARENT already in validation phase"
  exit 0
fi

if ! gh issue view "$PARENT" --repo "$REPO" --json labels -q '.labels[].name' | grep -qx 'implemented'; then
  echo "Parent #$PARENT not in implemented phase — skip"
  exit 0
fi

if ! python3 "$FIND" "$REPO" "$PARENT" --validation-complete; then
  STATUS="$(python3 "$FIND" "$REPO" "$PARENT" --validation-status)"
  echo "Validation not complete for parent #$PARENT: $STATUS"
  exit 0
fi

gh issue edit "$PARENT" --repo "$REPO" --add-label "validation" --remove-label "implemented" || true

BODY="$(python3 "$FORMAT_COMMENT" notice \
  --message "**Squad orchestrator:** All validation deliverables received. Parent advanced to \`validation\` — Release Manager dispatching." \
  --repo "$REPO")"
gh issue comment "$PARENT" --repo "$REPO" --body "$BODY"

echo "Advanced parent #$PARENT to validation"
