# AI Alpha Squad - Issue Lifecycle

## Purpose

Define the lifecycle of every GitHub issue.

All agents must follow this workflow. System context: [project-specification.md](project-specification.md). Documentation index: [README.md](README.md).

---

# Lifecycle States

## new

Issue created by Director.

Owner:

Business Owner

Actions:

* Analyze request
* Gather requirements
* Perform research

Exit Criteria:

Business Analysis completed

---

## awaiting-approval

Owner:

Director

Actions:

* Review Business Analysis
* Approve or reject proposal

Exit Criteria:

approved label added

---

## approved

Owner:

Architect

Actions:

* Create Technical Specification
* Define implementation plan
* Create sub-issues

Exit Criteria:

Architecture completed

---

## designed

Owner:

Developer

Actions:

* Implement solution
* Submit pull request

Exit Criteria:

Implementation completed

---

## implemented

Owners:

* QA
* Security
* DevOps
* Tech Writer

Actions:

Perform validation activities.

Exit Criteria:

All validation completed

---

## validation

Owner:

Release Manager

Actions:

* Verify readiness
* Validate reports
* Review risks

Exit Criteria:

Release candidate approved

---

## release-candidate

Owner:

Director

Actions:

Final review

Exit Criteria:

Release approved

---

## released

Owner:

Release Manager

Actions:

* Publish release
* Publish changelog
* Close issue

Exit Criteria:

Issue closed

---

# Blocked State

Status:

blocked

A blocked issue cannot progress.

Reasons:

* Missing requirements
* Technical dependency
* Security issue
* Failed validation
* Infrastructure failure

Required Actions:

* Document blocker
* Create blocker issue
* Assign owner
* Link blocker

---

# Sub-Issue Rules

Architect creates child issues for:

* Development
* QA
* Security
* DevOps
* Documentation

Each child issue must:

* Reference parent issue
* Reference technical specification
* Define expected deliverables

---

# Pull Request Rules

Every pull request must use [pull-request-template.md](templates/pull-request-template.md) and include:

* Summary
* Related issue and requirements (`BR-*`, `FR-*`)
* Testing evidence
* Risks
* Rollback plan

Pull requests missing these sections may not be merged.

---

# Closure Requirements

An issue may be closed only when:

* Acceptance criteria satisfied
* QA approved
* Security approved
* Documentation completed
* Release approved
* Artifacts archived

No exceptions.
