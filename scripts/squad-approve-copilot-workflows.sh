#!/usr/bin/env bash
# Approve pending GitHub Actions workflow runs for a Copilot PR (reduces "workflow awaiting approval").
# Usage: squad-approve-copilot-workflows.sh <owner/repo> <pr_number>
# Requires GH_TOKEN with actions:write (SQUAD_ORCHESTRATOR_TOKEN).
set -euo pipefail

REPO="${1:?owner/repo required}"
PR="${2:?pr number required}"

SHA="$(gh pr view "$PR" --repo "$REPO" --json headRefOid -q .headRefOid 2>/dev/null || true)"
if [[ -z "$SHA" ]]; then
  echo "Could not resolve PR #$PR head SHA — skip workflow approve"
  exit 0
fi

OWNER="${REPO%%/*}"
NAME="${REPO#*/}"

APPROVED=0
while IFS= read -r run_id; do
  [[ -n "$run_id" ]] || continue
  if gh api --method POST \
    -H "Accept: application/vnd.github+json" \
    "/repos/${OWNER}/${NAME}/actions/runs/${run_id}/approve" 2>/dev/null; then
    APPROVED=$((APPROVED + 1))
    echo "Approved workflow run ${run_id} for PR #${PR}"
  fi
done < <(
  gh api \
    -H "Accept: application/vnd.github+json" \
    "/repos/${OWNER}/${NAME}/actions/runs?head_sha=${SHA}&per_page=30" \
    --jq '.workflow_runs[] | select(.status == "waiting" or .conclusion == "action_required") | .id' 2>/dev/null || true
)

if [[ "$APPROVED" -eq 0 ]]; then
  echo "No pending workflow runs to approve for PR #${PR} (${SHA:0:7})"
else
  echo "Approved ${APPROVED} workflow run(s) for PR #${PR}"
fi
