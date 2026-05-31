#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE' >&2
Usage:
  squad-delivery-complete.sh --repo owner/name --issue <number> [--dry-run]

Posts the standard completion comment on a GitHub issue:
  Squad deliverable complete on this issue.
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

validate_issue() {
  local v="$1"
  [[ "$v" =~ ^[0-9]+$ ]] || die "Invalid issue '$v' (expected numeric)"
}

REPO=""
ISSUE=""
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      [[ $# -ge 2 ]] || die "--repo requires a value"
      REPO="$(trim "$2")"
      shift 2
      ;;
    --issue)
      [[ $# -ge 2 ]] || die "--issue requires a value"
      ISSUE="$(trim "$2")"
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
[[ -n "$ISSUE" ]] || die "--issue is required"

validate_repo "$REPO"
validate_issue "$ISSUE"

require_cmd gh

body='Squad deliverable complete on this issue.'

if [[ "$DRY_RUN" -eq 1 ]]; then
  printf '[dry-run] gh issue comment %q --repo %q --body %q\n' "$ISSUE" "$REPO" "$body"
else
  gh issue comment "$ISSUE" --repo "$REPO" --body "$body" >/dev/null
  printf 'Posted delivery completion comment to %s#%s\n' "$REPO" "$ISSUE"
fi
