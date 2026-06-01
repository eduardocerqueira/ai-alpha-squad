#!/usr/bin/env bash
# Smoke-test Squad Actions agent routing (no live HF or git push).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"

echo "== Unit tests =="
uv run pytest tests/test_dispatch_routing.py tests/test_actions_agent.py -q

echo "== Dispatch mode (default env) =="
python3 -c "
from ai_alpha_squad.agent_models import resolve_code_runtime, resolve_dispatch_mode
print('code_runtime:', resolve_code_runtime())
for a in ('business-owner', 'developer', 'qa'):
    print(a, '->', resolve_dispatch_mode(a))
"

echo "Actions agent integration checks passed."
