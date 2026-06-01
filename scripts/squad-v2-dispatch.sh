#!/usr/bin/env bash
# Dispatch the next v2 agent on a single parent issue (sequential, HF + Actions for dev).
# Usage: squad-v2-dispatch.sh <queue_repo> <issue_number>
set -euo pipefail

REPO="${1:?queue repo}"
ISSUE="${2:?issue number}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
export SQUAD_V2=1

FORMAT="${ROOT}/scripts/format-squad-comment.py"
DISPATCH="${ROOT}/scripts/squad-dispatch-subissue.sh"

ACTION="$(python3 -c "
from ai_alpha_squad.squad_v2 import IssueView, next_action
import json, subprocess, sys

repo, issue = sys.argv[1], int(sys.argv[2])
data = json.loads(subprocess.check_output(
    ['gh', 'issue', 'view', str(issue), '--repo', repo,
     '--json', 'state,labels,body,comments'],
    text=True,
))
labels = frozenset(x['name'] for x in data.get('labels') or [])
comments = tuple(data.get('comments') or [])
view = IssueView(issue, data.get('state') or 'OPEN', labels, comments, data.get('body') or '')
act = next_action(view)
print(act.kind)
print(act.agent or '')
print(act.reason)
" "$REPO" "$ISSUE")"

KIND="$(echo "$ACTION" | sed -n '1p')"
AGENT="$(echo "$ACTION" | sed -n '2p')"
REASON="$(echo "$ACTION" | sed -n '3,$p' | head -1)"

echo "v2 #$ISSUE: kind=$KIND agent=$AGENT — $REASON"

case "$KIND" in
  dispatch) ;;
  gate|done|idle)
    exit 0
    ;;
  failed)
    BODY="$(python3 "$FORMAT" notice --message "**Squad v2:** $REASON" --repo "$REPO")"
    gh issue comment "$ISSUE" --repo "$REPO" --body "$BODY"
    gh issue edit "$ISSUE" --repo "$REPO" --add-label "blocked" 2>/dev/null || true
    exit 1
    ;;
  *)
    exit 0
    ;;
esac

TARGET="$(python3 -c "
import json, subprocess, sys
from ai_alpha_squad.squad_v2 import extract_target_repo
repo, issue = sys.argv[1], sys.argv[2]
body = subprocess.check_output(
    ['gh', 'issue', 'view', issue, '--repo', repo, '--json', 'body', '-q', '.body'],
    text=True,
)
print(extract_target_repo(body) or repo)
" "$REPO" "$ISSUE")"

MARKER="$(python3 -c "from ai_alpha_squad.squad_v2 import in_progress_comment; print(in_progress_comment('$AGENT'))")"
gh issue comment "$ISSUE" --repo "$REPO" --body "$MARKER"

INSTRUCTIONS="$(mktemp)"
case "$AGENT" in
  business-owner)
    cat > "$INSTRUCTIONS" <<EOF
You are the Business Owner for AI Alpha Squad (v2 — single issue, no sub-issues).

Read .agents/agent-business-owner.md and .agents/templates/business-analysis-template.md

Issue: https://github.com/${REPO}/issues/${ISSUE}
Target repo (for context): ${TARGET}

1. Post the full Business Analysis on THIS issue (#${ISSUE}) — heading must include: # Business Analysis
2. Do not open sub-issues. Do not open PRs on ${REPO}.
3. When complete, the orchestrator will add label awaiting-approval.
EOF
    ;;
  developer)
    cat > "$INSTRUCTIONS" <<EOF
You are the Developer for AI Alpha Squad (v2 — single issue, no sub-issues).

Read .agents/agent-developer.md. Target repo: ${TARGET}

Issue: https://github.com/${REPO}/issues/${ISSUE}

1. Implement on ${TARGET} (branch + PR)
2. Post on THIS issue (#${ISSUE}) — heading must include: # Developer Deliverable
   Include the PR URL and summary of changes.
3. Do not create sub-issues. Do not post validation reports — v2 has only BO + Developer.
EOF
    ;;
  *)
    echo "Unknown agent: $AGENT" >&2
    exit 1
    ;;
esac

export SQUAD_AI_PROVIDER=huggingface
export SQUAD_CODE_RUNTIME=actions
if ! "$DISPATCH" "$REPO" "$ISSUE" "$AGENT" "$TARGET" "$INSTRUCTIONS"; then
  ERR="dispatch failed for ${AGENT}"
  FAIL="$(python3 -c "from ai_alpha_squad.squad_v2 import failed_comment; print(failed_comment('$AGENT', '''$ERR'''))")"
  gh issue comment "$ISSUE" --repo "$REPO" --body "$FAIL"
  exit 1
fi

rm -f "$INSTRUCTIONS"
echo "Dispatched $AGENT on #$ISSUE"
