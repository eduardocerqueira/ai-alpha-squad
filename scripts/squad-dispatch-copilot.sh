#!/usr/bin/env bash
# Dispatch Copilot cloud agent for a squad lifecycle label on an issue.
# Usage: squad-dispatch-copilot.sh <owner/repo> <issue_number> <lifecycle_label>
set -euo pipefail

REPO="${1:?repo required}"
ISSUE="${2:?issue number required}"
LABEL="${3:?lifecycle label required}"

OWNER="${REPO%%/*}"
NAME="${REPO#*/}"

AGENT=""
INSTRUCTIONS=""

case "$LABEL" in
  new)
    AGENT="business-owner"
    INSTRUCTIONS="$(cat <<EOF
You are the Business Owner for AI Alpha Squad.

1. Read .agents/agent-business-owner.md and .agents/templates/business-analysis-template.md
2. Complete Business Analysis for issue #${ISSUE} (read the issue body and comments)
3. Post the full report as an issue comment
4. Add label awaiting-approval and remove label new
5. Do NOT implement code. Do NOT open a PR on ai-alpha-squad for BA-only work.

After posting BA, the orchestrator will notify the Director on WhatsApp.
EOF
)"
    ;;
  approved)
    AGENT="architect"
    INSTRUCTIONS="$(cat <<EOF
You are the Architect for AI Alpha Squad.

1. Read .agents/agent-architect.md and approved Business Analysis on issue #${ISSUE}
2. Write Technical Specification per .agents/templates/tech-spec-template.md
3. Post tech spec on the issue; create sub-issues per .agents/templates/sub-issue-template.md
4. Map FR-* requirements to BR-* from the BA
5. Target implementation repo is named in the issue (e.g. eduardocerqueira/seeker) — sub-issues for Developer/QA/DevOps should reference it
6. When complete, add label designed and remove approved

Do NOT implement application code in product repos in this session.
EOF
)"
    ;;
  *)
    echo "No Copilot dispatch for label: $LABEL"
    exit 0
    ;;
esac

# Skip if Copilot already assigned
if gh issue view "$ISSUE" --repo "$REPO" --json assignees -q \
  '.assignees[].login' 2>/dev/null | grep -qiE '^(copilot|copilot-swe-agent\[bot\])$'; then
  echo "Copilot already assigned on #$ISSUE — skip"
  exit 0
fi

export REPO AGENT INSTRUCTIONS
export INSTRUCTIONS_JSON="$(python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))' <<<"$INSTRUCTIONS")"

BODY_FILE="$(mktemp)"
python3 -c "
import json, os
payload = {
  'assignees': ['copilot-swe-agent[bot]'],
  'agent_assignment': {
    'target_repo': os.environ['REPO'],
    'base_branch': 'main',
    'custom_agent': os.environ['AGENT'],
    'custom_instructions': json.loads(os.environ['INSTRUCTIONS_JSON']),
  },
}
print(json.dumps(payload))
" > "$BODY_FILE"

if gh api --method POST \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "/repos/${OWNER}/${NAME}/issues/${ISSUE}/assignees" \
  --input "$BODY_FILE" 2>/dev/null; then
  rm -f "$BODY_FILE"
  gh issue comment "$ISSUE" --repo "$REPO" --body "**Squad orchestrator** assigned Copilot agent \`${AGENT}\` for label \`${LABEL}\`."
  echo "Dispatched $AGENT on $REPO#$ISSUE"
  exit 0
fi

rm -f "$BODY_FILE"
echo "Copilot assign API failed — posting manual instructions"
gh issue comment "$ISSUE" --repo "$REPO" --body "$(cat <<EOF
**Squad orchestrator** could not auto-assign Copilot (check \`SQUAD_ORCHESTRATOR_TOKEN\` / Copilot agent API).

Please assign **Copilot** with custom agent **\`${AGENT}\`** on this issue.

\`\`\`
${INSTRUCTIONS}
\`\`\`
EOF
)" || echo "Could not post fallback comment (check token permissions)"
exit 0
