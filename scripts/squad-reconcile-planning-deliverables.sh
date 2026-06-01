#!/usr/bin/env bash
# Wrapper for squad-reconcile-planning-deliverables.py
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
exec python3 "${ROOT}/scripts/squad-reconcile-planning-deliverables.py" "$@"
