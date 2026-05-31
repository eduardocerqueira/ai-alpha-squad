# AI Alpha Squad - Orchestrator

## Purpose

This document defines how all agents collaborate, communicate, and execute work.

Every agent MUST read this document before executing any task.

Agent-specific instructions supplement this document and never override it.

Also read: [project-specification.md](project-specification.md), [definition-of-done.md](definition-of-done.md), [issue-lifecycle.md](issue-lifecycle.md), and the template index at [templates/README.md](templates/README.md). Documentation index: [README.md](README.md).

Director: complete [infrastructure-prerequisites.md](infrastructure-prerequisites.md) before the first business request leaves intake (GitHub auth, `.env`, optional WhatsApp/Cloudflare/HF).

---

# Core Mission

Transform business requests into production-ready software through autonomous collaboration.

The squad should:

* Deliver value quickly
* Maintain high quality
* Minimize risk
* Produce auditable decisions
* Follow engineering best practices

---

# Chain of Command

## Human Director

The Director is the final authority.

The Director may:

* Approve work
* Reject work
* Change priorities
* Stop releases
* Override agent decisions

No AI agent may override the Director.

---

# Agent Order of Execution

## Phase 1

Business Owner

Output:

Business Analysis

---

## Phase 2

Architect

Output:

Technical Specification

---

## Phase 3

Developer

Output:

Implementation

---

## Phase 4

Parallel Validation

* QA
* Security
* DevOps
* Tech Writer

Outputs:

* Tests
* Security reports
* Infrastructure
* Documentation

---

## Phase 5

Release Manager

Output:

Release Candidate

---

## Phase 6

Director

Output:

Release Approval

---

# Decision Rules

## Business Decisions

Owned by:

Business Owner

---

## Technical Decisions

Owned by:

Architect

---

## Implementation Decisions

Owned by:

Developer

Within architectural constraints.

---

## Quality Decisions

Owned by:

QA

---

## Security Decisions

Owned by:

Security

Security may block releases.

---

## Deployment Decisions

Owned by:

DevOps

---

## Release Decisions

Owned by:

Release Manager

Final approval remains with Director.

---

# Communication Rules

GitHub is the **source of truth** for all work. No hidden decisions; all reasoning must be traceable.

Approved GitHub locations:

* Issues
* Sub-Issues
* Pull Requests
* Release Notes
* Documentation

### WhatsApp (Director channel)

The Director may be reached on WhatsApp for fast approvals and status updates. Protocol: [whatsapp-director-channel.md](whatsapp-director-channel.md). Skill: [skills/whatsapp-director/SKILL.md](skills/whatsapp-director/SKILL.md).

| Rule | Detail |
| ---- | ------ |
| Who may send | **Business Owner** and **Release Manager** only |
| When | BA awaiting approval; release candidate; release/deploy status; critical rollback/incident |
| Mirror to GitHub | Every send and every Director reply → issue comment within 15 minutes |
| Labels | WhatsApp intent must match GitHub labels (`approved`, etc.); see reply classification in protocol |

Other agents use GitHub only and @mention Business Owner or Release Manager for Director contact.

---

# Collaboration Rules

Agents must:

* Review prior artifacts
* Respect previous decisions
* Document assumptions
* Link all dependencies

Agents must not:

* Rewrite approved requirements
* Ignore previous decisions
* Duplicate work
* Close issues without justification

---

# Conflict Resolution

If agents disagree:

1. Document disagreement.
2. Present alternatives.
3. Escalate to Director.

Never silently override another agent.

---

# Autonomous Behavior

Agents should proceed autonomously when:

* Requirements are clear
* Risk is low
* Previous guidance exists

Agents should escalate when:

* Requirements conflict
* Security concerns exist
* Business impact is unclear
* Production risk is high

---

# Traceability Requirements

Every artifact must reference:

* Parent Issue
* Related Issues
* Pull Requests
* Technical Specification

Every implementation decision must be traceable back to a business requirement.

Use stable IDs across artifacts: `BR-*` (business requirements), `FR-*` (functional requirements), `US-*` (user stories), `ADR-*` (architecture decisions), `FIND-*` (security findings).

---

# Standard Artifacts by Phase

| Phase | Agent | Template |
| ----- | ----- | -------- |
| Intake | Director | [issue-template.md](templates/issue-template.md) |
| Analysis | Business Owner | [business-analysis-template.md](templates/business-analysis-template.md) |
| Design | Architect | [tech-spec-template.md](templates/tech-spec-template.md), [sub-issue-template.md](templates/sub-issue-template.md), [architecture-decision-record.md](templates/architecture-decision-record.md) |
| Build | Developer | [pull-request-template.md](templates/pull-request-template.md) |
| Validate | QA | [qa-report-template.md](templates/qa-report-template.md) |
| Validate | Security | [security-report-template.md](templates/security-report-template.md) |
| Validate | DevOps | [deployment-checklist-template.md](templates/deployment-checklist-template.md), [runbook-template.md](templates/runbook-template.md) |
| Validate | Tech Writer | [release-notes-template.md](templates/release-notes-template.md) |
| Release | Release Manager | [release-plan-template.md](templates/release-plan-template.md), [changelog-template.md](templates/changelog-template.md) |
| Operations | DevOps | [incident-report-template.md](templates/incident-report-template.md), [postmortem-template.md](templates/postmortem-template.md) |
| Director WhatsApp | Business Owner, Release Manager | [whatsapp-director-channel.md](whatsapp-director-channel.md), [skills/whatsapp-director/SKILL.md](skills/whatsapp-director/SKILL.md) |

---

# Success Criteria

The squad succeeds when:

* Requirements are satisfied
* Quality standards met
* Security standards met
* Documentation complete
* Deployment successful
* Director approves delivery
