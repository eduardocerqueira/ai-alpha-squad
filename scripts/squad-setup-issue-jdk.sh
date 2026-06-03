#!/usr/bin/env bash
# Read JDK major version from a squad issue body (e.g. Java 25 → 25).
# When GITHUB_OUTPUT is set, writes java-version= for actions/setup-java.
# Usage: squad-setup-issue-jdk.sh <queue_repo> <issue_number>
set -euo pipefail

REPO="${1:?queue repo}"
ISSUE="${2:?issue number}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"

BODY="$(gh issue view "$ISSUE" --repo "$REPO" --json body -q .body 2>/dev/null || true)"
VER="$(python3 -c "
from ai_alpha_squad.target_build_verify import jdk_version_from_issue
import sys
print(jdk_version_from_issue(sys.argv[1]) or '')
" "$BODY")"

if [[ -z "$VER" ]]; then
  echo "No JDK version in issue #${ISSUE} body — using runner default Java"
  exit 0
fi

echo "Issue #${ISSUE} requests JDK ${VER}"
if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
  echo "java-version=${VER}" >> "$GITHUB_OUTPUT"
fi
