#!/usr/bin/env bash
# Smoke-test Hugging Face squad integration (router API + optional issue dispatch).
# Usage:
#   ./scripts/test-hf-integration.sh              # router only
#   ./scripts/test-hf-integration.sh <repo> <issue> <agent>  # dispatch on issue
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"

echo "== HF prerequisites =="
if command -v hf >/dev/null 2>&1; then
  hf auth whoami
else
  echo "hf CLI not in PATH (optional)"
fi

[[ -n "${HF_TOKEN:-}" ]] || {
  echo "HF_TOKEN is not set — add to .env" >&2
  exit 1
}

echo
echo "== Unit tests =="
uv run pytest tests/test_agent_models.py tests/test_hf_dispatch.py -q

echo
echo "== Router smoke test =="
uv run python -c "
from ai_alpha_squad.hf_dispatch import chat_completion
from ai_alpha_squad.agent_models import resolve_model
import os
model = resolve_model('business-owner', 'huggingface')
out = chat_completion(model, system='test', user='Reply exactly: HF_OK', token=os.environ['HF_TOKEN'])
assert 'HF_OK' in out, out
print('model:', model)
print('router: OK')
"

if [[ $# -ge 3 ]]; then
  REPO="$1"
  ISSUE="$2"
  AGENT="$3"
  echo
  echo "== Issue dispatch on ${REPO}#${ISSUE} (${AGENT}) =="
  export SQUAD_AI_PROVIDER="${SQUAD_AI_PROVIDER:-huggingface}"
  TMP="$(mktemp)"
  trap 'rm -f "$TMP"' EXIT
  cat > "$TMP" <<EOF
HF integration test. Post a minimal deliverable with heading appropriate for your role.
One sentence confirming the test passed. Do not change labels or open PRs.
EOF
  chmod +x "${ROOT}/scripts/squad-run-hf-agent.sh"
  "${ROOT}/scripts/squad-run-hf-agent.sh" "$REPO" "$ISSUE" "$AGENT" "$TMP"
  echo "See issue comments for dispatch + result markers."
fi

echo
echo "HF integration checks passed."
