#!/usr/bin/env bash
# Scan open Copilot PRs on the work-queue repo and run squad-copilot-pr-guard on each.
# Then reconcile planning issues (promote branch .md files, sync labels/board).
# Usage: squad-scan-planning-prs.sh [owner/repo]
set -euo pipefail

REPO="${1:-${GITHUB_REPOSITORY:-}}"
if [[ -z "$REPO" ]]; then
  echo "owner/repo required" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
GUARD="${ROOT}/scripts/squad-copilot-pr-guard.sh"
APPROVE="${ROOT}/scripts/squad-approve-copilot-workflows.sh"
RECONCILE="${ROOT}/scripts/squad-reconcile-planning-deliverables.sh"

chmod +x "$GUARD" "$APPROVE" "$RECONCILE" \
  "${ROOT}/scripts/squad-nudge-stuck.sh" \
  "${ROOT}/scripts/squad-sync-planning-labels.sh" \
  "${ROOT}/scripts/squad-dispatch-copilot.sh" \
  "${ROOT}/scripts/squad-dispatch-subissue.sh" \
  "${ROOT}/scripts/squad-promote-pr-deliverable.py" 2>/dev/null || true

PRS=()
while IFS= read -r pr; do
  [[ -n "$pr" ]] && PRS+=("$pr")
done < <(
  gh pr list --repo "$REPO" --state open --limit 30 --json number,author \
    --jq '.[] | select(
      (.author.login | ascii_downcase) == "copilot"
      or (.author.login | ascii_downcase) == "copilot-swe-agent"
      or (.author.login | ascii_downcase) == "app/copilot-swe-agent"
    ) | .number'
)

if [[ ${#PRS[@]} -eq 0 ]]; then
  echo "No open Copilot PRs on $REPO"
else
  echo "Scanning ${#PRS[@]} open Copilot PR(s) on $REPO"
  CLOSED=0
  for pr in "${PRS[@]}"; do
    echo "--- PR #$pr ---"
    "$APPROVE" "$REPO" "$pr" || true
    if "$GUARD" "$REPO" "$pr"; then
      STATE="$(gh pr view "$pr" --repo "$REPO" --json state -q .state 2>/dev/null || true)"
      if [[ "$STATE" == "CLOSED" ]]; then
        CLOSED=$((CLOSED + 1))
      fi
    fi
  done
  echo "Scan complete: ${#PRS[@]} checked, $CLOSED closed"
fi

for issue in $(gh issue list --repo "$REPO" --label new --state open --json number -q '.[].number' 2>/dev/null || true); do
  [[ -n "$issue" ]] && "$RECONCILE" "$REPO" "$issue" || true
done
for issue in $(gh issue list --repo "$REPO" --label director-approved --state open --json number -q '.[].number' 2>/dev/null || true); do
  [[ -n "$issue" ]] && "$RECONCILE" "$REPO" "$issue" || true
done
