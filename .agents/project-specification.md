# AI Alpha Squad - Autonomous Multi-Agent Software Delivery System

## 1. Objective

AI Alpha Squad is an autonomous software delivery organization composed of specialized AI agents collaborating through GitHub Issues.

The system receives business requests as GitHub Issues and autonomously progresses them through analysis, design, implementation, validation, security review, documentation, release preparation, and deployment.

The goal is to produce production-ready software following engineering best practices while maintaining clear accountability, traceability, and human oversight.

Agents may run on **GitHub Copilot cloud** (recommended for code), **Cursor** (optional), or orchestration Workers — see [agent-runtime-strategy.md](agent-runtime-strategy.md).

---

# 2. Repository

Repository:

https://github.com/eduardocerqueira/ai-alpha-squad

Primary work queue:

https://github.com/eduardocerqueira/ai-alpha-squad/issues

GitHub Issues are the single source of truth for all work.

## Documentation layout

Squad documentation is versioned in the `.agents/` directory at the repository root. The legacy `doc/` folder is removed; do not reference or recreate it.

| Document | Path |
| -------- | ---- |
| Index | [.agents/README.md](README.md) |
| Orchestrator | [squad-orchestrator.md](squad-orchestrator.md) |
| Issue lifecycle | [issue-lifecycle.md](issue-lifecycle.md) |
| Definition of done | [definition-of-done.md](definition-of-done.md) |
| Artifact templates | [templates/README.md](templates/README.md) |

Agent role files: `agent-<role>.md` in this directory (see [README.md](README.md#agent-definitions)).

---

# 3. Core Principles

## Autonomous Execution

Agents should complete their responsibilities without human intervention whenever possible.

## Role Specialization

Each agent operates only within its defined area of expertise.

## Traceability

Every decision, artifact, implementation, and approval must be documented in GitHub.

## Human Governance

The Director is the only human participant and retains final approval authority.

## Quality First

Code must be secure, tested, documented, deployable, and maintainable before release.

---

# 4. Agent Structure

Each agent is represented by a GitHub label and may only perform actions within its responsibility domain. Detailed prompts and deliverables are in `agent-<role>.md`; artifact formats are in [templates/](templates/README.md).

| Label | Agent definition |
| ----- | ---------------- |
| `business-owner` | [agent-business-owner.md](agent-business-owner.md) |
| `architect` | [agent-architect.md](agent-architect.md) |
| `developer` | [agent-developer.md](agent-developer.md) |
| `qa` | [agent-qa.md](agent-qa.md) |
| `security` | [agent-security.md](agent-security.md) |
| `devops` | [agent-devops.md](agent-devops.md) |
| `tech-writer` | [agent-tech-writer.md](agent-tech-writer.md) |
| `release-manager` | [agent-release-manager.md](agent-release-manager.md) |

## Director (Human)

### Responsibilities

* Create business requests
* Review business proposals
* Approve or reject solutions
* Approve releases
* Resolve conflicts between agents

### Triggers

Creates a new GitHub Issue.

### Output

Business request issue.

### WhatsApp

The Director may approve or respond via WhatsApp. **Business Owner** and **Release Manager** are the only agents that message the Director on WhatsApp; all messages and replies are mirrored to GitHub Issues. Protocol: [whatsapp-director-channel.md](whatsapp-director-channel.md). Skill: [skills/whatsapp-director/SKILL.md](skills/whatsapp-director/SKILL.md).

---

## Business Owner Agent

Label: `business-owner`

### Responsibilities

* Analyze the business request
* Clarify requirements
* Perform market and technical research
* Identify risks and assumptions
* Define acceptance criteria
* Propose business solution

### Input

Director issue.

### Deliverables

Business Analysis document containing:

* Problem statement
* Goals
* Scope
* Out-of-scope items
* User stories
* Acceptance criteria
* Risks
* Proposed solution

### Completion Criteria

Business proposal is submitted to the issue.

### Approval Gate

Director adds label:

`approved`

Only after approval may the Architect begin.

Director may approve via GitHub or WhatsApp; Business Owner must classify WhatsApp replies and post an audit comment on the issue (see [whatsapp-director-channel.md](whatsapp-director-channel.md)).

---

## Architect Agent

Label: `architect`

### Responsibilities

Transform approved business requirements into a complete technical solution.

### Input

Approved Business Analysis.

### Deliverables

Technical Specification document containing:

#### System Design

* Architecture overview
* Component diagram
* Service boundaries
* Data flow

#### Technology Decisions

* Frameworks
* Libraries
* Infrastructure
* Database choices

#### Technical Requirements

* Functional requirements
* Non-functional requirements
* Performance requirements
* Security requirements

#### Implementation Guidance

Instructions for:

* Developer
* QA
* Security
* DevOps
* Tech Writer

### Output

Create sub-issues:

* Development
* QA
* Security
* DevOps
* Documentation

### Completion Criteria

All technical work packages created and linked.

---

## Developer Agent

Label: `developer`

### Responsibilities

Implement the approved technical specification.

### Deliverables

* Source code
* Feature implementation
* Database migrations
* API endpoints
* UI implementation

### Requirements

* Follow architecture guidance
* Follow coding standards
* Maintain readability
* Keep dependencies current

### Completion Criteria

Implementation Pull Request submitted.

---

## Quality Assurance Agent

Label: `qa`

### Responsibilities

Validate software quality.

### Deliverables

* Unit tests
* Integration tests
* End-to-end tests
* Code review findings
* Quality report

### Validation Areas

* Correctness
* Reliability
* Regression prevention
* Edge cases
* Performance validation

### Completion Criteria

All tests pass.

Coverage targets:

* Unit Test Coverage >= 80%
* Critical Paths >= 95%

---

## Security Agent

Label: `security`

### Responsibilities

Protect the solution from vulnerabilities.

### Deliverables

* Security review report
* Dependency audit
* Vulnerability scan results
* Remediation Pull Requests

### Validation Areas

* OWASP Top 10
* Dependency vulnerabilities
* Secrets exposure
* Authentication
* Authorization
* Data protection
* Secure configuration

### Completion Criteria

No critical or high vulnerabilities remain.

---

## DevOps Agent

Label: `devops`

### Responsibilities

Automate build, deployment, and operational readiness.

### Deliverables

* CI pipelines
* CD pipelines
* Infrastructure definitions
* Build scripts
* Container definitions
* Deployment automation

### Validation Areas

* Build reproducibility
* Environment consistency
* Rollback capability
* Monitoring readiness

### Completion Criteria

Application deployable via automated pipeline.

---

## Tech Writer Agent

Label: `tech-writer`

### Responsibilities

Maintain project documentation.

### Deliverables

MkDocs documentation including:

* Architecture
* Installation
* Deployment
* User guides
* API references
* Troubleshooting

### Completion Criteria

Documentation builds successfully and covers all delivered functionality.

---

## Release Manager Agent

Label: `release-manager`

### Responsibilities

Coordinate delivery readiness.

### Deliverables

#### Release Planning

* Release schedule
* Release scope
* Release checklist

#### Change Management

* Changelog
* Release notes
* Versioning

#### Risk Management

* Risk assessment
* Deployment risks
* Rollback strategy

#### Communication

* Stakeholder updates
* Release status reports
* Director WhatsApp for release candidate and deploy status ([whatsapp-director-channel.md](whatsapp-director-channel.md))

### Release Authority

The Release Manager may recommend release readiness.

The Director performs final release approval (GitHub and/or WhatsApp; WhatsApp replies must be classified and logged on the issue).

### Completion Criteria

All release gates passed.

---

# 5. Workflow

## Stage 1: Intake

Director creates issue.

Issue automatically assigned to:

`business-owner`

Status:

`new`

---

## Stage 2: Business Analysis

Business Owner completes analysis.

Status:

`awaiting-approval`

Director reviews.

If approved:

Label added:

`approved`

Status:

`approved`

If rejected:

Return to Business Owner.

---

## Stage 3: Architecture

Architect creates:

* Technical Specification
* Work breakdown
* Sub-issues

Status:

`designed`

---

## Stage 4: Implementation

Developer completes implementation.

Status:

`implemented`

---

## Stage 5: Validation

Parallel execution:

* QA review
* Security review
* DevOps review
* Documentation review

Status:

`validation`

---

## Stage 6: Release Preparation

Release Manager validates:

* Code complete
* Tests passed
* Security approved
* Documentation approved
* Deployment approved

Status:

`release-candidate`

---

## Stage 7: Production Release

Director approves release.

Status:

`released`

Issue closed.

---

# 6. GitHub Labels

## Agent Labels

* business-owner
* architect
* developer
* qa
* security
* devops
* tech-writer
* release-manager

## Workflow Labels

* new
* awaiting-approval
* approved
* designed
* implemented
* validation
* release-candidate
* released
* blocked

## Priority Labels

* critical
* high
* medium
* low

---

# 7. Required Artifacts

Every feature must produce:

| Artifact | Template |
| -------- | -------- |
| Business Analysis | [business-analysis-template.md](templates/business-analysis-template.md) |
| Technical Specification | [tech-spec-template.md](templates/tech-spec-template.md) |
| Source Code | — |
| Tests | — (evidence in [qa-report-template.md](templates/qa-report-template.md)) |
| Security Report | [security-report-template.md](templates/security-report-template.md) |
| Deployment Pipeline | [deployment-checklist-template.md](templates/deployment-checklist-template.md) |
| Documentation | MkDocs site + [runbook-template.md](templates/runbook-template.md) as needed |
| Release Notes | [release-notes-template.md](templates/release-notes-template.md) |
| Changelog Entry | [changelog-template.md](templates/changelog-template.md) |

Full checklist: [definition-of-done.md](definition-of-done.md).

---

# 8. Definition of Done

A work item is considered complete only when all criteria in [definition-of-done.md](definition-of-done.md) are satisfied, including Director approval for release.

---

# 9. Failure Handling

If an agent cannot complete its task:

1. Document the blocker.
2. Create a blocker issue.
3. Assign the blocker to the responsible agent.
4. Add label:

`blocked`

5. Notify Release Manager.

No release may proceed with unresolved blockers.

---

# 10. Success Metrics

The system should continuously measure:

* Lead Time
* Cycle Time
* Deployment Frequency
* Change Failure Rate
* Mean Time to Recovery (MTTR)
* Test Coverage
* Vulnerability Count
* Documentation Coverage
* Release Predictability

These metrics should be published in periodic project reports.

---

# 11. Future Enhancements

Potential future agents:

* Product Manager
* UX Designer
* Data Engineer
* SRE
* AI Reviewer
* Cost Optimization Agent
* Compliance Agent
* Performance Engineering Agent
* Customer Success Agent
