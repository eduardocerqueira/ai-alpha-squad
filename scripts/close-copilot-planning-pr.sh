#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE' >&2
Usage:
  close-copilot-planning-pr.sh --repo owner/name --pr <number> --issue <number> [--reason <text>] [--dry-run]

Close a Copilot planning PR in ai-alpha-squad once issue-first deliverable is posted.
USAGE
}

die() {
  printf 'Error: %s\n' "$*" >&2
  exit 2
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

trim() {
  local s="$1"
  # shellcheck disable=SC2001
  s="$(printf '%s' "$s" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
  printf '%s' "$s"
}

validate_repo() {
  local v="$1"
  [[ "$v" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || die "Invalid repo '$v' (expected owner/name)"
}

validate_number() {
  local name="$1"
  local v="$2"
  [[ "$v" =~ ^[0-9]+$ ]] || die "Invalid ${name} '$v' (expected numeric)"
}

REPO=""
PR_NUMBER=""
ISSUE_NUMBER=""
REASON=""
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      [[ $# -ge 2 ]] || die "--repo requires a value"
      REPO="$(trim "$2")"
      shift 2
      ;;
    --pr)
      [[ $# -ge 2 ]] || die "--pr requires a value"
      PR_NUMBER="$(trim "$2")"
      shift 2
      ;;
    --issue)
      [[ $# -ge 2 ]] || die "--issue requires a value"
      ISSUE_NUMBER="$(trim "$2")"
      shift 2
      ;;
    --reason)
      [[ $# -ge 2 ]] || die "--reason requires a value"
      REASON="$(trim "$2")"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage
      die "Unknown argument: $1"
      ;;
  esac
done

[[ -n "$REPO" ]] || die "--repo is required"
[[ -n "$PR_NUMBER" ]] || die "--pr is required"
[[ -n "$ISSUE_NUMBER" ]] || die "--issue is required"

validate_repo "$REPO"
validate_number "pr" "$PR_NUMBER"
validate_number "issue" "$ISSUE_NUMBER"

require_cmd gh

if [[ -z "$REASON" ]]; then
  REASON="Issue-first deliverable is now on issue #${ISSUE_NUMBER}; closing planning PR."
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  printf '[dry-run] gh pr comment %q --repo %q --body %q\n' "$PR_NUMBER" "$REPO" "$REASON"
  printf '[dry-run] gh pr close %q --repo %q\n' "$PR_NUMBER" "$REPO"
else
  gh pr comment "$PR_NUMBER" --repo "$REPO" --body "$REASON" >/dev/null
  gh pr close "$PR_NUMBER" --repo "$REPO" >/dev/null
  printf 'Closed PR %s in %s\n' "$PR_NUMBER" "$REPO"
fi
