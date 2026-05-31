#!/usr/bin/env bash
# Assign Copilot custom agent to a single issue/sub-issue.
# Usage: squad-dispatch-subissue.sh <queue_repo> <issue_number> <agent> <target_repo> [instructions_file]
set -euo pipefail

REPO="${1:?queue repo required}"
ISSUE="${2:?issue number required}"
AGENT="${3:?agent slug required}"
TARGET_REPO="${4:?target repo required}"
INSTRUCTIONS_FILE="${5:-}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORMAT_COMMENT="${ROOT}/scripts/format-squad-comment.py"
export SQUAD_ICON_REPO="${SQUAD_ICON_REPO:-$REPO}"
export SQUAD_ICON_REF="${SQUAD_ICON_REF:-main}"

OWNER="${REPO%%/*}"
NAME="${REPO#*/}"

if [[ -z "$INSTRUCTIONS_FILE" ]]; then
  echo "instructions file required"
  exit 1
fi

INSTRUCTIONS="$(cat "$INSTRUCTIONS_FILE")"

if gh issue view "$ISSUE" --repo "$REPO" --json assignees -q \
  '.assignees[].login' 2>/dev/null | grep -qiE '^(copilot|copilot-swe-agent\[bot\])$'; then
  if [[ "${SQUAD_FORCE_NUDGE:-}" != "1" ]]; then
    echo "Copilot already assigned on #$ISSUE — skip"
    if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
      echo "dispatched=false" >> "$GITHUB_OUTPUT"
    fi
    exit 0
  fi
  gh api --method DELETE \
    -H "Accept: application/vnd.github+json" \
    "/repos/${OWNER}/${NAME}/issues/${ISSUE}/assignees" \
    -f 'assignees[]=copilot-swe-agent[bot]' 2>/dev/null || true
fi

export REPO AGENT INSTRUCTIONS TARGET_REPO
export INSTRUCTIONS_JSON="$(python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))' <<<"$INSTRUCTIONS")"

BODY_FILE="$(mktemp)"
python3 -c "
import json, os
payload = {
  'assignees': ['copilot-swe-agent[bot]'],
  'agent_assignment': {
    'target_repo': os.environ['TARGET_REPO'],
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
  COMMENT_BODY="$(python3 "$FORMAT_COMMENT" dispatch "$AGENT" "${DISPATCH_LABEL:-$AGENT}" --repo "$SQUAD_ICON_REPO" --ref "$SQUAD_ICON_REF")"
  gh issue comment "$ISSUE" --repo "$REPO" --body "$COMMENT_BODY"
  echo "Dispatched $AGENT on $REPO#$ISSUE (target_repo=${TARGET_REPO})"
  if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
    echo "dispatched=true" >> "$GITHUB_OUTPUT"
    echo "agent=$AGENT" >> "$GITHUB_OUTPUT"
  fi
  exit 0
fi

rm -f "$BODY_FILE"
echo "Copilot assign API failed — posting manual instructions"
COMMENT_BODY="$(python3 "$FORMAT_COMMENT" fallback "$AGENT" --instructions-file "$INSTRUCTIONS_FILE" --repo "$SQUAD_ICON_REPO" --ref "$SQUAD_ICON_REF")"
gh issue comment "$ISSUE" --repo "$REPO" --body "$COMMENT_BODY" \
  || echo "Could not post fallback comment (check token permissions)"
exit 0
