# Deployment Checklist

> **Instructions:** DevOps completes before and during each production deployment. Link parent issue, release plan, and PRs.

## Metadata

| Field           | Value |
| --------------- | ----- |
| Parent Issue    | #     |
| Release Version |       |
| Environment     | staging / production |
| Deployer        | DevOps |
| Date            |       |
| Release Plan    | Link  |

---

## Pre-Deployment

| # | Item | Status | Notes |
| - | ---- | ------ | ----- |
| 1 | Director / Release Manager approval recorded | ☐ |  |
| 2 | QA report: PASS | ☐ | Link |
| 3 | Security report: approved, 0 critical/high open | ☐ | Link |
| 4 | Technical Specification and PRs merged to release branch | ☐ |  |
| 5 | Database migrations reviewed and reversible | ☐ |  |
| 6 | Secrets and config verified in target environment | ☐ |  |
| 7 | Rollback procedure documented and tested | ☐ |  |
| 8 | Monitoring dashboards and alerts active | ☐ |  |
| 9 | On-call / communication channel ready | ☐ |  |

---

## Deployment Steps

| Step | Action | Verified |
| ---- | ------ | -------- |
| 1 | Notify stakeholders (start) | ☐ |
| 2 | Enable maintenance mode (if applicable) | ☐ |
| 3 | Run database migrations | ☐ |
| 4 | Deploy application / infrastructure | ☐ |
| 5 | Smoke tests in target environment | ☐ |
| 6 | Disable maintenance mode | ☐ |
| 7 | Notify stakeholders (complete) | ☐ |

**CI/CD run:** Link to pipeline execution

---

## Post-Deployment Verification

| Check | Expected | Actual | Pass |
| ----- | -------- | ------ | ---- |
| Health endpoints | 200 |  | ☐ |
| Critical user flows | Per FR-* acceptance criteria |  | ☐ |
| Error rate / latency | Within SLO |  | ☐ |
| Logs free of critical errors | Yes |  | ☐ |

---

## Rollback (if needed)

| Trigger | Action taken | Time | Outcome |
| ------- | ------------ | ---- | ------- |
|         |              |      |         |

---

## Sign-off

| Role | Name | Approved | Date |
| ---- | ---- | -------- | ---- |
| DevOps |  | ☐ |  |
| Release Manager |  | ☐ |  |
