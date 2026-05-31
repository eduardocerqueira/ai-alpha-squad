#!/usr/bin/env bash
# Sync GitHub CLI token (with project scopes) to SQUAD_ORCHESTRATOR_TOKEN and run project setup.
#
# Usage:
#   unset GITHUB_TOKEN
#   gh auth refresh -s read:project,project,repo,workflow
#   ./scripts/setup-squad-project-github.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO="${1:-${GITHUB_OWNER:-eduardocerqueira}/${SQUAD_WORK_QUEUE_REPO:-ai-alpha-squad}}"

if [[ -n "${GITHUB_TOKEN:-}" ]]; then
  export GH_TOKEN="${GITHUB_TOKEN}"
elif ! gh auth status >/dev/null 2>&1; then
  echo "Run: gh auth login — or set GITHUB_TOKEN in .env" >&2
  exit 1
fi

if ! gh api graphql -f query='query { user(login: "eduardocerqueira") { projectV2(number: 6) { id } } }' >/dev/null 2>&1; then
  echo "Token missing read:project. Add project scopes to GITHUB_TOKEN or run:" >&2
  echo "  gh auth refresh -s read:project,project,repo,workflow" >&2
  exit 1
fi

TOKEN="${GH_TOKEN:-$(gh auth token)}"
echo "Updating SQUAD_ORCHESTRATOR_TOKEN on $REPO (project scopes)..."
printf '%s' "$TOKEN" | gh secret set SQUAD_ORCHESTRATOR_TOKEN --repo "$REPO"

echo "Running project board setup..."
"${ROOT}/scripts/setup-squad-project-board.sh" setup

echo "Done. Add view tabs in https://github.com/users/eduardocerqueira/projects/6 (see docs/director-project-board.md)."
