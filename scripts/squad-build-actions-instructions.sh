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

Parent issue #${PARENT_ISSUE} contains the Technical Specification and Business Analysis (included in agent context).
Target repo: ${TARGET_REPO} — may only have README.md; scaffold the VS Code extension from scratch.

1. list_dir first, then write_file for package.json, tsconfig.json, src/extension.ts, etc.
2. Implement per the tech spec on branch \`main\`
3. Add or extend tests; run test/lint commands when available
4. Use the finish tool when implementation is ready for PR
5. Do NOT modify the ai-alpha-squad queue repo
6. Do NOT merge to main

Agent profile: .agents/agent-${AGENT}.md on the queue repo.
EOF

echo "$OUT"
