#!/usr/bin/env bash
# Configure GitHub Project #6 for Director pipeline visibility.
# Usage: ./scripts/setup-squad-project-board.sh [ensure-fields|sync-all|sync-issue N|print-views|setup]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OWNER="${SQUAD_PROJECT_OWNER:-eduardocerqueira}"
PROJECT="${SQUAD_PROJECT_NUMBER:-6}"
REPO="${SQUAD_WORK_QUEUE_REPO:-eduardocerqueira/ai-alpha-squad}"
CMD="${1:-setup}"

if ! gh auth status >/dev/null 2>&1; then
  echo "Run: gh auth login" >&2
  exit 1
fi

if ! gh auth status -h github.com 2>&1 | grep -q 'read:project\|project'; then
  echo "GitHub CLI needs project scope. Run:" >&2
  echo "  gh auth refresh -s read:project,project" >&2
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
