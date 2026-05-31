#!/usr/bin/env bash
# Close Copilot planning PRs on ai-alpha-squad when deliverables belong on the issue.
# Usage: squad-copilot-pr-guard.sh <owner/repo> <pr_number>
set -euo pipefail

REPO="${1:?owner/repo required}"
PR="${2:?pr number required}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORMAT_COMMENT="${ROOT}/scripts/format-squad-comment.py"
export SQUAD_ICON_REPO="${SQUAD_ICON_REPO:-$REPO}"
export SQUAD_ICON_REF="${SQUAD_ICON_REF:-main}"

AUTHOR="$(gh pr view "$PR" --repo "$REPO" --json author -q .author.login 2>/dev/null || true)"
if [[ "$AUTHOR" != "copilot-swe-agent" && "$AUTHOR" != "Copilot" && "$AUTHOR" != "app/copilot-swe-agent" ]]; then
  echo "PR #$PR author is $AUTHOR — skip guard"
  exit 0
fi

ISSUE="$(gh api graphql -f query="
query(\$owner: String!, \$name: String!, \$pr: Int!) {
  repository(owner: \$owner, name: \$name) {
    pullRequest(number: \$pr) {
      closingIssuesReferences(first: 5) { nodes { number } }
    }
  }
}" -f owner="${REPO%%/*}" -f name="${REPO#*/}" -F pr="$PR" \
  --jq '.data.repository.pullRequest.closingIssuesReferences.nodes[0].number // empty' 2>/dev/null || true)"

if [[ -z "$ISSUE" ]]; then
  BODY="$(gh pr view "$PR" --repo "$REPO" --json body,title -q '[.title,.body]|join("\n")')"
  ISSUE="$(printf '%s' "$BODY" | grep -Eo '(issue|Issue|Fixes|fixes|Closes|closes)[^#]*#[[:space:]]*[0-9]+|#[0-9]+' | grep -Eo '[0-9]+' | head -1 || true)"
fi

if [[ -z "$ISSUE" ]]; then
  echo "Could not resolve linked issue for PR #$PR — skip"
  exit 0
fi

LABELS="$(gh issue view "$ISSUE" --repo "$REPO" --json labels -q '.labels[].name' | tr '\n' ' ')"

phase=""
marker=""
if grep -q 'director-approved' <<<"$LABELS" && ! grep -q 'designed' <<<"$LABELS"; then
  phase="architect"
  marker="# Technical Specification"
elif grep -qE '(^|[[:space:]])new([[:space:]]|$)|business-owner' <<<"$LABELS" && ! grep -q 'awaiting-approval' <<<"$LABELS"; then
  phase="business-owner"
  marker="# Business Analysis"
else
  echo "Issue #$ISSUE not in a guarded planning phase — skip PR #$PR"
  exit 0
fi

export MARKER="$marker"
export ISSUE
export REPO

issue_has_deliverable_marker() {
  python3 -c "
import json, os, subprocess, sys
sys.path.insert(0, '${ROOT}/src')
from ai_alpha_squad.nudge import issue_has_deliverable

repo = os.environ['REPO']
issue = os.environ['ISSUE']
marker = os.environ['MARKER']
proc = subprocess.run(
    ['gh', 'issue', 'view', issue, '--repo', repo, '--json', 'comments'],
    capture_output=True, text=True, check=True,
)
comments = json.loads(proc.stdout)['comments']
sys.exit(0 if issue_has_deliverable(comments, marker) else 1)
"
}

has_marker=false
if issue_has_deliverable_marker 2>/dev/null; then
  has_marker=true
fi

if [[ "$has_marker" == false ]]; then
  attempts="${SQUAD_PR_GUARD_WAIT_ATTEMPTS:-18}"
  interval="${SQUAD_PR_GUARD_WAIT_INTERVAL_SEC:-10}"
  echo "Waiting up to $((attempts * interval))s for deliverable on issue #${ISSUE} (${marker})..."
  for ((i = 1; i <= attempts; i++)); do
    sleep "$interval"
    if issue_has_deliverable_marker 2>/dev/null; then
      has_marker=true
      echo "Found ${marker} on issue #${ISSUE} after ${i} poll(s)."
      break
    fi
  done
fi

PR_URL="$(gh pr view "$PR" --repo "$REPO" --json url -q .url)"

if [[ "$has_marker" == false ]]; then
  REASON="Copilot opened PR #$PR before the required issue comment (\`${marker}\`) was posted on #$ISSUE."
  NEXT="Post the full deliverable on the issue, apply lifecycle labels, then close this PR."
else
  REASON="Deliverable is on issue #$ISSUE; this PR is a redundant Copilot handoff (squad policy: issue-first)."
  NEXT="Close this PR. Work continues on the issue and sub-issues only."
fi

MSG="**Squad PR guard (${phase}):** ${REASON}

${NEXT}

PR: ${PR_URL}"

COMMENT_BODY="$(python3 "$FORMAT_COMMENT" notice --message "$MSG" --repo "$SQUAD_ICON_REPO" --ref "$SQUAD_ICON_REF")"
gh issue comment "$ISSUE" --repo "$REPO" --body "$COMMENT_BODY"

gh pr comment "$PR" --repo "$REPO" --body "$MSG"
gh pr close "$PR" --repo "$REPO" --comment "Closed by squad PR guard — deliverable belongs on issue #${ISSUE}. See issue comment."
echo "Closed PR #$PR (phase=${phase}, has_marker=${has_marker})"

chmod +x "${ROOT}/scripts/squad-nudge-stuck.sh" "${ROOT}/scripts/squad-sync-planning-labels.sh"
if [[ "$has_marker" == true ]]; then
  "${ROOT}/scripts/squad-sync-planning-labels.sh" "$REPO" "$ISSUE" || true
else
  "${ROOT}/scripts/squad-nudge-stuck.sh" "$REPO" "$ISSUE" --phase "$phase" --force --reason "$REASON"
fi
