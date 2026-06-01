#!/usr/bin/env bash
# Apply lifecycle labels when planning deliverables appear on the issue thread.
# Usage: squad-sync-planning-labels.sh <owner/repo> <issue_number>
set -euo pipefail

REPO="${1:?owner/repo required}"
ISSUE="${2:?issue number required}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
FIND="${ROOT}/scripts/squad-find-subissues.py"
FORMAT="${ROOT}/scripts/format-squad-comment.py"

LABELS="$(gh issue view "$ISSUE" --repo "$REPO" --json labels -q '.labels[].name' | tr '\n' ' ')"

cleanup_stale_business_owner_label() {
  if grep -q 'director-approved' <<<"$LABELS" && grep -q 'business-owner' <<<"$LABELS"; then
    gh issue edit "$ISSUE" --repo "$REPO" --remove-label "business-owner" || true
    echo "Removed stale business-owner label on #$ISSUE (director-approved active)"
  fi
}

sync_ba() {
  if ! grep -qE '(^|[[:space:]])new([[:space:]]|$)' <<<"$LABELS"; then
    return 0
  fi
  if grep -q 'awaiting-approval' <<<"$LABELS"; then
    return 0
  fi
  if ! python3 - "$REPO" "$ISSUE" <<'PY'
import json, subprocess, sys
repo, issue = sys.argv[1], sys.argv[2]
sys.path.insert(0, "src")
from ai_alpha_squad.nudge import issue_has_deliverable, PHASE_MARKERS

proc = subprocess.run(
    ["gh", "issue", "view", issue, "--repo", repo, "--json", "comments"],
    capture_output=True, text=True, check=True,
)
comments = json.loads(proc.stdout)["comments"]
marker = PHASE_MARKERS["business-owner"]
raise SystemExit(0 if issue_has_deliverable(comments, marker) else 1)
PY
  then
    return 0
  fi

  gh issue edit "$ISSUE" --repo "$REPO" \
    --add-label "awaiting-approval" --add-label "business-owner" --remove-label "new"
  BODY="$(python3 "$FORMAT" notice \
    --message "**Squad orchestrator:** \`# Business Analysis\` detected on issue — applied \`awaiting-approval\`. Director review follows." \
    --repo "$REPO")"
  gh issue comment "$ISSUE" --repo "$REPO" --body "$BODY"
  echo "Synced BA labels on #$ISSUE"
}

sync_architect() {
  # v1 only — v2 has no architect/designed phase. Skip to avoid mislabelling.
  if [[ "${SQUAD_V2:-}" == "1" ]]; then
    return 0
  fi
  if ! grep -q 'director-approved' <<<"$LABELS"; then
    return 0
  fi
  if grep -q 'designed' <<<"$LABELS"; then
    return 0
  fi
  if ! python3 - "$REPO" "$ISSUE" <<'PY'
import json, subprocess, sys
repo, issue = sys.argv[1], sys.argv[2]
sys.path.insert(0, "src")
from ai_alpha_squad.nudge import issue_has_deliverable, PHASE_MARKERS, architect_subissues_complete

proc = subprocess.run(
    ["gh", "issue", "view", issue, "--repo", repo, "--json", "comments"],
    capture_output=True, text=True, check=True,
)
comments = json.loads(proc.stdout)["comments"]
if not issue_has_deliverable(comments, PHASE_MARKERS["architect"]):
    raise SystemExit(1)

subs = {}
for role in ("developer", "qa", "security", "devops", "tech-writer"):
    p = subprocess.run(
        ["python3", "scripts/squad-find-subissues.py", repo, issue, role, "--state", "all"],
        capture_output=True, text=True,
    )
    subs[role] = int(p.stdout.strip()) if p.returncode == 0 else None

raise SystemExit(0 if architect_subissues_complete(subs) else 1)
PY
  then
    return 0
  fi

  gh issue edit "$ISSUE" --repo "$REPO" --add-label "designed" --remove-label "director-approved"
  BODY="$(python3 "$FORMAT" notice \
    --message "**Squad orchestrator:** Technical spec and sub-issues detected — applied \`designed\`. Developer dispatch follows." \
    --repo "$REPO")"
  gh issue comment "$ISSUE" --repo "$REPO" --body "$BODY"
  echo "Synced architect labels on #$ISSUE"
}

sync_release_candidate() {
  # v2 only: developer deliverable on the issue → release-candidate gate.
  [[ "${SQUAD_V2:-}" == "1" ]] || return 0
  grep -q 'director-approved' <<<"$LABELS" || return 0
  if python3 - "$REPO" "$ISSUE" <<'PY'
import json, subprocess, sys
repo, issue = sys.argv[1], sys.argv[2]
sys.path.insert(0, "src")
from ai_alpha_squad.squad_v2 import has_deliverable

proc = subprocess.run(
    ["gh", "issue", "view", issue, "--repo", repo, "--json", "comments"],
    capture_output=True, text=True, check=True,
)
comments = tuple(json.loads(proc.stdout)["comments"])
raise SystemExit(0 if has_deliverable(comments, "developer") else 1)
PY
  then
    gh issue edit "$ISSUE" --repo "$REPO" \
      --add-label "release-candidate" --remove-label "director-approved" 2>/dev/null || true
    echo "Synced developer release-candidate on #$ISSUE"
  fi
}

cleanup_stale_business_owner_label
sync_ba
sync_architect
sync_release_candidate
