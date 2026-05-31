# AI Alpha Squad - Definition of Done

## Purpose

This document defines the minimum quality standards required before work may be considered complete.

Every agent must validate against this checklist.

Artifact templates live in [templates/README.md](templates/README.md). Documentation index: [README.md](README.md).

---

# Business Requirements

✓ Business problem understood

✓ Scope documented

✓ Acceptance criteria defined

✓ Risks documented

✓ Director approval received (if via WhatsApp: audit comment on issue per [whatsapp-director-channel.md](whatsapp-director-channel.md))

---

# Architecture

✓ Technical Specification completed

✓ Architecture documented

✓ Security requirements defined

✓ Deployment requirements defined

✓ Traceability established

---

# Development

✓ Code implemented

✓ Code reviewed

✓ Linting passes

✓ Build passes

✓ No critical defects

✓ No dead code

✓ No hardcoded secrets

---

# Testing

✓ Unit tests implemented

✓ Integration tests implemented

✓ Critical flows tested

✓ Regression tests completed

✓ Test results documented

Minimum Coverage:

80%

Critical Paths:

95%

---

# Security

✓ Dependency scan completed

✓ Vulnerability scan completed

✓ Authentication reviewed

✓ Authorization reviewed

✓ Secrets review completed

✓ OWASP Top 10 reviewed

Release blockers:

* Critical vulnerabilities
* High vulnerabilities

Must equal:

0

---

# DevOps

✓ CI pipeline operational

✓ CD pipeline operational

✓ Rollback plan exists

✓ Monitoring configured

✓ Logging configured

✓ Deployment documented

---

# Documentation

✓ User documentation updated

✓ Developer documentation updated

✓ API documentation updated

✓ Release notes created

✓ Changelog updated

✓ Documentation builds successfully

---

# Release Readiness

✓ QA approved

✓ Security approved

✓ DevOps approved

✓ Documentation approved

✓ Risks assessed

✓ Rollback plan documented

✓ Release notes published

---

# Production Readiness

The software is considered production-ready only when:

* Functionality complete
* Tests pass
* Security approved
* Documentation complete
* CI/CD green
* Release approved

---

# Mandatory Artifacts

Every completed feature must produce:

1. Business Analysis
2. Technical Specification
3. Source Code
4. Test Suite
5. Security Report
6. Deployment Pipeline
7. Documentation
8. Changelog Entry
9. Release Notes

Missing artifacts mean the work is NOT done.

---

# Final Rule

Done does not mean code is written.

Done means the feature can be safely deployed, operated, maintained, and understood by future teams.
