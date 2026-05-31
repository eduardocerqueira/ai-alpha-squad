#!/usr/bin/env bash
# Dispatch Copilot cloud agent for a squad lifecycle label on an issue.
# Usage: squad-dispatch-copilot.sh <owner/repo> <issue_number> <lifecycle_label>
set -euo pipefail

REPO="${1:?repo required}"
ISSUE="${2:?issue number required}"
LABEL="${3:?lifecycle label required}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORMAT_COMMENT="${ROOT}/scripts/format-squad-comment.py"
export SQUAD_ICON_REPO="${SQUAD_ICON_REPO:-$REPO}"
export SQUAD_ICON_REF="${SQUAD_ICON_REF:-main}"

OWNER="${REPO%%/*}"
NAME="${REPO#*/}"

AGENT=""
INSTRUCTIONS=""

case "$LABEL" in
  new)
    AGENT="business-owner"
    INSTRUCTIONS="$(cat <<EOF
You are the Business Owner for AI Alpha Squad.

Read first: .agents/copilot-issue-first-delivery.md (issue-first — no planning PR).

1. Read .agents/agent-business-owner.md and .agents/templates/business-analysis-template.md
2. Complete Business Analysis for issue #${ISSUE} (read the issue body and comments)
3. Post the FULL report as an issue comment — heading must include: # Business Analysis
4. Add label awaiting-approval and remove label new
5. Comment on the issue: Squad deliverable complete on this issue.
6. Do NOT open a pull request on ai-alpha-squad. Do NOT commit BA-only files. Issue comment is the deliverable.

If a draft PR exists, close it after step 3–5.

After posting BA, the orchestrator will notify the Director on WhatsApp.
EOF
)"
    ;;
  director-approved|approved)
    AGENT="architect"
    INSTRUCTIONS="$(cat <<EOF
You are the Architect for AI Alpha Squad.

Read first: .agents/copilot-issue-first-delivery.md (issue-first — no planning PR).

1. Read .agents/agent-architect.md and Director-approved Business Analysis on issue #${ISSUE}
2. Write Technical Specification per .agents/templates/tech-spec-template.md
3. Post the FULL tech spec as an issue comment — heading must include: # Technical Specification
4. Create GitHub sub-issues (gh issue create) for Developer, QA, Security, DevOps, Tech Writer using .agents/templates/sub-issue-template.md — reference parent #${ISSUE} and target repo from the issue body
5. Map every FR-* requirement to BR-* from the BA
6. Add label designed and remove director-approved
7. Comment on the issue: Squad deliverable complete on this issue.
8. Do NOT open a pull request on ai-alpha-squad. Do NOT commit spec-only files. Issue comment + sub-issues are the deliverable.

If a draft PR exists, close it after steps 3–7.

Do NOT add director-approved or approved labels. Do NOT implement application code in product repos.
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
  if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
    echo "dispatched=false" >> "$GITHUB_OUTPUT"
  fi
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
  COMMENT_BODY="$(python3 "$FORMAT_COMMENT" dispatch "$AGENT" "$LABEL" --repo "$SQUAD_ICON_REPO" --ref "$SQUAD_ICON_REF")"
  gh issue comment "$ISSUE" --repo "$REPO" --body "$COMMENT_BODY"
  echo "Dispatched $AGENT on $REPO#$ISSUE"
  if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
    echo "dispatched=true" >> "$GITHUB_OUTPUT"
    echo "agent=$AGENT" >> "$GITHUB_OUTPUT"
  fi
  exit 0
fi

rm -f "$BODY_FILE"
echo "Copilot assign API failed — posting manual instructions"
INSTRUCTIONS_FILE="$(mktemp)"
printf '%s' "$INSTRUCTIONS" > "$INSTRUCTIONS_FILE"
COMMENT_BODY="$(python3 "$FORMAT_COMMENT" fallback "$AGENT" --instructions-file "$INSTRUCTIONS_FILE" --repo "$SQUAD_ICON_REPO" --ref "$SQUAD_ICON_REF")"
rm -f "$INSTRUCTIONS_FILE"
gh issue comment "$ISSUE" --repo "$REPO" --body "$COMMENT_BODY" \
  || echo "Could not post fallback comment (check token permissions)"
exit 0
