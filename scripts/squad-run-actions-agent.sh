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

checkout_work_branch() {
  local workdir="$1"
  cd "$workdir"
  git remote set-url origin "https://x-access-token:${GH_TOKEN}@github.com/${TARGET_REPO}.git"
  if git ls-remote --heads origin "$BRANCH" | grep -q .; then
    git fetch origin "$BRANCH"
    git checkout "$BRANCH"
    git pull --rebase origin "$BRANCH" || git pull origin "$BRANCH" || true
  else
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
    -f target_repo="$TARGET_REPO" 2>/dev/null; then
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

WORKDIR="${RUNNER_TEMP:-/tmp}/squad-target-${ISSUE}-$$"
rm -rf "$WORKDIR"
configure_git_auth
git clone --depth 1 "https://github.com/${TARGET_REPO}.git" "$WORKDIR"

checkout_work_branch "$WORKDIR"

export SQUAD_ACTIONS_SKIP_DISPATCH_COMMENT=1
python3 -m ai_alpha_squad.actions_agent run \
  "$QUEUE_REPO" "$ISSUE" "$AGENT" "$TARGET_REPO" "$WORKDIR" "$INSTRUCTIONS_FILE"

PR_URL=""
if ! git diff --quiet || ! git diff --cached --quiet || [[ -n "$(git status --porcelain)" ]]; then
  git add -A
  git -c user.name="github-actions[bot]" -c user.email "github-actions[bot]@users.noreply.github.com" \
    commit -m "feat(squad): ${AGENT} work for ${QUEUE_REPO}#${ISSUE}" || true
  if ! git push -u origin "$BRANCH"; then
    echo "error: git push failed for ${TARGET_REPO} branch ${BRANCH}" >&2
    echo "Ensure SQUAD_ORCHESTRATOR_TOKEN has repo scope + contents:write on ${TARGET_REPO}." >&2
    exit 128
  fi
  PR_URL="$(ensure_pull_request)"
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
  echo "No PR was created on ${TARGET_REPO} — check issue #${ISSUE} result comment and workflow logs." >&2
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
