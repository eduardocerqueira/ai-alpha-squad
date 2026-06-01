#!/usr/bin/env bash
# Close a parent squad job and its validation/developer sub-issues (Director stop / reset).
# Usage: squad-close-job.sh <queue_repo> <parent_issue_number> [reason]
set -euo pipefail

REPO="${1:?queue repo}"
PARENT="${2:?parent issue number}"
REASON="${3:-Director requested stop — see docs/retrospectives/ on ai-alpha-squad.}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIND="${ROOT}/scripts/squad-find-subissues.py"

COMMENT="$(cat <<EOF
**Squad orchestrator — job stopped**

${REASON}

Parent #${PARENT} and open sub-issues are being closed. Restart the job from a new parent issue after orchestration fixes on \`main\`.
EOF
)"

close_one() {
  local num="$1"
  if gh issue view "$num" --repo "$REPO" --json state -q '.state' 2>/dev/null | grep -qi open; then
    gh issue close "$num" --repo "$REPO" --comment "$COMMENT"
    echo "Closed #${num}"
  else
    echo "Skip #${num} (already closed)"
  fi
}

SUBS="$("$FIND" "$REPO" "$PARENT" 2>/dev/null || echo '{}')"
DEV="$("$FIND" --state all "$REPO" "$PARENT" developer 2>/dev/null || true)"
for num in $DEV $(echo "$SUBS" | python3 -c "import json,sys; d=json.load(sys.stdin); print(' '.join(str(v) for v in d.values()))" 2>/dev/null || true); do
  [[ -n "$num" ]] && close_one "$num"
done

close_one "$PARENT"
gh issue edit "$PARENT" --repo "$REPO" \
  --remove-label "validation,implemented,designed,awaiting-approval,release-candidate,new,director-approved" 2>/dev/null || true

echo "Job #${PARENT} closed on ${REPO}"
