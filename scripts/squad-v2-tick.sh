#!/usr/bin/env bash
# v2 phase watch: sync labels from deliverables, dispatch next agent, nudge stale runs.
# Usage: squad-v2-tick.sh <queue_repo> [issue_number]
set -euo pipefail

REPO="${1:?queue repo}"
ISSUE_FILTER="${2:-}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
export SQUAD_V2=1
DISPATCH="${ROOT}/scripts/squad-v2-dispatch.sh"
SYNC="${ROOT}/scripts/squad-sync-planning-labels.sh"

sync_labels() {
  local issue="$1"
  chmod +x "$SYNC" 2>/dev/null || true
  # Label transitions (BA→awaiting-approval, dev deliverable→release-candidate)
  # live in the shared sync script, gated by SQUAD_V2.
  "$SYNC" "$REPO" "$issue" || true
}

# Recover an orphaned run: an in_progress marker with no terminal marker, older
# than the stale threshold (a cancelled/timed-out run never posts a result).
# Posting a failure marker clears the "active" state and counts as an attempt.
recover_stale_run() {
  local issue="$1"
  python3 - "$REPO" "$issue" <<'PY' || true
import json, os, subprocess, sys
from datetime import datetime, timezone

repo, issue = sys.argv[1], sys.argv[2]
sys.path.insert(0, "src")
from ai_alpha_squad.squad_v2 import find_stale_in_progress, failed_comment

data = json.loads(subprocess.check_output(
    ["gh", "issue", "view", issue, "--repo", repo, "--json", "comments"], text=True))
comments = tuple(data.get("comments") or ())
max_age = int(os.environ.get("SQUAD_V2_STALE_MINUTES", "120"))
agent = find_stale_in_progress(comments, datetime.now(timezone.utc).isoformat(), max_age)
if agent:
    body = failed_comment(agent, f"stale run auto-recovered after {max_age}m with no result")
    subprocess.run(["gh", "issue", "comment", issue, "--repo", repo, "--body", body], check=True)
    print(f"recovered stale {agent} run on #{issue}")
PY
}

tick_issue() {
  local issue="$1"
  recover_stale_run "$issue"
  sync_labels "$issue"
  chmod +x "$DISPATCH"
  "$DISPATCH" "$REPO" "$issue" || true
}

if [[ -n "$ISSUE_FILTER" ]]; then
  tick_issue "$ISSUE_FILTER"
  exit 0
fi

for issue in $(gh issue list --repo "$REPO" --state open --json number,labels \
  -q '.[] | select([.labels[].name] | any(. == "new" or . == "director-approved" or . == "awaiting-approval" or . == "release-candidate")) | .number'); do
  [[ -n "$issue" ]] && tick_issue "$issue"
done

echo "v2 phase tick complete for $REPO"
