#!/usr/bin/env bash
# Create or update AI Alpha Squad labels. Run from repo root: ./.github/labels-setup.sh
set -euo pipefail
REPO="${1:-eduardocerqueira/ai-alpha-squad}"

create() {
  gh label create "$1" --repo "$REPO" --color "$2" --description "$3" --force
}

# Agent labels
create business-owner 1D76DB "Business Owner agent — analysis and requirements"
create architect 5319E7 "Architect agent — technical specification and design"
create developer 0E8A16 "Developer agent — implementation"
create qa FBCA04 "QA agent — testing and quality validation"
create security B60205 "Security agent — security assessment"
create devops 006B75 "DevOps agent — CI/CD, infrastructure, operations"
create tech-writer C5DEF5 "Tech Writer agent — documentation"
create release-manager D93F0B "Release Manager agent — release coordination"

# Workflow labels (issue status)
create new E4E4E4 "New request — intake"
create awaiting-approval FEF2C0 "Business analysis complete — awaiting Director approval"
create approved C2E0C6 "Director approved — ready for architecture"
create designed BFD4F2 "Technical specification complete"
create implemented 1D76DB "Implementation complete — in validation"
create validation D4C5F9 "QA, Security, DevOps, and docs validation in progress"
create release-candidate F9D0C4 "Release candidate — awaiting Director release approval"
create released 0E8A16 "Released to production"
create blocked B60205 "Blocked — cannot progress until resolved"

# Priority labels
create critical B60205 "Critical priority"
create high D93F0B "High priority"
create medium FBCA04 "Medium priority"
create low 0E8A16 "Low priority"

echo "Labels created/updated on $REPO"
