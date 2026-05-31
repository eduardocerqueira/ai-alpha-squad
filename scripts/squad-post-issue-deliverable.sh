#!/usr/bin/env bash
# Post a planning deliverable (# Business Analysis / # Technical Specification) on an issue.
# Usage: squad-post-issue-deliverable.sh <owner/repo> <issue> <marker> <markdown_file>
# Example: squad-post-issue-deliverable.sh eduardocerqueira/ai-alpha-squad 17 "Business Analysis" ba.md
set -euo pipefail

REPO="${1:?owner/repo required}"
ISSUE="${2:?issue number required}"
MARKER="${3:?marker name required (Business Analysis or Technical Specification)}"
FILE="${4:?markdown file required}"

if [[ ! -f "$FILE" ]]; then
  echo "Missing file: $FILE" >&2
  exit 1
fi

BODY="$(cat "$FILE")"
if ! grep -q "^# ${MARKER}" <<<"$BODY"; then
  echo "File must start with '# ${MARKER}'" >&2
  exit 1
fi

gh issue comment "$ISSUE" --repo "$REPO" --body "$BODY"
echo "Posted # ${MARKER} on issue #${ISSUE}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
chmod +x "${ROOT}/scripts/squad-sync-planning-labels.sh"
"${ROOT}/scripts/squad-sync-planning-labels.sh" "$REPO" "$ISSUE" || true

case "$MARKER" in
  "Business Analysis")
    gh issue comment "$ISSUE" --repo "$REPO" --body "Squad deliverable complete on this issue."
    ;;
esac
