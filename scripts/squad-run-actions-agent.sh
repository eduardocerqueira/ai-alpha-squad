#!/usr/bin/env bash
# Squad coding agent on GitHub Actions: clone target repo, HF tool loop, push PR.
# Usage: squad-run-actions-agent.sh <queue_repo> <issue> <agent> <target_repo> <instructions_file>
set -euo pipefail

QUEUE_REPO="${1:?queue repo required}"
ISSUE="${2:?issue required}"
AGENT="${3:?agent required}"
TARGET_REPO="${4:?target repo required}"
INSTRUCTIONS_FILE="${5:?instructions file required}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
export SQUAD_REPO_ROOT="$ROOT"
export DISPATCH_LABEL="${DISPATCH_LABEL:-$AGENT}"

SUMMARY_FILE="${RUNNER_TEMP:-/tmp}/squad-actions-summary-${ISSUE}.txt"
export SQUAD_ACTIONS_SUMMARY_FILE="$SUMMARY_FILE"

# Push/PR to target repo needs a token with contents + pull-requests on TARGET_REPO.
if [[ -z "${GH_TOKEN:-}" ]]; then
  GH_TOKEN="${GITHUB_TOKEN:-}"
  export GH_TOKEN
fi

configure_git_auth() {
  if [[ -z "${GH_TOKEN:-}" ]]; then
    echo "error: set GH_TOKEN or SQUAD_ORCHESTRATOR_TOKEN (PAT with write on ${TARGET_REPO})" >&2
    exit 1
  fi
  gh auth setup-git
}

BRANCH="$(python3 -c "from ai_alpha_squad.squad_v2 import squad_work_branch; print(squad_work_branch('$AGENT', $ISSUE))" 2>/dev/null || echo "squad/${AGENT}-issue-${ISSUE}")"
BASE_BRANCH="${SQUAD_TARGET_BASE_BRANCH:-main}"

checkout_work_branch() {
  local workdir="$1"
  cd "$workdir"
  git remote set-url origin "https://x-access-token:${GH_TOKEN}@github.com/${TARGET_REPO}.git"
  if git ls-remote --heads origin "$BRANCH" | grep -q .; then
    # Shallow clone (-b main) does not include other branches until explicitly fetched.
    git fetch --depth 1 origin "${BRANCH}:refs/heads/${BRANCH}"
    git checkout "$BRANCH"
    git pull --rebase origin "$BRANCH" || git pull origin "$BRANCH" || true
  else
    git checkout "$BASE_BRANCH"
    git checkout -b "$BRANCH"
  fi
}

ensure_pull_request() {
  local existing
  existing="$(gh pr list --repo "$TARGET_REPO" --head "$BRANCH" --state open --json url -q '.[0].url' 2>/dev/null || true)"
  if [[ -z "$existing" ]]; then
    # Reuse any open squad PR for this issue (legacy timestamp branches).
    existing="$(gh pr list --repo "$TARGET_REPO" --state open --json url,headRefName -q \
      ".[] | select(.headRefName | test(\"^squad/${AGENT}-issue-${ISSUE}\")) | .url" 2>/dev/null | head -1 || true)"
  fi
  if [[ -n "$existing" ]]; then
    echo "$existing"
    return 0
  fi
  gh pr create --repo "$TARGET_REPO" \
    --base "$BASE_BRANCH" \
    --title "[Squad ${AGENT}] Issue #${ISSUE}" \
    --body "Squad queue: ${QUEUE_REPO}#${ISSUE}

Automated PR from Squad Actions agent (\`${AGENT}\`). One branch per job — updates reuse this PR." \
    --head "$BRANCH" 2>/dev/null || true
}

# In orchestrator job, spawn dedicated workflow unless inline mode requested.
if [[ -n "${GITHUB_ACTIONS:-}" && "${SQUAD_ACTIONS_INLINE:-}" != "1" ]]; then
  REPO_FOR_WF="${GITHUB_REPOSITORY:-$QUEUE_REPO}"
  if gh workflow run squad-actions-agent.yml \
    --repo "$REPO_FOR_WF" \
    -f queue_repo="$QUEUE_REPO" \
    -f issue_number="$ISSUE" \
    -f agent="$AGENT" \
    -f target_repo="$TARGET_REPO" \
    -f model="${SQUAD_AGENT_MODEL_OVERRIDE:-}" 2>/dev/null; then
    if [[ "${SQUAD_V2:-}" == "1" ]]; then
      MARKER="$(python3 -c "from ai_alpha_squad.squad_v2 import in_progress_comment; print(in_progress_comment('${AGENT}'))")"
      gh issue comment "$ISSUE" --repo "$QUEUE_REPO" --body "$MARKER" 2>/dev/null || true
    fi
    echo "Triggered squad-actions-agent workflow for $AGENT on $QUEUE_REPO#$ISSUE"
    if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
      echo "dispatched=true" >> "$GITHUB_OUTPUT"
      echo "agent=$AGENT" >> "$GITHUB_OUTPUT"
      echo "provider=actions" >> "$GITHUB_OUTPUT"
    fi
    exit 0
  fi
  echo "workflow dispatch failed — running inline (SQUAD_ACTIONS_INLINE fallback)" >&2
fi

# Escalate a non-retryable setup/permission problem to the Director and stop
# WITHOUT consuming a retry attempt (exit 0 so the wrapper posts no failed marker).
escalate_setup_failure() {
  local reason="$1"
  echo "error: setup failure — ${reason}" >&2
  if [[ "${SQUAD_V2:-}" == "1" ]]; then
    gh issue edit "$ISSUE" --repo "$QUEUE_REPO" --add-label blocked 2>/dev/null || true
    local marker
    marker="$(python3 -c "from ai_alpha_squad.squad_v2 import setup_failed_comment; print(setup_failed_comment('${AGENT}', '''${reason}'''))" 2>/dev/null \
      || echo "squad-v2-run:setup-failed:${AGENT} — ${reason}")"
    gh issue comment "$ISSUE" --repo "$QUEUE_REPO" --body "$marker" 2>/dev/null || true
  fi
  exit 0
}

WORKDIR="${RUNNER_TEMP:-/tmp}/squad-target-${ISSUE}-$$"
rm -rf "$WORKDIR"
configure_git_auth

# Pre-flight (cheap, before the expensive agent loop): fail fast on setup problems
# that retries cannot fix, rather than burning the retry budget on full agent runs.
PUSH_PERM="$(gh api "repos/${TARGET_REPO}" --jq '.permissions.push' 2>/dev/null || echo "unknown")"
if [[ "$PUSH_PERM" == "false" ]]; then
  escalate_setup_failure "the squad token lacks push (contents:write) access to ${TARGET_REPO}"
fi
if ! git ls-remote --heads "https://x-access-token:${GH_TOKEN}@github.com/${TARGET_REPO}.git" "$BASE_BRANCH" | grep -q .; then
  escalate_setup_failure "target repo ${TARGET_REPO} has no ${BASE_BRANCH} branch — create it before dispatching squad work"
fi
git clone --depth 1 -b "$BASE_BRANCH" "https://github.com/${TARGET_REPO}.git" "$WORKDIR"

checkout_work_branch "$WORKDIR"

if [[ "${SQUAD_V2:-}" == "1" ]]; then
  MARKER="$(python3 -c "from ai_alpha_squad.squad_v2 import in_progress_comment; print(in_progress_comment('${AGENT}'))")"
  gh issue comment "$ISSUE" --repo "$QUEUE_REPO" --body "$MARKER" 2>/dev/null || true
fi

export SQUAD_ACTIONS_SKIP_DISPATCH_COMMENT=1
python3 -m ai_alpha_squad.actions_agent run \
  "$QUEUE_REPO" "$ISSUE" "$AGENT" "$TARGET_REPO" "$WORKDIR" "$INSTRUCTIONS_FILE"

# Stall abort → escalate developer model before the compile gate (next run uses stronger model).
if [[ "${SQUAD_V2:-}" == "1" && "$AGENT" == "developer" && -f "$SUMMARY_FILE" ]]; then
  ESC_MARKER="$(python3 <<PY || true
import json, os, subprocess, sys
sys.path.insert(0, "${ROOT}/src")
from ai_alpha_squad.squad_dev_summary import is_stall_abort_summary
from ai_alpha_squad.squad_v2 import dev_model_ladder, stall_model_escalation_body

summary = open("${SUMMARY_FILE}", encoding="utf-8").read()
if not is_stall_abort_summary(summary):
    raise SystemExit(0)
data = json.loads(subprocess.check_output(
    ["gh", "issue", "view", str(${ISSUE}), "--repo", "${QUEUE_REPO}", "--json", "comments"],
    text=True,
))
comments = tuple(data.get("comments") or ())
body = stall_model_escalation_body(comments, dev_model_ladder(os.environ.get("SQUAD_DEV_MODEL_LADDER")))
if body:
    print(body)
PY
)"
  if [[ -n "${ESC_MARKER:-}" ]]; then
    gh issue comment "$ISSUE" --repo "$QUEUE_REPO" --body "$ESC_MARKER" 2>/dev/null || true
    echo "Posted stall model escalation for developer on #${ISSUE}"
  fi
fi

# Mandatory compile gate for developer/devops when the repo has a build tool.
BUILD_VERIFIED=0
if [[ "$AGENT" == "developer" || "$AGENT" == "devops" ]]; then
  ISSUE_BODY="$(gh issue view "$ISSUE" --repo "$QUEUE_REPO" --json body -q .body 2>/dev/null || true)"
  BUILD_LOG="${RUNNER_TEMP:-/tmp}/squad-build-verify-${ISSUE}.log"
  if ! python3 -m ai_alpha_squad.target_build_verify workdir "$WORKDIR" "$ISSUE_BODY" 2>"$BUILD_LOG"; then
    echo "error: build verification failed on ${TARGET_REPO} before commit" >&2
    COMMENT="$(python3 -c "
from ai_alpha_squad.target_build_verify import format_build_failure_issue_comment
import sys
print(format_build_failure_issue_comment('${AGENT}', open(sys.argv[1], encoding='utf-8').read()))
" "$BUILD_LOG")"
    gh issue comment "$ISSUE" --repo "$QUEUE_REPO" --body "$COMMENT" 2>/dev/null || true
    exit 1
  fi
  BUILD_VERIFIED=1
fi

# Safety gate: reject destructive rewrites (agent deleting most of a file / dropping
# public functions) before they become a PR. Retryable failure so the cap applies.
SAFETY_VIOLATIONS="$(cd "$WORKDIR" && python3 -m ai_alpha_squad.actions_agent check-changes "$WORKDIR" 2>/dev/null)" || {
  echo "error: developer change failed the destructive-edit safety check on ${TARGET_REPO}" >&2
  printf '%s\n' "$SAFETY_VIOLATIONS" >&2
  gh issue comment "$ISSUE" --repo "$QUEUE_REPO" --body "**Squad developer — change rejected by safety check.** The proposed edit on \`${TARGET_REPO}\` looks destructive (likely a file rewrite that drops existing code), so no PR was opened:

\`\`\`
${SAFETY_VIOLATIONS}
\`\`\`
Re-run after the agent makes a *targeted* change." 2>/dev/null || true
  exit 1
}

# Completeness backstop: if the task enumerates N files to create, a partial
# result (e.g. the agent hit max turns) must not become a finished deliverable.
# Checks the named files exist (committed or not) against the issue body.
INCOMPLETE_MSG="$(python3 -m ai_alpha_squad.actions_agent check-complete "$WORKDIR" "$QUEUE_REPO" "$ISSUE" 2>/dev/null)" && COMPLETE=1 || COMPLETE=0

if ! git diff --quiet || ! git diff --cached --quiet || [[ -n "$(git status --porcelain)" ]]; then
  # Drop ignored build artifacts (e.g. Maven target/) before staging — compile
  # verification runs above but must not ship build output in the PR (#178).
  git clean -fdX 2>/dev/null || true
  git add -A
  git -c 'user.name=github-actions[bot]' \
    -c 'user.email=github-actions[bot]@users.noreply.github.com' \
    commit -m "feat(squad): ${AGENT} work for ${QUEUE_REPO}#${ISSUE}" || true
  if ! git push -u origin "$BRANCH"; then
    git fetch origin "$BRANCH" 2>/dev/null || true
    if ! git pull --rebase origin "$BRANCH" 2>/dev/null && ! git pull origin "$BRANCH" 2>/dev/null; then
      echo "error: git push failed for ${TARGET_REPO} branch ${BRANCH} (rebase/pull also failed)" >&2
      echo "Ensure SQUAD_ORCHESTRATOR_TOKEN has repo scope + contents:write on ${TARGET_REPO}." >&2
      exit 128
    fi
    if ! git push -u origin "$BRANCH"; then
      echo "error: git push failed for ${TARGET_REPO} branch ${BRANCH} after rebase" >&2
      exit 128
    fi
  fi
fi

# Resolve the PR for this branch (existing or newly created) regardless of whether
# THIS run added commits: an idempotent re-run on a branch that already has work
# still has an open PR, and that PR is the deliverable.
PR_URL="$(ensure_pull_request)"

# Replace abort/churn summary when compile gate passed (#178).
if [[ "$AGENT" == "developer" && "${BUILD_VERIFIED:-0}" == "1" && -f "$SUMMARY_FILE" ]]; then
  python3 <<PY
from ai_alpha_squad.squad_dev_summary import sanitize_developer_summary
from pathlib import Path
p = Path("${SUMMARY_FILE}")
text = sanitize_developer_summary(p.read_text(encoding="utf-8"), build_verified=True, pr_url="${PR_URL:-}")
p.write_text(text + "\n", encoding="utf-8")
PY
fi

# If the work is incomplete, preserve progress on the branch but do NOT finalize —
# posting no deliverable keeps the issue out of release-candidate. The failure is
# retryable; a re-run continues from the pushed branch (idempotent).
if [[ "${COMPLETE:-1}" == "0" ]]; then
  echo "error: incomplete deliverable — ${INCOMPLETE_MSG}" >&2
  gh issue comment "$ISSUE" --repo "$QUEUE_REPO" --body "**Squad developer — incomplete, not finalized.** ${INCOMPLETE_MSG}. Progress was pushed to \`${BRANCH}\`${PR_URL:+ (PR ${PR_URL})}; a re-run will continue from there." 2>/dev/null || true
  exit 1
fi

export SQUAD_V2="${SQUAD_V2:-}"
python3 -m ai_alpha_squad.actions_agent finalize \
  "$QUEUE_REPO" "$ISSUE" "$AGENT" "$SUMMARY_FILE" "${PR_URL:-}"

# Director visibility: dashboard (site/director); issue comments opt-in only.
if [[ -n "$PR_URL" ]] && [[ "${SQUAD_DIRECTOR_STATUS_COMMENTS:-0}" == "1" ]]; then
  chmod +x "${ROOT}/scripts/squad-post-director-status.sh"
  ./scripts/squad-post-director-status.sh "$QUEUE_REPO" "$ISSUE" \
    --agent "$AGENT" --pr-url "$PR_URL" --target-repo "$TARGET_REPO" || true
fi

if [[ -n "$PR_URL" ]]; then
  chmod +x "${ROOT}/scripts/squad-director-dashboard.py"
  python3 "${ROOT}/scripts/squad-director-dashboard.py" --write "${ROOT}/site/public/director/jobs.json" || true
fi

if [[ -z "$PR_URL" ]]; then
  # No PR exists and none could be created (the agent produced no committable
  # work, e.g. it churned on reads or hit max turns). The deliverable heading is
  # only posted with a PR, so has_deliverable stays false. Exit non-zero so the
  # caller records a failure marker and the retry cap engages — otherwise the
  # orchestrator would re-dispatch this no-op run on every tick, forever.
  echo "error: no PR on ${TARGET_REPO} for ${BRANCH} — agent produced no changes; treating as failure" >&2
  echo "See issue #${ISSUE} agent result comment and workflow logs for the agent's summary." >&2
  exit 1
fi

if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  echo "dispatched=true" >> "$GITHUB_OUTPUT"
  echo "agent=$AGENT" >> "$GITHUB_OUTPUT"
  echo "provider=actions" >> "$GITHUB_OUTPUT"
  [[ -n "$PR_URL" ]] && echo "pr_url=$PR_URL" >> "$GITHUB_OUTPUT"
fi

echo "Actions agent complete for $AGENT on $QUEUE_REPO#$ISSUE (branch ${BRANCH}, PR ${PR_URL})"
rm -rf "$WORKDIR"
exit 0
