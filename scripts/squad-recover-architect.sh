#!/usr/bin/env bash
# Assign architect Copilot when parent issue is director-approved but unassigned.
# Usage: squad-recover-architect.sh <owner/repo> [issue_number]
set -euo pipefail

REPO="${1:?owner/repo required}"
ISSUE_FILTER="${2:-}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DISPATCH="${ROOT}/scripts/squad-dispatch-copilot.sh"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"

recover_one() {
  local issue="$1"
  if ! gh issue view "$issue" --repo "$REPO" --json labels -q '.labels[].name' | grep -qx 'director-approved'; then
    return 0
  fi
  if gh issue view "$issue" --repo "$REPO" --json labels -q '.labels[].name' | grep -qx 'designed'; then
    return 0
  fi
  if ! python3 - "$REPO" "$issue" <<'PY'
import json, subprocess, sys

repo, issue = sys.argv[1], sys.argv[2]
sys.path.insert(0, "src")
from ai_alpha_squad.nudge import PHASE_MARKERS, issue_has_deliverable

proc = subprocess.run(
    ["gh", "issue", "view", issue, "--repo", repo, "--json", "comments"],
    capture_output=True,
    text=True,
    check=True,
)
comments = json.loads(proc.stdout)["comments"]
raise SystemExit(0 if issue_has_deliverable(comments, PHASE_MARKERS["architect"]) else 1)
PY
  then
    return 0
  fi

  if gh issue view "$issue" --repo "$REPO" --json assignees -q '.assignees[].login' 2>/dev/null \
    | grep -qiE '^(copilot|copilot-swe-agent|app/copilot-swe-agent)$'; then
    echo "Issue #$issue — architect deliverable missing but Copilot already assigned"
    return 0
  fi

  echo "Recovering architect dispatch on #$issue (no Copilot assignee)"
  chmod +x "$DISPATCH" "${ROOT}/scripts/squad-dispatch-subissue.sh"
  export SQUAD_ALLOW_COPILOT_REASSIGN=1
  "$DISPATCH" "$REPO" "$issue" "director-approved"
}

if [[ -n "$ISSUE_FILTER" ]]; then
  recover_one "$ISSUE_FILTER"
  exit 0
fi

while read -r issue; do
  [[ -n "$issue" ]] && recover_one "$issue"
done < <(gh issue list --repo "$REPO" --label director-approved --state open --json number -q '.[].number')
