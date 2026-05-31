# Technical Specification

> **Instructions:** Copy this template into the parent issue or a linked design document after Business Analysis is approved. Map every `FR-*` to a `BR-*` from the Business Analysis. Create sub-issues from the Work Breakdown section.

## Metadata

| Field              | Value                                      |
| ------------------ | ------------------------------------------ |
| Parent Issue       | #                                          |
| Business Analysis  | Link to issue comment or document          |
| Author             | Architect                                  |
| Date               |                                            |
| Version            | 1.0                                        |
| Status             | Draft / In Review / Approved               |

## Related Artifacts

| Artifact | Link |
| -------- | ---- |
| Business Analysis |  |
| Sub-issues |  |
| ADRs |  |

---

## Overview

Brief description of the technical solution and how it satisfies the business goals.

---

## Business Requirements Mapping

| Requirement | Summary | Technical Solution |
| ----------- | ------- | ------------------ |
| BR-001      |         | FR-001, components, APIs |
| BR-002      |         |                    |

---

## Architecture Overview

### Context

Describe system boundaries, actors, and external dependencies.

### Component Diagram

Describe or link a diagram (Mermaid, image, or doc path).

### Components

| Component | Responsibility | Technology |
| --------- | -------------- | ---------- |
|           |                |            |

### Data Flow

Describe primary read/write paths and integration points.

---

## Technology Stack

| Layer              | Choice | Rationale |
| ------------------ | ------ | --------- |
| Frontend           |        |           |
| Backend            |        |           |
| Database           |        |           |
| Infrastructure     |        |           |
| External Services  |        |           |

---

## Functional Requirements

### FR-001: Title

**Maps to:** BR-001

**Description:**

**Implementation notes:**

- 

**Acceptance criteria:**

- [ ] Criterion 1
- [ ] Criterion 2

---

### FR-002: Title

**Maps to:** BR-002

**Description:**

**Implementation notes:**

- 

**Acceptance criteria:**

- [ ] Criterion 1

---

## Non-Functional Requirements

| Category        | Requirement | How verified |
| --------------- | ----------- | ------------ |
| Performance     |             |              |
| Scalability     |             |              |
| Reliability     |             |              |
| Availability    |             |              |
| Observability   |             |              |

---

## Security Requirements

| Area               | Requirement |
| ------------------ | ----------- |
| Authentication     |             |
| Authorization      |             |
| Data protection    |             |
| Secrets management |             |
| Audit logging      |             |

Security Agent validates against [security-report-template.md](security-report-template.md).

---

## Data Model

### Entity: Name

| Field | Type | Required | Notes |
| ----- | ---- | -------- | ----- |
|       |      |          |       |

**Relationships:**

**Migration notes:**

---

## API Design

### Endpoint: Name

| Property | Value |
| -------- | ----- |
| Method   |       |
| Path     |       |
| Auth     |       |

**Request:**

```json
```

**Response (success):**

```json
```

**Error codes:**

| Code | Condition |
| ---- | --------- |
|      |           |

---

## Dependencies and Constraints

| Dependency | Type (technical / team / external) | Owner | Status |
| ---------- | ---------------------------------- | ----- | ------ |
|            |                                    |       |        |

**Assumptions:**

- 

**Open questions:**

| ID | Question | Owner | Resolution |
| -- | -------- | ----- | ---------- |
| Q1 |          |       |            |

---

## Testing Strategy

| Level       | Scope | Owner |
| ----------- | ----- | ----- |
| Unit        |       | Developer / QA |
| Integration |       | QA |
| E2E         |       | QA |

**Critical paths (target 95% coverage):**

- 

---

## Deployment Strategy

| Topic        | Approach |
| ------------ | -------- |
| Environments |          |
| CI/CD        |          |
| Rollback     |          |
| Monitoring   |          |
| Feature flags|          |

DevOps uses [deployment-checklist-template.md](deployment-checklist-template.md) at release time.

---

## Work Breakdown

Create one sub-issue per row using [sub-issue-template.md](sub-issue-template.md).

| Role         | Sub-issue | Deliverables |
| ------------ | --------- | ------------ |
| Developer    | #         | Code, PR, tests |
| QA           | #         | QA report, test suite |
| Security     | #         | Security report |
| DevOps       | #         | Pipelines, IaC, runbooks |
| Tech Writer  | #         | Docs, release notes draft |

---

## Architecture Decisions

Record significant decisions in [architecture-decision-record.md](architecture-decision-record.md) and link here.

| ADR | Title | Status |
| --- | ----- | ------ |
|     |       |        |

---

## Approval

| Reviewer  | Status (Approved / Changes requested) | Date |
| --------- | ------------------------------------- | ---- |
| Architect |                                       |      |
| Director  |                                       |      |
