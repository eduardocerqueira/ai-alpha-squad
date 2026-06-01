#!/usr/bin/env bash
# Post Director job status on parent issue and sync GitHub Project fields.
# Usage: squad-post-director-status.sh <queue_repo> <issue> [--agent A] [--pr-url URL] [--target-repo R]
set -euo pipefail

QUEUE_REPO="${1:?queue repo}"
ISSUE="${2:?issue}"
shift 2

AGENT=""
PR_URL=""
TARGET_REPO=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --agent) AGENT="${2:-}"; shift 2 ;;
    --pr-url) PR_URL="${2:-}"; shift 2 ;;
    --target-repo) TARGET_REPO="${2:-}"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
export SQUAD_REPO_ROOT="$ROOT"
export QUEUE_REPO ISSUE PR_URL TARGET_REPO
export SQUAD_STATUS_AGENT="$AGENT"
python3 -c "
import os
from ai_alpha_squad.director_visibility import post_director_status, sync_project_family

repo = os.environ['QUEUE_REPO']
issue = int(os.environ['ISSUE'])
parent = post_director_status(
    repo,
    issue,
    agent=os.environ.get('SQUAD_STATUS_AGENT', ''),
    pr_url=os.environ.get('PR_URL', ''),
    target_repo=os.environ.get('TARGET_REPO', ''),
)
sync_project_family(repo, parent)
print(f'Director status posted on #{parent}; project synced for family.')
"

if [[ -n "$PR_URL" ]]; then
  chmod +x "${ROOT}/scripts/notify-director-lifecycle.sh"
  ./scripts/notify-director-lifecycle.sh "developer-pr-ready" "$ISSUE" "$QUEUE_REPO" "PR: $PR_URL" || true
fi
