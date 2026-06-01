#!/usr/bin/env bash
# Run Hugging Face inference for a squad agent and post results on the issue.
# Usage: squad-run-hf-agent.sh <repo> <issue> <agent> <instructions_file>
set -euo pipefail

REPO="${1:?repo required}"
ISSUE="${2:?issue required}"
AGENT="${3:?agent required}"
INSTRUCTIONS_FILE="${4:?instructions file required}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
export DISPATCH_LABEL="${DISPATCH_LABEL:-$AGENT}"

if python3 -m ai_alpha_squad.hf_dispatch "$REPO" "$ISSUE" "$AGENT" "$INSTRUCTIONS_FILE"; then
  if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
    echo "dispatched=true" >> "$GITHUB_OUTPUT"
    echo "agent=$AGENT" >> "$GITHUB_OUTPUT"
    echo "provider=huggingface" >> "$GITHUB_OUTPUT"
  fi
  echo "HF dispatch complete for $AGENT on $REPO#$ISSUE"
  exit 0
fi

if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  echo "dispatched=false" >> "$GITHUB_OUTPUT"
fi
exit 1
