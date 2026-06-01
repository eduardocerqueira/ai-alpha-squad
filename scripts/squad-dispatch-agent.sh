#!/usr/bin/env bash
# Route squad lifecycle dispatch (HF / Actions / legacy Copilot per agent).
# Usage: squad-dispatch-agent.sh <owner/repo> <issue_number> <lifecycle_label>
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"

# Lifecycle labels share one script; per-issue routing is in squad-dispatch-subissue.sh.
exec "${ROOT}/scripts/squad-dispatch-copilot.sh" "$@"
