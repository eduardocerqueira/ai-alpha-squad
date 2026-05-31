#!/usr/bin/env bash
# Configure GitHub Project #6 for Director pipeline visibility.
# Usage: ./scripts/setup-squad-project-board.sh [ensure-fields|sync-all|sync-issue N|print-views|setup]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OWNER="${SQUAD_PROJECT_OWNER:-eduardocerqueira}"
PROJECT="${SQUAD_PROJECT_NUMBER:-6}"
if [[ "${SQUAD_WORK_QUEUE_REPO:-ai-alpha-squad}" == */* ]]; then
  REPO="${SQUAD_WORK_QUEUE_REPO}"
else
  REPO="${GITHUB_OWNER:-eduardocerqueira}/${SQUAD_WORK_QUEUE_REPO:-ai-alpha-squad}"
fi
CMD="${1:-setup}"

if [ -n "${GITHUB_TOKEN:-}" ]; then
  export GH_TOKEN="${GITHUB_TOKEN}"
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "Run: gh auth login — or set GITHUB_TOKEN in .env" >&2
  exit 1
fi

if ! gh api graphql -f query='query { user(login: "eduardocerqueira") { projectV2(number: 6) { id } } }' >/dev/null 2>&1; then
  echo "GITHUB_TOKEN/gh auth missing read:project — add project scopes to your token." >&2
  exit 1
fi

run_py() {
  python3 "${ROOT}/scripts/squad_project_sync.py" \
    --owner "$OWNER" \
    --project "$PROJECT" \
    --repo "$REPO" \
    "$@"
}

case "$CMD" in
  ensure-fields)
    run_py ensure-fields
    ;;
  sync-all)
    run_py sync-all
    ;;
  sync-issue)
    ISSUE="${2:?issue number required}"
    run_py sync-issue "$ISSUE"
    ;;
  print-views)
    run_py print-views
    ;;
  setup)
    run_py ensure-fields
    run_py sync-all
    run_py print-views
    echo
    echo "Next: open https://github.com/users/${OWNER}/projects/${PROJECT} and add the views above."
    ;;
  *)
    echo "Usage: $0 [ensure-fields|sync-all|sync-issue N|print-views|setup]" >&2
    exit 1
    ;;
esac
