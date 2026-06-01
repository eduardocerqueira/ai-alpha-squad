#!/usr/bin/env bash
# Dispatch Copilot cloud agent for a squad lifecycle label on an issue.
# Usage: squad-dispatch-copilot.sh <owner/repo> <issue_number> <lifecycle_label>
set -euo pipefail

REPO="${1:?repo required}"
ISSUE="${2:?issue number required}"
LABEL="${3:?lifecycle label required}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIND="${ROOT}/scripts/squad-find-subissues.py"
DISPATCH="${ROOT}/scripts/squad-dispatch-subissue.sh"

TARGET_REPO="${TARGET_REPO:-$REPO}"
AGENT=""
PARENT_ISSUE="$ISSUE"
DISPATCH_ISSUE="$ISSUE"
INSTRUCTIONS_FILE=""

case "$LABEL" in
  new)
    AGENT="business-owner"
    INSTRUCTIONS_FILE="$(mktemp)"
    cat > "$INSTRUCTIONS_FILE" <<EOF
You are the Business Owner for AI Alpha Squad.

Read first: .agents/copilot-issue-first-delivery.md (issue-first — no planning PR).

1. Read .agents/agent-business-owner.md and .agents/templates/business-analysis-template.md
2. Complete Business Analysis for issue #${ISSUE} (read the issue body and comments)
3. **FIRST — post on the issue (required before any git branch or PR):**
   gh issue comment ${ISSUE} --repo ${REPO} --body-file ba.md
   The file MUST start with a line exactly: # Business Analysis
4. Add label awaiting-approval and remove label new (use gh issue edit)
5. Comment on the issue: Squad deliverable complete on this issue.
6. **Do NOT open a pull request, branch, or commit** on ai-alpha-squad. No files in this repo — issue comment + labels only.
7. If you already opened a draft PR, close it immediately after steps 3–5.
8. **Never** use \`gh pr create\` on ai-alpha-squad. A PR is not a valid BA handoff; the squad PR guard will close it.

You have read/search tools only on this repo. Use \`gh issue comment\` and \`gh issue edit\` from the shell.

Example (required pattern):
  gh issue comment ${ISSUE} --repo ${REPO} --body-file ba.md
  gh issue edit ${ISSUE} --repo ${REPO} --add-label awaiting-approval --add-label business-owner --remove-label new

If you cannot post issue comments, output the full BA in your final message and stop — do not claim the issue was updated and do not open a PR.
EOF
    ;;
  director-approved|approved)
    export SQUAD_ALLOW_COPILOT_REASSIGN=1
    AGENT="architect"
    INSTRUCTIONS_FILE="$(mktemp)"
    cat > "$INSTRUCTIONS_FILE" <<EOF
You are the Architect for AI Alpha Squad.

Read first: .agents/copilot-issue-first-delivery.md (issue-first — no planning PR).

1. Read .agents/agent-architect.md and Director-approved Business Analysis on issue #${ISSUE}
2. Write Technical Specification per .agents/templates/tech-spec-template.md
3. Post the FULL tech spec as an issue comment — heading must include: # Technical Specification
4. Create GitHub sub-issues (gh issue create) for Developer, QA, Security, DevOps, Tech Writer using .agents/templates/sub-issue-template.md — reference parent #${ISSUE} and target repo from the issue body
5. Map every FR-* requirement to BR-* from the BA
6. Add label designed and remove director-approved
7. Comment on the issue: Squad deliverable complete on this issue.
8. Do NOT open a pull request, branch, or commit on ai-alpha-squad. Issue comment + sub-issues are the deliverable.

You have read/search tools only on this repo. Use \`gh issue comment\`, \`gh issue create\`, and \`gh issue edit\`.

If a draft PR exists, close it immediately after steps 3–7.

Do NOT add director-approved or approved labels. Do NOT implement application code in product repos.
EOF
    ;;
  designed)
    export SQUAD_ALLOW_COPILOT_REASSIGN=1
    AGENT="developer"
    if gh issue view "$ISSUE" --repo "$REPO" --json labels -q '.labels[].name' 2>/dev/null | grep -qx 'developer'; then
      DEV_ISSUE="$ISSUE"
      PARENT_ISSUE="$(gh issue view "$ISSUE" --repo "$REPO" --json body -q .body \
        | grep -Eo 'issues/[0-9]+' | head -1 | cut -d/ -f2)"
    else
      PARENT_ISSUE="$ISSUE"
      DEV_ISSUE="$("$FIND" "$REPO" "$PARENT_ISSUE" developer)" || {
        echo "No developer sub-issue found for parent #$PARENT_ISSUE"
        exit 1
      }
    fi
    DISPATCH_ISSUE="$DEV_ISSUE"
    TARGET_REPO="$("$FIND" "$REPO" "$PARENT_ISSUE" --target-repo)" || TARGET_REPO="eduardocerqueira/seeker"
    INSTRUCTIONS_FILE="$(mktemp)"
    cat > "$INSTRUCTIONS_FILE" <<EOF
You are the Developer for AI Alpha Squad — implementation runs on the target product repo.

Read the Developer sub-issue #${DEV_ISSUE} and squad context on parent issue #${PARENT_ISSUE}:
https://github.com/${REPO}/issues/${PARENT_ISSUE}

Technical Specification: parent issue comment with heading "# Technical Specification".
Custom agent profile on target repo: .github/agents/developer.agent.md

1. Clone and work on target repo: ${TARGET_REPO} (branch from main)
2. Implement Phase 1 per tech spec FR-003–FR-006 (Python LTS, pinned deps, preserve scheduled collection + obfuscation)
3. Add/extend tests; keep CI green on your PR branch
4. Open PR(s) on ${TARGET_REPO}; link parent #${PARENT_ISSUE}, sub-issue #${DEV_ISSUE}, FR/BR IDs in description
5. Comment on sub-issue #${DEV_ISSUE} with PR URL(s) when ready
6. Do NOT merge to main. Do NOT open PRs on ai-alpha-squad for product code.

After PR is merged by the Director, the orchestrator will advance the parent to \`implemented\` and dispatch validation agents automatically.
EOF
    ;;
  implemented)
    # Phase 4 fan-out runs in squad-orchestrator.yml matrix job (parallel).
    echo "implemented label — validation matrix dispatch handled by workflow"
    if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
      echo "dispatched=false" >> "$GITHUB_OUTPUT"
    fi
    exit 0
    ;;
  validation)
    export SQUAD_ALLOW_COPILOT_REASSIGN=1
    AGENT="release-manager"
    if gh issue view "$ISSUE" --repo "$REPO" --json labels -q '.labels[].name' | grep -qx 'release-candidate'; then
      echo "Parent #$ISSUE already release-candidate — skip release-manager dispatch"
      exit 0
    fi
    TARGET_REPO="$("$FIND" "$REPO" "$ISSUE" --target-repo)" || TARGET_REPO="$REPO"
    INSTRUCTIONS_FILE="$(mktemp)"
    cat > "$INSTRUCTIONS_FILE" <<EOF
You are the Release Manager for AI Alpha Squad.

Read: .agents/agent-release-manager.md and validation deliverables on issue #${ISSUE} and its sub-issues.

1. Confirm QA report, Security report, DevOps checklist, and Tech Writer release notes are complete
2. Post FULL release plan on parent issue #${ISSUE} — heading must include: # Release Plan
3. Prepare release artifacts on target repo: ${TARGET_REPO} (version, changelog, release draft PR if needed)
4. Add label release-candidate on parent #${ISSUE} when ready for Director final approval
5. Comment: Squad deliverable complete on this issue.

Do NOT merge release to production without Director approval. Orchestrator notifies Director on WhatsApp when release-candidate is added.
EOF
    DISPATCH_ISSUE="$ISSUE"
    ;;
  *)
    echo "No Copilot dispatch for label: $LABEL"
    exit 0
    ;;
esac

if [[ -n "${SQUAD_NUDGE_REASON:-}" && -n "$INSTRUCTIONS_FILE" ]]; then
  {
    echo "**Orchestrator nudge:** ${SQUAD_NUDGE_REASON}"
    echo
    cat "$INSTRUCTIONS_FILE"
  } > "${INSTRUCTIONS_FILE}.nudge"
  mv "${INSTRUCTIONS_FILE}.nudge" "$INSTRUCTIONS_FILE"
fi

export DISPATCH_LABEL="$LABEL"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"

chmod +x "$DISPATCH" \
  "${ROOT}/scripts/squad-run-hf-agent.sh" \
  "${ROOT}/scripts/squad-run-actions-agent.sh"
"$DISPATCH" "$REPO" "$DISPATCH_ISSUE" "$AGENT" "$TARGET_REPO" "$INSTRUCTIONS_FILE"
rm -f "$INSTRUCTIONS_FILE"
