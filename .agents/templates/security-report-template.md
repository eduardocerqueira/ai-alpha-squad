# Security Assessment Report

> **Instructions:** Security reviews implementation against tech spec security requirements and OWASP Top 10. Block release on critical or high unresolved findings.

## Metadata

| Field                 | Value |
| --------------------- | ----- |
| Parent Issue          | #     |
| Sub-issue             | #     |
| Technical Specification | Link |
| Reviewer              | Security Agent |
| Date                  |       |
| Scope (PRs, commits)  |       |

---

## Executive Summary

**Overall:** PASS / FAIL

**Summary:** Brief assessment and release recommendation.

---

## Security Controls Review

| Control            | Status (Pass/Fail/N/A) | Notes |
| ------------------ | ---------------------- | ----- |
| Authentication     |                        |       |
| Authorization      |                        |       |
| Input validation     |                        |       |
| Output encoding      |                        |       |
| Secrets management   |                        |       |
| Logging (no secrets) |                        |       |
| Encryption at rest   |                        |       |
| Encryption in transit|                        |       |
| Session management   |                        |       |

---

## Dependency Audit

| Package | Version | Known CVEs | Risk | Action |
| ------- | ------- | ---------- | ---- | ------ |
|         |         |            |      |        |

---

## Vulnerability Scan

| Severity | Open count | Fixed in this release |
| -------- | ---------- | --------------------- |
| Critical | 0 required |  |
| High     | 0 required |  |
| Medium   |            |  |
| Low      |            |  |

**Scan tools / date:**

---

## OWASP Top 10 (2021) Review

| # | Category | Status | Notes |
| - | -------- | ------ | ----- |
| A01 | Broken Access Control |  |  |
| A02 | Cryptographic Failures |  |  |
| A03 | Injection |  |  |
| A04 | Insecure Design |  |  |
| A05 | Security Misconfiguration |  |  |
| A06 | Vulnerable and Outdated Components |  |  |
| A07 | Identification and Authentication Failures |  |  |
| A08 | Software and Data Integrity Failures |  |  |
| A09 | Security Logging and Monitoring Failures |  |  |
| A10 | Server-Side Request Forgery (SSRF) |  |  |

---

## Findings

### FIND-001: Title

| Field | Value |
| ----- | ----- |
| Severity | Critical / High / Medium / Low / Informational |
| Location | File, endpoint, or config |
| Description |  |
| Remediation |  |
| Status | Open / Fixed / Accepted risk |

---

## Release Recommendation

| Field | Value |
| ----- | ----- |
| Approved for release | YES / NO |
| Blockers | List FIND-* or CVEs |
| Accepted risks (Director acknowledged) |  |
