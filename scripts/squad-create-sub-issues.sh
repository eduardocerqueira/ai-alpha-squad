#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE' >&2
Usage:
  squad-create-sub-issues.sh --repo owner/name --parent-issue <number> --target-repo owner/name --spec-link <url>
                            [--title-prefix "[Job X]"] [--dry-run]

Creates five role-specific sub-issues (Developer, QA, Security, DevOps, Tech Writer)
and links them to the parent issue/spec.
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
  [[ "$v" =~ ^[0-9]+$ ]] || die "Invalid parent issue '$v' (expected numeric)"
}

validate_url() {
  local v="$1"
  [[ "$v" =~ ^https?://[^[:space:]]+$ ]] || die "Invalid URL '$v'"
}

REPO=""
PARENT_ISSUE=""
TARGET_REPO=""
SPEC_LINK=""
TITLE_PREFIX=""
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      [[ $# -ge 2 ]] || die "--repo requires a value"
      REPO="$(trim "$2")"
      shift 2
      ;;
    --parent-issue)
      [[ $# -ge 2 ]] || die "--parent-issue requires a value"
      PARENT_ISSUE="$(trim "$2")"
      shift 2
      ;;
    --target-repo)
      [[ $# -ge 2 ]] || die "--target-repo requires a value"
      TARGET_REPO="$(trim "$2")"
      shift 2
      ;;
    --spec-link)
      [[ $# -ge 2 ]] || die "--spec-link requires a value"
      SPEC_LINK="$(trim "$2")"
      shift 2
      ;;
    --title-prefix)
      [[ $# -ge 2 ]] || die "--title-prefix requires a value"
      TITLE_PREFIX="$(trim "$2")"
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
[[ -n "$PARENT_ISSUE" ]] || die "--parent-issue is required"
[[ -n "$TARGET_REPO" ]] || die "--target-repo is required"
[[ -n "$SPEC_LINK" ]] || die "--spec-link is required"

validate_repo "$REPO"
validate_repo "$TARGET_REPO"
validate_issue "$PARENT_ISSUE"
validate_url "$SPEC_LINK"

require_cmd gh

mk_body() {
  local role="$1"
  local objective="$2"
  local scope_a="$3"
  local scope_b="$4"
  local deliverable_a="$5"
  local deliverable_b="$6"
  local deliverable_c="$7"
  local dependency="$8"
  local ac_when="$9"
  local ac_then="${10}"
  local notes="${11}"

  cat <<BODY
# ${role} Sub-Issue — ${TITLE_PREFIX:+$TITLE_PREFIX }${role} handoff

## Parent

- Parent issue: https://github.com/${REPO}/issues/${PARENT_ISSUE}
- Spec reference: ${SPEC_LINK}
- Target repo: ${TARGET_REPO}

## Objective

${objective}

## Scope

- ${scope_a}
- ${scope_b}

## Deliverables Checklist

- [ ] ${deliverable_a}
- [ ] ${deliverable_b}
- [ ] ${deliverable_c}

## Dependencies

- ${dependency}

## Acceptance Criteria

```gherkin
Given parent issue #${PARENT_ISSUE} is in designed phase
When ${ac_when}
Then ${ac_then}
```

## Handoff Notes

${notes}
BODY
}

create_issue() {
  local title="$1"
  local body="$2"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf '[dry-run] gh issue create --repo %q --title %q --body-file <(generated)\n' "$REPO" "$title"
    printf -- '---- body start (%s) ----\n%s\n---- body end ----\n' "$title" "$body"
  else
    local tmp
    tmp="$(mktemp)"
    printf '%s' "$body" >"$tmp"
    gh issue create --repo "$REPO" --title "$title" --body-file "$tmp" >/dev/null
    rm -f "$tmp"
    printf 'Created sub-issue: %s\n' "$title"
  fi
}

create_issue \
  "${TITLE_PREFIX:+$TITLE_PREFIX }Developer — implement extension core" \
  "$(mk_body \
     "Developer" \
     "Implement the VS Code extension core in target repo per approved tech spec." \
     "Commands, TreeDataProvider, status bar wiring, and approve action" \
     "GitHub auth/SecretStorage integration and lifecycle grouping" \
     "Feature-complete PR linked to parent issue" \
     "Unit + extension-host tests for key flows" \
     "Docs updates in target repo README/changelog as applicable" \
     "Tech Spec comment and parent issue #${PARENT_ISSUE}" \
     "Developer submits implementation PR in ${TARGET_REPO}" \
     "implementation maps to FR IDs and passes CI" \
     "No planning artifacts in ai-alpha-squad; implementation only in target repo." \
   )"

create_issue \
  "${TITLE_PREFIX:+$TITLE_PREFIX }QA — test plan and validation" \
  "$(mk_body \
     "QA" \
     "Validate functional behavior against FR acceptance criteria." \
     "Create/execute test matrix for sign-in, queue grouping, status bar, approve action" \
     "Verify regression and failure handling scenarios" \
     "QA report linked to parent issue" \
     "Reproducible test evidence (commands/screenshots/logs)" \
     "Defect list with severity and retest status" \
     "Developer implementation readiness in ${TARGET_REPO}" \
     "QA executes validation on candidate build" \
     "all Must requirements are verified or defects are tracked" \
     "Coordinate with Developer for fixes and reruns." \
   )"

create_issue \
  "${TITLE_PREFIX:+$TITLE_PREFIX }Security — auth and API hardening review" \
  "$(mk_body \
     "Security" \
     "Assess extension security posture for auth, secrets, and API usage." \
     "Review SecretStorage/auth session handling and token scope minimization" \
     "Validate no telemetry and no sensitive logging" \
     "Security review report with findings and disposition" \
     "Recommended mitigations merged or tracked" \
     "Sign-off comment for release gate" \
     "Developer PR and CI artifacts in ${TARGET_REPO}" \
     "Security reviews implementation and tests" \
     "security gate requirements are met for release" \
     "Follow least privilege and secure defaults." \
   )"

create_issue \
  "${TITLE_PREFIX:+$TITLE_PREFIX }DevOps — CI packaging and publish pipeline" \
  "$(mk_body \
     "DevOps" \
     "Ensure CI produces validated .vsix and supports marketplace release flow." \
     "Compile/lint/test/smoke/package workflow hardening" \
     "Document secrets and release steps for VS Code Marketplace/Open VSX" \
     "Green CI workflow linked to parent issue" \
     "Artifact generation (.vsix) and retention verified" \
     "Release runbook/checklist for first ship" \
     "Implementation branch + workflows in ${TARGET_REPO}" \
     "DevOps runs CI and confirms artifacts" \
     "release pipeline is repeatable for v1" \
     "Coordinate publish credentials with Director." \
   )"

create_issue \
  "${TITLE_PREFIX:+$TITLE_PREFIX }Tech Writer — docs and marketplace copy" \
  "$(mk_body \
     "Tech Writer" \
     "Produce user-facing docs and listing copy for release." \
     "README usage, commands, configuration, and troubleshooting" \
     "Marketplace/Open VSX listing text, screenshots, and changelog notes" \
     "Documentation PR(s) linked to parent issue" \
     "Accurate setup/sign-in instructions with constraints" \
     "Release notes aligned to delivered scope" \
     "Developer/QA outputs in ${TARGET_REPO}" \
     "Tech Writer finalizes docs before release" \
     "Director can follow docs to use and approve from extension" \
     "Keep v1 scope boundaries explicit." \
   )"

printf 'Sub-issue creation complete for parent issue #%s\n' "$PARENT_ISSUE"
