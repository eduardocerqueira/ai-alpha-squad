#!/usr/bin/env bash
# Configure main-branch protection for ai-alpha-squad without blocking squad automation.
# Squad workflows (orchestrator, director-gate, phase-watch, copilot-pr-guard) only
# touch issues and pull requests — they never push to main.
#
# Usage:
#   ./scripts/setup-branch-protection.sh                    # PR-only gate (solo Director)
#   ./scripts/setup-branch-protection.sh --require-ci       # also require ci-test check
#   ./scripts/setup-branch-protection.sh --require-review   # require 1 approving review
#
# After merging .github/workflows/ci.yml to main, re-run with --require-ci.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

REPO="${GITHUB_REPOSITORY:-eduardocerqueira/ai-alpha-squad}"
RULESET_NAME="Protect main (AI Alpha Squad)"
REQUIRE_CI=false
REQUIRE_REVIEW=false

for arg in "$@"; do
  case "$arg" in
    --require-ci) REQUIRE_CI=true ;;
    --require-review) REQUIRE_REVIEW=true ;;
    -h|--help)
      sed -n '2,12p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown option: $arg" >&2
      exit 1
      ;;
  esac
done

if ! gh auth status >/dev/null 2>&1; then
  echo "Run: gh auth login" >&2
  exit 1
fi

REVIEW_COUNT=0
if [ "$REQUIRE_REVIEW" = true ]; then
  REVIEW_COUNT=1
fi

RULES='[
  {"type": "deletion"},
  {"type": "non_fast_forward"},
  {
    "type": "pull_request",
    "parameters": {
      "required_approving_review_count": '"$REVIEW_COUNT"',
      "dismiss_stale_reviews_on_push": true,
      "require_code_owner_review": false,
      "require_last_push_approval": false,
      "required_review_thread_resolution": false
    }
  }
]'

if [ "$REQUIRE_CI" = true ]; then
  RULES="$(python3 -c '
import json, sys
rules = json.loads(sys.argv[1])
rules.append({
    "type": "required_status_checks",
    "parameters": {
        "strict_required_status_checks_policy": true,
        "required_status_checks": [{"context": "ci-test"}],
    },
})
print(json.dumps(rules))
' "$RULES")"
fi

PAYLOAD="$(RULES_JSON="$RULES" RULESET_NAME="$RULESET_NAME" python3 -c '
import json, os
rules = json.loads(os.environ["RULES_JSON"])
payload = {
    "name": os.environ["RULESET_NAME"],
    "target": "branch",
    "enforcement": "active",
    "conditions": {
        "ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []},
    },
    "rules": rules,
}
print(json.dumps(payload))
' )"

export RULESET_NAME="$RULESET_NAME"

EXISTING_ID="$(gh api "repos/${REPO}/rulesets" --jq ".[] | select(.name == \"${RULESET_NAME}\") | .id" 2>/dev/null | head -1 || true)"

if [ -n "$EXISTING_ID" ]; then
  echo "Updating ruleset id=${EXISTING_ID} on ${REPO} …"
  gh api --method PUT "repos/${REPO}/rulesets/${EXISTING_ID}" --input - <<<"$PAYLOAD" >/dev/null
else
  echo "Creating ruleset on ${REPO} …"
  gh api --method POST "repos/${REPO}/rulesets" --input - <<<"$PAYLOAD" >/dev/null
fi

echo ""
echo "Main branch protection applied on ${REPO}."
echo "  • Pull request required before merge"
echo "  • Force push and branch deletion blocked"
echo "  • Required approving reviews: ${REVIEW_COUNT}"
if [ "$REQUIRE_CI" = true ]; then
  echo "  • Required status check: ci-test"
else
  echo "  • Status checks: none (run with --require-ci after CI workflow is on main)"
fi
echo ""
echo "Squad automation unaffected — see docs/branch-protection.md"
