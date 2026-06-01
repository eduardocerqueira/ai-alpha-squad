#!/usr/bin/env bash
# When the Developer PR is merged, advance parent issue to implemented phase.
# Usage: squad-advance-implemented.sh <queue_repo> <parent_issue_number>
set -euo pipefail

REPO="${1:?queue repo required}"
PARENT="${2:?parent issue number required}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIND="${ROOT}/scripts/squad-find-subissues.py"
FORMAT_COMMENT="${ROOT}/scripts/format-squad-comment.py"

DEV_ISSUE="$("$FIND" --state all "$REPO" "$PARENT" developer 2>/dev/null)" || {
  echo "No developer sub-issue for parent #$PARENT"
  exit 0
}

ALREADY_IMPLEMENTED=0
if gh issue view "$PARENT" --repo "$REPO" --json labels -q '.labels[].name' | grep -qx 'implemented'; then
  ALREADY_IMPLEMENTED=1
  echo "Parent #$PARENT already has implemented label — checking validation dispatch and labels"
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

PR_STATE="$(gh pr view "$PR_NUM" --repo "$PR_REPO" --json state,mergedAt -q '.state')" || exit 0
PR_MERGED_AT="$(gh pr view "$PR_NUM" --repo "$PR_REPO" --json state,mergedAt -q '.mergedAt')" || true
if [[ "$PR_STATE" != "MERGED" ]] && [[ -z "$PR_MERGED_AT" || "$PR_MERGED_AT" == "null" ]]; then
  echo "PR $PR_URL not merged yet (state=$PR_STATE)"
  exit 0
fi

if [[ "$ALREADY_IMPLEMENTED" -eq 0 ]]; then
  gh issue edit "$PARENT" --repo "$REPO" --add-label "implemented" --remove-label "designed" || true
  BODY="$(python3 "$FORMAT_COMMENT" notice \
    --message "**Squad orchestrator:** Developer PR merged ($PR_URL). Parent advanced to \`implemented\` — validation agents dispatching." \
    --repo "$REPO")"
  gh issue comment "$PARENT" --repo "$REPO" --body "$BODY"
else
  gh issue edit "$PARENT" --repo "$REPO" --remove-label "designed" 2>/dev/null || true
fi

gh issue close "$DEV_ISSUE" --repo "$REPO" --comment "Developer deliverable merged: $PR_URL" 2>/dev/null || true

# Validation must dispatch even when implemented was set earlier (orchestrator only fires on label add).
# Do not call squad-phase-tick here — it invokes this script again and loops forever.
chmod +x "${ROOT}/scripts/squad-dispatch-validation.sh"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
for role in qa security devops tech-writer; do
  "${ROOT}/scripts/squad-dispatch-validation.sh" "$REPO" "$PARENT" "$role" || true
done

echo "Advanced parent #$PARENT to implemented (PR $PR_URL merged); validation dispatch attempted"
