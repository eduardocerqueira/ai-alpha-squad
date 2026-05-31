#!/usr/bin/env bash
# Install squad-notify-queue workflow on a target product repo.
# Usage: install-target-repo-orchestrator-hook.sh <target_repo> [queue_repo]
set -euo pipefail

TARGET="${1:?target owner/repo e.g. eduardocerqueira/seeker}"
QUEUE="${2:-eduardocerqueira/ai-alpha-squad}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATE="${ROOT}/.agents/templates/target-repo-squad-notify.yml"
DEST=".github/workflows/squad-notify-queue.yml"

if [ ! -f "$TEMPLATE" ]; then
  echo "Missing template: $TEMPLATE"
  exit 1
fi

TMP="$(mktemp)"
cp "$TEMPLATE" "$TMP"

if ! gh api "repos/${TARGET}/contents/${DEST}" --jq .sha 2>/dev/null; then
  gh api --method PUT "repos/${TARGET}/contents/${DEST}" \
    -f message="chore: add squad queue notify workflow" \
    -f content="$(base64 < "$TMP" | tr -d '\n')" \
    -f "branch=main" 2>/dev/null || {
      echo "Could not commit workflow to $TARGET — add manually from .agents/templates/target-repo-squad-notify.yml"
      rm -f "$TMP"
      exit 1
    }
  echo "Installed $DEST on $TARGET"
else
  echo "$DEST already exists on $TARGET"
fi
rm -f "$TMP"

echo ""
echo "Set on $TARGET:"
echo "  Variable SQUAD_QUEUE_REPO=$QUEUE"
echo "  Secret SQUAD_ORCHESTRATOR_TOKEN (PAT with repo + workflow on queue repo)"
