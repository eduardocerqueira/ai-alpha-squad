#!/usr/bin/env bash
# Close Copilot planning PRs on ai-alpha-squad when deliverables belong on the issue.
# Also closes Copilot PRs that add product/extension code on the work-queue repo.
# Usage: squad-copilot-pr-guard.sh <owner/repo> <pr_number>
set -euo pipefail

REPO="${1:?owner/repo required}"
PR="${2:?pr number required}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORMAT_COMMENT="${ROOT}/scripts/format-squad-comment.py"
export SQUAD_ICON_REPO="${SQUAD_ICON_REPO:-$REPO}"
export SQUAD_ICON_REF="${SQUAD_ICON_REF:-main}"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"

close_copilot_pr() {
  local phase="$1"
  local issue="$2"
  local reason="$3"
  local next="$4"

  local pr_url
  pr_url="$(gh pr view "$PR" --repo "$REPO" --json url -q .url)"

  local msg
  msg="**Squad PR guard (${phase}):** ${reason}

${next}

PR: ${pr_url}"

  if [[ -n "$issue" ]] && issue_is_open "$issue"; then
    local comment_body
    comment_body="$(python3 "$FORMAT_COMMENT" notice --message "$msg" --repo "$SQUAD_ICON_REPO" --ref "$SQUAD_ICON_REF")"
    gh issue comment "$issue" --repo "$REPO" --body "$comment_body"
  elif [[ -n "$issue" ]]; then
    echo "Skip issue comment — #$issue is not OPEN"
  fi

  gh pr comment "$PR" --repo "$REPO" --body "$msg"
  gh pr close "$PR" --repo "$REPO" --comment "Closed by squad PR guard — see issue #${issue:-N/A} comment or PR thread."
  echo "Closed PR #$PR (phase=${phase})"

  chmod +x "${ROOT}/scripts/squad-nudge-stuck.sh" \
    "${ROOT}/scripts/squad-sync-planning-labels.sh" \
    "${ROOT}/scripts/squad-approve-copilot-workflows.sh"
  "${ROOT}/scripts/squad-approve-copilot-workflows.sh" "$REPO" "$PR" || true

}

resolve_linked_issue() {
  local pr_text
  pr_text="$(gh pr view "$PR" --repo "$REPO" --json body,title -q '[.title,.body]|join("\n")' 2>/dev/null || true)"
  python3 "${ROOT}/scripts/squad-resolve-guard-issue.py" "$REPO" "$PR" "$pr_text" 2>/dev/null || true
}

issue_is_open() {
  local issue="$1"
  [[ -n "$issue" ]] || return 1
  [[ "$(gh issue view "$issue" --repo "$REPO" --json state -q .state 2>/dev/null || true)" == "OPEN" ]]
}

copilot_assigned_on_issue() {
  local issue="$1"
  gh issue view "$issue" --repo "$REPO" --json assignees -q '.assignees[].login' 2>/dev/null \
    | grep -qiE '^(copilot|copilot-swe-agent|app/copilot-swe-agent)$'
}

# Re-dispatch only when Copilot is not already running (avoids guard ↔ PR death spiral).
maybe_guard_redispatch() {
  local issue="$1"
  local phase="$2"
  local reason="$3"

  [[ -n "$issue" && -n "$phase" ]] || return 0
  if ! issue_is_open "$issue"; then
    echo "Skip guard redispatch — issue #$issue is not OPEN"
    return 0
  fi
  if copilot_assigned_on_issue "$issue"; then
    echo "Skip guard redispatch — Copilot already assigned on #$issue"
    return 0
  fi

  chmod +x "${ROOT}/scripts/squad-dispatch-copilot.sh" "${ROOT}/scripts/squad-dispatch-subissue.sh"
  export SQUAD_ALLOW_COPILOT_REASSIGN=1
  case "$phase" in
    architect)
      SQUAD_NUDGE_REASON="$reason" "${ROOT}/scripts/squad-dispatch-copilot.sh" "$REPO" "$issue" "director-approved"
      ;;
    business-owner)
      SQUAD_NUDGE_REASON="$reason" "${ROOT}/scripts/squad-dispatch-copilot.sh" "$REPO" "$issue" "new"
      ;;
    developer)
      SQUAD_NUDGE_REASON="$reason" "${ROOT}/scripts/squad-dispatch-copilot.sh" "$REPO" "$issue" "designed"
      ;;
    *)
      echo "No guard redispatch for phase=${phase}"
      ;;
  esac
}

AUTHOR="$(gh pr view "$PR" --repo "$REPO" --json author -q .author.login 2>/dev/null || true)"
if [[ "$AUTHOR" != "copilot-swe-agent" && "$AUTHOR" != "Copilot" && "$AUTHOR" != "app/copilot-swe-agent" ]]; then
  echo "PR #$PR author is $AUTHOR — skip guard"
  exit 0
fi

PR_VIEW="$(gh pr view "$PR" --repo "$REPO" --json body,title -q '[.title,.body]|join("\n")' 2>/dev/null || true)"
PR_TITLE="$(gh pr view "$PR" --repo "$REPO" --json title -q .title 2>/dev/null || true)"
PR_FILES=""
while IFS= read -r path; do
  [[ -n "$path" ]] && PR_FILES+="${path}"$'\n'
done < <(gh pr diff "$PR" --repo "$REPO" --name-only 2>/dev/null || true)
export PR_VIEW
export PR_FILES

PRODUCT_DECISION="$(python3 - "$REPO" "$PR_TITLE" <<'PY'
import json, os, sys

sys.path.insert(0, os.environ.get("PYTHONPATH", "src"))
from ai_alpha_squad.pr_guard import should_close_queue_product_pr

repo = sys.argv[1]
title = sys.argv[2]
body = os.environ.get("PR_VIEW", "")
paths = [line for line in os.environ.get("PR_FILES", "").splitlines() if line.strip()]
close, reason = should_close_queue_product_pr(repo, changed_paths=paths, title=title, body=body)
print(json.dumps({"close": close, "reason": reason}))
PY
)"

if [[ "$(python3 -c 'import json,sys; print("yes" if json.loads(sys.argv[1])["close"] else "no")' "$PRODUCT_DECISION")" == "yes" ]]; then
  PRODUCT_REASON="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["reason"])' "$PRODUCT_DECISION")"
  ISSUE="$(resolve_linked_issue)"
  close_copilot_pr "queue-product-code" "$ISSUE" "$PRODUCT_REASON" \
    "Close this PR. Post planning artifacts on the parent issue; implement code only on the target product repo (Developer sub-issue)."
  # Product PRs must not re-dispatch Copilot (causes WIP extension loop on the queue repo).
  exit 0
fi

ISSUE="$(resolve_linked_issue)"
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

PR_HAS_MARKER=false
if [[ -n "$PR_VIEW" ]] && grep -qiF "$marker" <<<"$PR_VIEW"; then
  PR_HAS_MARKER=true
fi

if [[ "$has_marker" == false && "$PR_HAS_MARKER" == false ]]; then
  attempts="${SQUAD_PR_GUARD_WAIT_ATTEMPTS:-6}"
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
elif [[ "$has_marker" == false && "$PR_HAS_MARKER" == true ]]; then
  echo "PR body contains ${marker} but issue does not — promoting to issue #${ISSUE}."
  chmod +x "${ROOT}/scripts/squad-promote-pr-deliverable.py"
  if python3 "${ROOT}/scripts/squad-promote-pr-deliverable.py" "$REPO" "$ISSUE" "$PR" --phase "$phase"; then
    has_marker=true
    PR_HAS_MARKER=false
  else
    echo "Promotion failed (stub or incomplete PR body) — will close PR without label advance."
  fi
fi

if [[ "$has_marker" == false ]]; then
  REASON="Copilot opened PR #$PR before the required issue comment (\`${marker}\`) was posted on #$ISSUE."
  NEXT="Post the full deliverable on the issue, apply lifecycle labels, then close this PR."
else
  REASON="Deliverable is on issue #$ISSUE; this PR is a redundant Copilot handoff (squad policy: issue-first)."
  NEXT="Close this PR. Work continues on the issue and sub-issues only."
fi

close_copilot_pr "$phase" "$ISSUE" "$REASON" "$NEXT"
if [[ "$has_marker" == true ]]; then
  "${ROOT}/scripts/squad-sync-planning-labels.sh" "$REPO" "$ISSUE" || true
  if [[ -x "${ROOT}/scripts/squad_project_sync.py" ]]; then
    python3 "${ROOT}/scripts/squad_project_sync.py" sync-issue "$ISSUE" || true
  fi
  if [[ "$phase" == "business-owner" ]] && copilot_assigned_on_issue "$ISSUE"; then
    gh issue edit "$ISSUE" --repo "$REPO" --remove-assignee Copilot 2>/dev/null \
      || gh api --method DELETE "/repos/${REPO%%/*}/${REPO#*/}/issues/${ISSUE}/assignees" \
        -f 'assignees[]=Copilot' 2>/dev/null || true
    echo "Unassigned Copilot on #$ISSUE — BA on issue; awaiting Director approval."
  fi
elif [[ "$PR_HAS_MARKER" == true ]]; then
  echo "Deliverable only on PR (could not promote) — skip redispatch."
  maybe_guard_redispatch "$ISSUE" "$phase" "$REASON"
else
  maybe_guard_redispatch "$ISSUE" "$phase" "$REASON"
fi
