# Runbook: [Service or procedure name]

> **Instructions:** DevOps or Tech Writer maintains operational procedures. Link from deployment docs and monitoring alerts.

## Metadata

| Field            | Value |
| ---------------- | ----- |
| Service / system |       |
| Owner            | DevOps |
| Last reviewed    |       |
| On-call rotation | Link or team |
| Related issues   | #     |

---

## Overview

Purpose of this runbook and when to use it.

---

## Prerequisites

| Requirement | Details |
| ----------- | ------- |
| Access | Roles, accounts, VPN |
| Tools | CLI versions, dashboards |
| Documentation | Tech spec, architecture links |

---

## Normal Operations

### Health check

```bash
# Example commands — replace with project-specific steps
```

**Expected result:**

### Routine task: [Name]

| Step | Action | Verification |
| ---- | ------ | ------------ |
| 1 |  |  |
| 2 |  |  |

---

## Alerts and Troubleshooting

| Symptom | Likely cause | Steps |
| ------- | ------------ | ----- |
| High error rate |  | 1. Check logs … |
| Elevated latency |  |  |

---

## Failure Recovery

### Restart service

1. 

### Rollback deployment

See [deployment-checklist-template.md](deployment-checklist-template.md) rollback section and Release Plan.

---

## Escalation

| Level | Contact | When |
| ----- | ------- | ---- |
| L1 | On-call | First response |
| L2 | DevOps lead | SEV-2+ or >30 min |
| L3 | Director | SEV-1 or data loss risk |

For customer-impacting events, open an incident using [incident-report-template.md](incident-report-template.md).

---

## Revision History

| Date | Author | Change |
| ---- | ------ | ------ |
|      |        | Initial |
