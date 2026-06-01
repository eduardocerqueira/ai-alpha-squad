#!/usr/bin/env bash
# Dispatch QA, Security, DevOps, and Tech Writer on validation sub-issues (Phase 4 — parallel).
# Usage:
#   squad-dispatch-validation.sh <queue_repo> <parent_issue_number>           # all roles (bash parallel)
#   squad-dispatch-validation.sh <queue_repo> <parent_issue_number> <role>  # single role (CI matrix)
set -euo pipefail

REPO="${1:?queue repo required}"
PARENT="${2:?parent issue number required}"
ROLE_FILTER="${3:-}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIND="${ROOT}/scripts/squad-find-subissues.py"
DISPATCH="${ROOT}/scripts/squad-dispatch-subissue.sh"
FORMAT_COMMENT="${ROOT}/scripts/format-squad-comment.py"

export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"

TARGET_REPO="$("$FIND" "$REPO" "$PARENT" --target-repo)" || TARGET_REPO="eduardocerqueira/seeker"
SUBISSUES="$("$FIND" "$REPO" "$PARENT")" || {
  echo "No validation sub-issues found for parent #$PARENT"
  exit 1
}

PARENT_URL="https://github.com/${REPO}/issues/${PARENT}"
DISPATCHED=0
SKIPPED=0
FAILED=0

role_should_dispatch() {
  local role="$1"
  local sub_issue="$2"
  python3 - "$REPO" "$sub_issue" "$role" <<'PY'
import json, os, subprocess, sys

sys.path.insert(0, os.environ.get("PYTHONPATH", "src"))
from ai_alpha_squad.agent_models import HF_DISPATCH_MARKER, HF_RESULT_MARKER
from ai_alpha_squad.validation_dispatch import role_dispatch_marker

repo, sub_issue, role = sys.argv[1], sys.argv[2], sys.argv[3]
proc = subprocess.run(
    ["gh", "issue", "view", sub_issue, "--repo", repo, "--json", "assignees,comments,state"],
    capture_output=True,
    text=True,
    check=True,
)
data = json.loads(proc.stdout)
if data.get("state") == "CLOSED":
    raise SystemExit(1)

marker = role_dispatch_marker(role).lower()
hf_markers = (HF_DISPATCH_MARKER.lower(), HF_RESULT_MARKER.lower())
for comment in data.get("comments") or []:
    body = (comment.get("body") or "").lower()
    if marker in body:
        raise SystemExit(1)
    if any(m in body for m in hf_markers) and f"`{role}`" in body:
        raise SystemExit(1)

assignees = [a.get("login", "").lower() for a in data.get("assignees") or []]
if any("copilot" in login for login in assignees) and os.environ.get("SQUAD_FORCE_NUDGE") != "1":
    raise SystemExit(1)
raise SystemExit(0)
PY
}

dispatch_role() {
  local role="$1"
  local sub_issue="$2"
  local instructions_file
  instructions_file="$(mktemp)"

  if ! role_should_dispatch "$role" "$sub_issue"; then
    echo "Skip $role on #$sub_issue (already dispatched or complete)"
    SKIPPED=$((SKIPPED + 1))
    return 0
  fi

  case "$role" in
    qa)
      cat > "$instructions_file" <<EOF
You are the QA agent for AI Alpha Squad.

Read: .agents/agent-qa.md and .agents/templates/qa-report-template.md
Parent issue: ${PARENT_URL}
Sub-issue: #${sub_issue}

1. Review merged implementation on target repo: ${TARGET_REPO} (main branch + linked PRs on parent/dev sub-issue)
2. Run/verify tests; validate FR/BR acceptance criteria from the Technical Specification on parent #${PARENT}
3. Post FULL QA report as issue comment on sub-issue #${sub_issue} — heading must include: # QA Report
4. Comment summary + link on parent #${PARENT}
5. Close sub-issue #${sub_issue} when deliverable is posted
6. Do NOT merge code. Do NOT open PRs on ai-alpha-squad for reports only.
EOF
      ;;
    security)
      cat > "$instructions_file" <<EOF
You are the Security agent for AI Alpha Squad.

Read: .agents/agent-security.md and .agents/templates/security-report-template.md
Parent issue: ${PARENT_URL}
Sub-issue: #${sub_issue}

1. Review ${TARGET_REPO} for secrets handling, dependency CVEs, obfuscation/redaction, workflow permissions
2. Post FULL security report on sub-issue #${sub_issue} — heading must include: # Security Report
3. Use FIND-* IDs for findings; comment summary on parent #${PARENT}
4. Critical findings block release — document clearly
5. Close sub-issue #${sub_issue} when deliverable is posted
6. Do NOT open PRs on ai-alpha-squad for reports only.
EOF
      ;;
    devops)
      cat > "$instructions_file" <<EOF
You are the DevOps agent for AI Alpha Squad.

Read: .agents/agent-devops.md, .agents/templates/deployment-checklist-template.md, .agents/templates/runbook-template.md, .agents/templates/pull-request-template.md, and .github/SECRETS_AND_VARIABLES.md
Parent issue: ${PARENT_URL}
Sub-issue: #${sub_issue}

1. Review and harden CI/CD on ${TARGET_REPO} (workflow permissions, runtime/tooling consistency, secrets usage, scheduled jobs, broken release.yml if present)
2. Verify default GITHUB_TOKEN permissions/config in each affected workflow; use SQUAD_ORCHESTRATOR_TOKEN only if cross-repo or elevated access is required
3. Open PR(s) on ${TARGET_REPO} for pipeline fixes using the PR template; link parent #${PARENT}, sub-issue #${sub_issue}, and the technical spec
4. Post deployment checklist on sub-issue #${sub_issue} — heading must include: # Deployment Checklist — and include PR links plus rollback/runbook notes
5. Comment summary + deliverable links on parent #${PARENT}
6. Close sub-issue #${sub_issue} when deliverable is posted
7. Ensure CI runs on push to copilot/* branches where workflow approval blocks PR checks
8. Do not merge to production without Director approval
EOF
      ;;
    tech-writer)
      cat > "$instructions_file" <<EOF
You are the Tech Writer agent for AI Alpha Squad.

Read: .agents/agent-tech-writer.md and .agents/templates/release-notes-template.md
Parent issue: ${PARENT_URL}
Sub-issue: #${sub_issue}

1. Update README and setup docs on ${TARGET_REPO} to match merged modernization
2. Draft release notes for the next release; post on sub-issue #${sub_issue} — heading must include: # Release Notes
3. Open PR on ${TARGET_REPO} if doc changes needed; link parent #${PARENT}
4. Close sub-issue #${sub_issue} when deliverable is posted
5. Comment summary on parent #${PARENT}
EOF
      ;;
    *)
      rm -f "$instructions_file"
      return 0
      ;;
  esac

  export DISPATCH_LABEL="implemented"
  export SQUAD_ALLOW_COPILOT_REASSIGN=1
  if [[ "${SQUAD_FORCE_NUDGE:-}" == "1" ]]; then
    gh api --method DELETE \
      -H "Accept: application/vnd.github+json" \
      "/repos/${REPO%%/*}/${REPO#*/}/issues/${sub_issue}/assignees" \
      -f 'assignees[]=copilot-swe-agent[bot]' 2>/dev/null || true
  fi

  local marker
  marker="$(python3 -c 'from ai_alpha_squad.validation_dispatch import role_dispatch_marker; import sys; print(role_dispatch_marker(sys.argv[1]))' "$role")"

  if "$DISPATCH" "$REPO" "$sub_issue" "$role" "$TARGET_REPO" "$instructions_file"; then
    DISPATCHED=$((DISPATCHED + 1))
    PROVIDER="$(python3 -c 'from ai_alpha_squad.agent_models import resolve_provider; print(resolve_provider())')"
    gh issue comment "$sub_issue" --repo "$REPO" --body "${marker} — ${PROVIDER} ${role} assigned for parent #${PARENT}." \
      || true
  else
    FAILED=$((FAILED + 1))
  fi
  rm -f "$instructions_file"
}

run_roles() {
  local pids=()
  local role sub_issue

  while IFS='=' read -r role sub_issue; do
    [[ -n "$role" && -n "$sub_issue" ]] || continue
    if [[ -n "$ROLE_FILTER" && "$role" != "$ROLE_FILTER" ]]; then
      continue
    fi
    if [[ -n "$ROLE_FILTER" ]]; then
      dispatch_role "$role" "$sub_issue"
      return
    fi
    dispatch_role "$role" "$sub_issue" &
    pids+=("$!")
  done < <(python3 -c "
import json, sys
data = json.loads(sys.argv[1])
for role, num in sorted(data.items()):
    print(f'{role}={num}')
" "$SUBISSUES")

  if [[ ${#pids[@]} -gt 0 ]]; then
    local pid
    for pid in "${pids[@]}"; do
      wait "$pid" || FAILED=$((FAILED + 1))
    done
  fi
}

run_roles

if [[ -z "$ROLE_FILTER" && "$DISPATCHED" -gt 0 ]]; then
  NEEDS_SUMMARY="$(python3 - "$REPO" "$PARENT" <<'PY'
import json, os, subprocess, sys

sys.path.insert(0, os.environ.get("PYTHONPATH", "src"))
from ai_alpha_squad.validation_dispatch import parent_has_validation_dispatch

repo, parent = sys.argv[1], sys.argv[2]
proc = subprocess.run(
    ["gh", "issue", "view", parent, "--repo", repo, "--json", "comments"],
    capture_output=True,
    text=True,
    check=True,
)
comments = json.loads(proc.stdout)["comments"]
print("no" if parent_has_validation_dispatch(comments) else "yes")
PY
)"
  if [[ "$NEEDS_SUMMARY" == "yes" ]]; then
    SUMMARY="$(python3 "$FORMAT_COMMENT" notice \
      --message "**Squad orchestrator: Validation phase started** on parent #${PARENT}. Dispatched: ${DISPATCHED}, skipped: ${SKIPPED}, failed: ${FAILED}. Track sub-issues for QA, Security, DevOps, and Tech Writer deliverables." \
      --repo "$REPO")"
    gh issue comment "$PARENT" --repo "$REPO" --body "$SUMMARY"
  fi
fi

if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  if [[ "$DISPATCHED" -gt 0 ]]; then
    echo "dispatched=true" >> "$GITHUB_OUTPUT"
    echo "agent=validation-matrix" >> "$GITHUB_OUTPUT"
    echo "validation_count=$DISPATCHED" >> "$GITHUB_OUTPUT"
  else
    echo "dispatched=false" >> "$GITHUB_OUTPUT"
  fi
fi

echo "Validation dispatch complete: $DISPATCHED dispatched, $SKIPPED skipped, $FAILED failed (role=${ROLE_FILTER:-all})"
if [[ "$FAILED" -gt 0 ]]; then
  exit 1
fi
