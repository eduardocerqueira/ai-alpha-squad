#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE' >&2
Usage:
  squad-label.sh --repo owner/name --issue <number> [--add label1,label2] [--remove label3,label4] [--dry-run]

Apply label transitions on a GitHub issue. Requires gh CLI authentication.
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
  [[ "$v" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || die "--repo must be in 'owner/name' format"
}

validate_issue() {
  local v="$1"
  [[ "$v" =~ ^[0-9]+$ ]] || die "--issue must be a numeric value"
}

validate_label() {
  local label="$1"
  [[ "$label" =~ ^[A-Za-z0-9][A-Za-z0-9 ._/-]*$ ]] || die "Invalid label value: $label"
}

parse_labels() {
  local raw="$1"
  local -n out_ref="$2"
  local token

  IFS=',' read -r -a parts <<<"$raw"
  for token in "${parts[@]}"; do
    token="$(trim "$token")"
    [[ -n "$token" ]] || continue
    validate_label "$token"
    out_ref+=("$token")
  done
}

dedupe_labels() {
  local -n in_ref="$1"
  local -n out_ref="$2"
  local item
  declare -A seen=()

  for item in "${in_ref[@]}"; do
    if [[ -z "${seen[$item]:-}" ]]; then
      seen["$item"]=1
      out_ref+=("$item")
    fi
  done
}

REPO=""
ISSUE=""
ADD_RAW=""
REMOVE_RAW=""
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
    --add)
      [[ $# -ge 2 ]] || die "--add requires a comma-separated value"
      ADD_RAW="$2"
      shift 2
      ;;
    --remove)
      [[ $# -ge 2 ]] || die "--remove requires a comma-separated value"
      REMOVE_RAW="$2"
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

add_labels=()
remove_labels=()
deduped_add=()
deduped_remove=()

parse_labels "$ADD_RAW" add_labels
parse_labels "$REMOVE_RAW" remove_labels

dedupe_labels add_labels deduped_add
dedupe_labels remove_labels deduped_remove

if [[ ${#deduped_add[@]} -eq 0 && ${#deduped_remove[@]} -eq 0 ]]; then
  die "At least one --add or --remove label is required"
fi

require_cmd gh

run_or_echo() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '[dry-run]'
    printf ' %q' "$@"
    printf '\n'
  else
    "$@"
  fi
}

for label in "${deduped_add[@]}"; do
  run_or_echo gh issue edit "$ISSUE" --repo "$REPO" --add-label "$label"
done

for label in "${deduped_remove[@]}"; do
  run_or_echo gh issue edit "$ISSUE" --repo "$REPO" --remove-label "$label"
done

if [[ "$DRY_RUN" -eq 0 ]]; then
  printf 'Updated labels for %s#%s\n' "$REPO" "$ISSUE"
fi
