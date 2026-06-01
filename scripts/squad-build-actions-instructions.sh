#!/usr/bin/env bash
# Build instructions file for Squad Actions agent (developer / devops).
# Usage: squad-build-actions-instructions.sh <queue_repo> <issue> <agent> <target_repo>
set -euo pipefail

QUEUE_REPO="${1:?queue repo}"
ISSUE="${2:?issue}"
AGENT="${3:?agent}"
TARGET_REPO="${4:?target repo}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIND="${ROOT}/scripts/squad-find-subissues.py"
OUT="$(mktemp)"

PARENT_ISSUE="$ISSUE"
if [[ "$AGENT" == "developer" ]]; then
  if ! gh issue view "$ISSUE" --repo "$QUEUE_REPO" --json labels -q '.labels[].name' 2>/dev/null | grep -qx 'developer'; then
    PARENT_ISSUE="$ISSUE"
    ISSUE="$("$FIND" "$QUEUE_REPO" "$PARENT_ISSUE" developer)" || {
      echo "No developer sub-issue for parent #$PARENT_ISSUE" >&2
      exit 1
    }
  else
    PARENT_ISSUE="$(gh issue view "$ISSUE" --repo "$QUEUE_REPO" --json body -q .body \
      | grep -Eo 'issues/[0-9]+' | head -1 | cut -d/ -f2)"
    PARENT_ISSUE="${PARENT_ISSUE:-$ISSUE}"
  fi
fi

cat > "$OUT" <<EOF
You are the ${AGENT} agent for AI Alpha Squad — implementation runs on the target product repo.

Queue repo issue: https://github.com/${QUEUE_REPO}/issues/${ISSUE}
Parent (if sub-issue): https://github.com/${QUEUE_REPO}/issues/${PARENT_ISSUE}

Read Technical Specification on the parent issue (heading "# Technical Specification").
Target repo: ${TARGET_REPO}

1. Implement per the tech spec on branch \`main\`
2. Add or extend tests; run test/lint commands when available
3. Use the finish tool when implementation is ready for PR
4. Do NOT modify the ai-alpha-squad queue repo
5. Do NOT merge to main

Agent profile: .agents/agent-${AGENT}.md on the queue repo.
EOF

echo "$OUT"
