#!/usr/bin/env bash
# Dispatch QA, Security, DevOps, and Tech Writer on validation sub-issues.
# Usage: squad-dispatch-validation.sh <queue_repo> <parent_issue_number>
set -euo pipefail

REPO="${1:?queue repo required}"
PARENT="${2:?parent issue number required}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIND="${ROOT}/scripts/squad-find-subissues.py"
DISPATCH="${ROOT}/scripts/squad-dispatch-subissue.sh"
FORMAT_COMMENT="${ROOT}/scripts/format-squad-comment.py"

TARGET_REPO="$("$FIND" "$REPO" "$PARENT" --target-repo)" || TARGET_REPO="eduardocerqueira/seeker"
SUBISSUES="$("$FIND" "$REPO" "$PARENT")" || {
  echo "No validation sub-issues found for parent #$PARENT"
  exit 1
}

if gh issue view "$PARENT" --repo "$REPO" --json comments -q '.comments[].body' 2>/dev/null \
  | grep -q 'Validation phase started'; then
  echo "Validation agents already dispatched for parent #$PARENT — skip"
  if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
    echo "dispatched=false" >> "$GITHUB_OUTPUT"
  fi
  exit 0
fi

PARENT_URL="https://github.com/${REPO}/issues/${PARENT}"
DISPATCHED=0
SKIPPED=0

dispatch_role() {
  local role="$1"
  local sub_issue="$2"
  local instructions_file
  instructions_file="$(mktemp)"

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
2. Draft release notes for the next seeker release; post on sub-issue #${sub_issue} — heading must include: # Release Notes
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
  if "$DISPATCH" "$REPO" "$sub_issue" "$role" "$TARGET_REPO" "$instructions_file"; then
    DISPATCHED=$((DISPATCHED + 1))
  else
    SKIPPED=$((SKIPPED + 1))
  fi
  rm -f "$instructions_file"
}

while IFS='=' read -r role sub_issue; do
  [[ -n "$role" && -n "$sub_issue" ]] || continue
  dispatch_role "$role" "$sub_issue"
done < <(python3 -c "
import json, sys
data = json.loads(sys.argv[1])
for role, num in sorted(data.items()):
    print(f'{role}={num}')
" "$SUBISSUES")

SUMMARY="$(python3 "$FORMAT_COMMENT" notice \
  --message "**Squad orchestrator:** Validation phase started on parent #${PARENT}. Dispatched agents for: \`$(echo "$SUBISSUES" | python3 -c 'import json,sys; print(", ".join(sorted(json.loads(sys.stdin.read()).keys())))')\`. Track sub-issues for deliverables." \
  --repo "$REPO")"
gh issue comment "$PARENT" --repo "$REPO" --body "$SUMMARY"

if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  echo "dispatched=true" >> "$GITHUB_OUTPUT"
  echo "agent=validation-matrix" >> "$GITHUB_OUTPUT"
  echo "validation_count=$DISPATCHED" >> "$GITHUB_OUTPUT"
fi

echo "Validation dispatch complete: $DISPATCHED dispatched, $SKIPPED skipped"
