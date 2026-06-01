#!/usr/bin/env bash
# Build lifecycle instructions and dispatch via Hugging Face (same phases as Copilot).
# Usage: squad-dispatch-huggingface.sh <owner/repo> <issue_number> <lifecycle_label>
set -euo pipefail

# Reuse instruction templates from the Copilot script, then run HF inference instead of assign API.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export SQUAD_DISPATCH_PROVIDER=huggingface
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"

# squad-dispatch-copilot.sh exits before Copilot assign when provider is huggingface (see end of file).
exec "${ROOT}/scripts/squad-dispatch-copilot.sh" "$@"
