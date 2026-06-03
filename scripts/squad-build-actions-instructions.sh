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
if [[ "$AGENT" == "developer" && "${SQUAD_V2:-}" == "1" ]]; then
  PARENT_ISSUE="$ISSUE"
elif [[ "$AGENT" == "developer" ]]; then
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

if [[ "${SQUAD_V2:-}" == "1" ]]; then
  cat > "$OUT" <<EOF
You are the ${AGENT} agent for AI Alpha Squad v2 (single parent issue — no sub-issues).

Parent issue: https://github.com/${QUEUE_REPO}/issues/${PARENT_ISSUE}
Target repo: ${TARGET_REPO}

Read the parent issue body and \`# Business Analysis\` comment. Implement exactly what the Director requested on the target repo (not the queue repo).
Use one folder or file per language when applicable. Keep changes minimal.

1. Use the repository layout in context; go to the file the task or QA fix list names — do NOT
   crawl with repeated list_dir/read_file before your first edit_file.
2. For REWORK after \`squad-v2-qa:fail\`: fix BLOCKER items first (compile errors, missing files),
   one fix at a time with targeted edit_file (never rewrite whole files).
3. Run the build/compile command (mvn compile, etc.) via run_command; finish is rejected if compile fails.
4. Push to the stable branch; one PR per job (updates reuse the same PR)
5. Use finish only when the tree compiles and required artifacts exist
6. The workflow posts \`# Developer Deliverable\` on the parent issue when the PR is ready
7. Do NOT modify ${QUEUE_REPO} except via the separate deliverable comment step
8. Do NOT merge to main on the target repo

Agent profile: .agents/agent-${AGENT}.md
EOF
  if [[ "$AGENT" == "developer" ]]; then
    APPEND="$(python3 -c "
import json, subprocess, sys
sys.path.insert(0, '${ROOT}/src')
from ai_alpha_squad.squad_v2 import developer_instruction_appendix
repo, issue = sys.argv[1], int(sys.argv[2])
data = json.loads(subprocess.check_output(
    ['gh', 'issue', 'view', str(issue), '--repo', repo, '--json', 'comments'],
    text=True,
))
comments = tuple(data.get('comments') or ())
text = developer_instruction_appendix(comments)
if text.strip():
    print(text)
" "$QUEUE_REPO" "$PARENT_ISSUE" 2>/dev/null || true)"
    if [[ -n "${APPEND:-}" ]]; then
      printf '\n%s\n' "$APPEND" >> "$OUT"
    fi
  fi
else
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
fi

echo "$OUT"
