#!/usr/bin/env bash
# Route squad dispatch to Copilot or Hugging Face based on SQUAD_AI_PROVIDER.
# Usage: squad-dispatch-agent.sh <owner/repo> <issue_number> <lifecycle_label>
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"

PROVIDER="$(python3 -c 'from ai_alpha_squad.agent_models import resolve_provider; print(resolve_provider())')"

case "$PROVIDER" in
  huggingface)
    exec "${ROOT}/scripts/squad-dispatch-huggingface.sh" "$@"
    ;;
  copilot)
    exec "${ROOT}/scripts/squad-dispatch-copilot.sh" "$@"
    ;;
  *)
    echo "Unknown SQUAD_AI_PROVIDER: $PROVIDER" >&2
    exit 1
    ;;
esac
