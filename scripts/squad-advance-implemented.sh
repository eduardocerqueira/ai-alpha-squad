#!/usr/bin/env bash
# When the Developer PR is merged, advance parent issue to implemented phase.
# Usage: squad-advance-implemented.sh <queue_repo> <parent_issue_number>
set -euo pipefail

REPO="${1:?queue repo required}"
PARENT="${2:?parent issue number required}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIND="${ROOT}/scripts/squad-find-subissues.py"
FORMAT_COMMENT="${ROOT}/scripts/format-squad-comment.py"

DEV_ISSUE="$("$FIND" "$REPO" "$PARENT" developer)" || {
  echo "No open developer sub-issue for parent #$PARENT"
  exit 0
}

if gh issue view "$PARENT" --repo "$REPO" --json labels -q '.labels[].name' | grep -qx 'implemented'; then
  echo "Parent #$PARENT already has implemented label"
  exit 0
fi

TARGET_REPO="$("$FIND" "$REPO" "$PARENT" --target-repo)" || TARGET_REPO=""

PR_URL="$(gh issue view "$DEV_ISSUE" --repo "$REPO" --json comments,body -q \
  '[.body] + [.comments[].body] | join("\n")' \
  | grep -Eo 'https://github.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/pull/[0-9]+' \
  | head -1)"

if [[ -z "$PR_URL" ]]; then
  echo "No PR URL found on developer sub-issue #$DEV_ISSUE"
  exit 0
fi

PR_REPO="${PR_URL#https://github.com/}"
PR_REPO="${PR_REPO%/pull/*}"
PR_NUM="${PR_URL##*/pull/}"

MERGED="$(gh pr view "$PR_NUM" --repo "$PR_REPO" --json merged,state -q '.merged')" || exit 0
if [[ "$MERGED" != "true" ]]; then
  echo "PR $PR_URL not merged yet (state check)"
  exit 0
fi

gh issue edit "$PARENT" --repo "$REPO" --add-label "implemented" --remove-label "designed" || true
gh issue close "$DEV_ISSUE" --repo "$REPO" --comment "Developer deliverable merged: $PR_URL" || true

BODY="$(python3 "$FORMAT_COMMENT" notice \
  --message "**Squad orchestrator:** Developer PR merged ($PR_URL). Parent advanced to \`implemented\` — validation agents dispatching." \
  --repo "$REPO")"
gh issue comment "$PARENT" --repo "$REPO" --body "$BODY"

echo "Advanced parent #$PARENT to implemented (PR $PR_URL merged)"
