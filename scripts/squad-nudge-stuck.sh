#!/usr/bin/env bash
# Re-dispatch squad agents when planning/validation deliverables are missing.
# Usage:
#   squad-nudge-stuck.sh <owner/repo>                    # scan active jobs
#   squad-nudge-stuck.sh <owner/repo> <issue> --phase business-owner [--force] [--reason "..."]
set -euo pipefail

REPO="${1:?owner/repo required}"
shift

ISSUE=""
PHASE=""
FORCE=0
REASON=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --phase) PHASE="$2"; shift 2 ;;
    --force) FORCE=1; shift ;;
    --reason) REASON="$2"; shift 2 ;;
    *)
      if [[ -z "$ISSUE" ]]; then
        ISSUE="$1"
        shift
      else
        echo "Unknown argument: $1" >&2
        exit 1
      fi
      ;;
  esac
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
DISPATCH="${ROOT}/scripts/squad-dispatch-copilot.sh"
FIND="${ROOT}/scripts/squad-find-subissues.py"
FORMAT="${ROOT}/scripts/format-squad-comment.py"
SYNC="${ROOT}/scripts/squad-sync-planning-labels.sh"

MIN_AGE="${SQUAD_NUDGE_MIN_AGE_MINUTES:-15}"
COOLDOWN="${SQUAD_NUDGE_COOLDOWN_MINUTES:-30}"

nudge_issue() {
  local issue="$1"
  local phase="$2"
  local force="$3"
  local reason="$4"

  local decision
  decision="$(python3 - "$REPO" "$issue" "$phase" "$force" "$MIN_AGE" "$COOLDOWN" <<'PY'
import json, subprocess, sys
repo, issue, phase = sys.argv[1], sys.argv[2], sys.argv[3]
force = sys.argv[4] == "1"
min_age = float(sys.argv[5])
cooldown = float(sys.argv[6])

sys.path.insert(0, "src")
from ai_alpha_squad.nudge import (
    PHASE_MARKERS,
    issue_has_deliverable,
    last_nudge_minutes_ago,
    minutes_since,
    should_nudge_phase,
)

proc = subprocess.run(
    ["gh", "issue", "view", issue, "--repo", repo, "--json", "comments,createdAt,labels"],
    capture_output=True, text=True, check=True,
)
data = json.loads(proc.stdout)
comments = data["comments"]
labels = [l["name"] for l in data["labels"]]
marker = PHASE_MARKERS.get(phase, "")

if phase == "business-owner" and "awaiting-approval" in labels and "new" not in labels:
    print("skip:awaiting-approval")
    raise SystemExit(0)
if phase == "architect" and "designed" in labels:
    print("skip:designed")
    raise SystemExit(0)

has_deliverable = issue_has_deliverable(comments, marker) if marker else False
created_min = minutes_since(data.get("createdAt"))
nudge_min = last_nudge_minutes_ago(comments)

if should_nudge_phase(
    has_deliverable=has_deliverable,
    minutes_since_created=created_min,
    minutes_since_last_nudge=nudge_min,
    force=force,
    min_age_minutes=min_age,
    cooldown_minutes=cooldown,
):
    print("nudge")
else:
    print("skip:cooldown-or-complete")
PY
)"

  [[ "$decision" == "nudge" ]] || {
    echo "Nudge skipped for #$issue ($phase): $decision"
    return 0
  }

  # After repeated Copilot failures, complete planning from job pack instead of re-dispatch loop.
  if [[ "$phase" == "business-owner" || "$phase" == "architect" ]]; then
    export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
    if python3 "${ROOT}/scripts/squad-autonomous-planning-fallback.py" "$REPO" "$issue" --phase "$phase"; then
      chmod +x "${ROOT}/scripts/squad-sync-planning-labels.sh"
      "${ROOT}/scripts/squad-sync-planning-labels.sh" "$REPO" "$issue" || true
      echo "Autonomous planning fallback applied on #$issue ($phase)"
      return 0
    fi
  fi

  local lifecycle_label=""
  case "$phase" in
    business-owner) lifecycle_label="new" ;;
    architect) lifecycle_label="director-approved" ;;
    developer) lifecycle_label="designed" ;;
    release-manager) lifecycle_label="validation" ;;
  esac

  local msg="**Squad orchestrator nudge (${phase}):** Deliverable still missing."
  if [[ -n "$reason" ]]; then
    msg="${msg}

Previous attempt: ${reason}"
  fi
  msg="${msg}

Re-dispatching \`${phase}\` agent. Post on the **issue** per \`.agents/copilot-issue-first-delivery.md\` — do not open planning PRs on ai-alpha-squad."

  local body
  body="$(python3 "$FORMAT" notice --message "$msg" --repo "$REPO")"
  gh issue comment "$issue" --repo "$REPO" --body "$body"

  export SQUAD_FORCE_NUDGE=1
  export SQUAD_NUDGE_REASON="$reason"
  if [[ "$phase" == "qa" || "$phase" == "security" || "$phase" == "devops" || "$phase" == "tech-writer" ]]; then
    local parent
    parent="$(gh issue view "$issue" --repo "$REPO" --json body -q .body | grep -Eo 'issues/[0-9]+' | head -1 | cut -d/ -f2)"
    [[ -n "$parent" ]] || parent="$issue"
    "$ROOT/scripts/squad-dispatch-validation.sh" "$REPO" "$parent" "$phase"
  elif [[ -n "$lifecycle_label" ]]; then
    "$DISPATCH" "$REPO" "$issue" "$lifecycle_label"
  fi
  echo "Nudged #$issue phase=${phase}"
}

nudge_validation_roles() {
  local parent="$1"
  local force="$2"

  if ! gh issue view "$parent" --repo "$REPO" --json labels -q '.labels[].name' | grep -qx 'implemented'; then
    return 0
  fi

  local status
  status="$(python3 "$FIND" "$REPO" "$parent" --validation-status 2>/dev/null || echo '{}')"
  local roles=(qa security devops tech-writer)
  local role
  for role in "${roles[@]}"; do
    local complete
    complete="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1]).get(sys.argv[2], False))' "$status" "$role")"
    if [[ "$complete" == "True" ]]; then
      continue
    fi
    local sub
    sub="$(python3 "$FIND" "$REPO" "$parent" "$role" --state open 2>/dev/null || true)"
    [[ -n "$sub" ]] || continue
    nudge_issue "$sub" "$role" "$force" "Validation deliverable missing on sub-issue #${sub}."
  done
}

if [[ -n "$ISSUE" && -n "$PHASE" ]]; then
  "$SYNC" "$REPO" "$ISSUE" || true
  nudge_issue "$ISSUE" "$PHASE" "$FORCE" "$REASON"
  exit 0
fi

if [[ -n "$ISSUE" ]]; then
  ISSUES=("$ISSUE")
else
  mapfile -t ISSUES < <(
    {
      gh issue list --repo "$REPO" --label new --state open --json number -q '.[].number'
      gh issue list --repo "$REPO" --label director-approved --state open --json number -q '.[].number'
      gh issue list --repo "$REPO" --label designed --state open --json number -q '.[].number'
      gh issue list --repo "$REPO" --label implemented --state open --json number -q '.[].number'
    } | sort -nu
  )
fi

for issue in "${ISSUES[@]}"; do
  [[ -n "$issue" ]] || continue
  "$SYNC" "$REPO" "$issue" || true

  LABELS="$(gh issue view "$issue" --repo "$REPO" --json labels -q '.labels[].name' | tr '\n' ' ')"
  if grep -qE '(^|[[:space:]])new([[:space:]]|$)' <<<"$LABELS" && ! grep -q 'awaiting-approval' <<<"$LABELS"; then
    nudge_issue "$issue" "business-owner" "$FORCE" "$REASON"
  elif grep -q 'director-approved' <<<"$LABELS" && ! grep -q 'designed' <<<"$LABELS"; then
    nudge_issue "$issue" "architect" "$FORCE" "$REASON"
  elif grep -q 'designed' <<<"$LABELS" && ! grep -q 'implemented' <<<"$LABELS"; then
    nudge_issue "$issue" "developer" "$FORCE" "$REASON"
  elif grep -q 'implemented' <<<"$LABELS" && ! grep -q 'validation' <<<"$LABELS"; then
    nudge_validation_roles "$issue" "$FORCE"
  fi
done

echo "Nudge scan complete for $REPO"
