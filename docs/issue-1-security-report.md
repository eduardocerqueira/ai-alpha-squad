# Security Assessment Report — Seeker Modernization

> **Security Agent** assessment against FR-006/FR-007 (tech spec) and BR-006/BR-007 (business analysis).
> Critical and High unresolved findings block release per Definition of Done.

## Metadata

| Field | Value |
| ----- | ----- |
| Parent Issue | [#1 — Modernise seeker](https://github.com/eduardocerqueira/ai-alpha-squad/issues/1) |
| Sub-issue | [Security — Assess modernization security posture](https://github.com/eduardocerqueira/ai-alpha-squad/issues) |
| Technical Specification | `docs/issue-1-technical-spec-and-sub-issues.md` |
| Reviewer | Security Agent (Copilot) |
| Date | 2026-05-31 |
| Scope (PRs, commits) | Branch `copilot/security-assess-modernization-security-posture`; ai-alpha-squad workflows, scripts, Worker, Python helpers; seeker target repo review pending developer PR |

---

## Executive Summary

**Overall:** CONDITIONAL PASS ⚠️

**Summary:** The ai-alpha-squad automation layer is well-structured with strong foundations: Director-only approval gates, HMAC-SHA256 webhook signature verification with timing-safe comparison, least-privilege workflow permissions, and `.env`-based secret management. Two actionable vulnerabilities were identified and **fixed in this PR**:

- **FIND-001 (High — Fixed):** GitHub Actions script injection via user-controlled `${{ github.event.* }}` values interpolated directly in `run:` blocks — fixed in `director-gate.yml` and `squad-orchestrator.yml` by routing all event context through environment variables.
- **FIND-002 (Medium — Fixed):** `WHATSAPP_APP_SECRET` was optional, allowing unsigned webhook POST requests through without verification.

Two informational findings remain documented but pose no release-blocking risk. The seeker target repo security review is **blocked pending the developer PR** (FIND-005). A follow-up security review of the seeker PR is required before final release approval.

---

## Security Controls Review

| Control | Status | Notes |
| ------- | ------ | ----- |
| Authentication | Pass | Director-gate enforces GitHub login identity; webhook uses HMAC-SHA256 signature |
| Authorization | Pass | Least-privilege workflow `permissions`; Director-only approval enforced by `is_authorized_approver()` |
| Input validation | Pass | Shell scripts use `set -euo pipefail`; comment body now passed via env var (FIND-001 fixed) |
| Output encoding | Pass | GitHub comments formatted via Python helper; no HTML injection path identified |
| Secrets management | Pass | Secrets via GitHub Actions Secrets; `.env` in `.gitignore`; `.env.example` committed without values |
| Logging (no secrets) | Pass | No secrets logged; `console.warn` for non-Director WhatsApp messages |
| Encryption at rest | N/A | No at-rest storage beyond Cloudflare-managed Worker bindings |
| Encryption in transit | Pass | HTTPS enforced on all external calls (Cloudflare Workers, GitHub API, Meta API) |
| Session management | N/A | Stateless automation; no user sessions |

---

## Dependency Audit

| Package | Version | Known CVEs | Risk | Action |
| ------- | ------- | ---------- | ---- | ------ |
| pytest | >=8.0 (dev only) | None known | Low | None |
| setuptools | >=61 (build) | None known at this version | Low | None |
| vitest | ^3.x (Worker dev) | None known | Low | None |
| wrangler | (Worker dev) | None known | Low | None |
| TypeScript | (Worker dev) | None known | Low | None |

> **Note:** The seeker target repo dependency audit (Python requirements, CI tooling) is pending the developer PR.

---

## Vulnerability Scan

| Severity | Open count | Fixed in this release |
| -------- | ---------- | --------------------- |
| Critical | 0 | 0 |
| High | 0 | 1 (FIND-001) |
| Medium | 0 | 1 (FIND-002) |
| Low | 2 open (FIND-003, FIND-004) | 0 |
| Informational | 1 open (FIND-005) | 0 |

**Scan tools / date:** Manual code review + OWASP Top 10 checklist; 2026-05-31. Seeker target repo pending.

---

## OWASP Top 10 (2021) Review

| # | Category | Status | Notes |
| - | -------- | ------ | ----- |
| A01 | Broken Access Control | Pass | Director gate (`director-gate.sh`, `director-gate-is-authorized.sh`) restricts label application and comment-approval to authorized logins only |
| A02 | Cryptographic Failures | Pass | Webhook uses HMAC-SHA256 with `crypto.subtle`; timing-safe comparison via XOR loop; TLS enforced on all external calls |
| A03 | Injection | Pass (after fix) | FIND-001 fixed — user-controlled event context (`comment.body`, `sender.login`, `label.name`) now passed through env vars in `director-gate.yml` and `squad-orchestrator.yml`; not interpolated directly into shell `run:` expressions |
| A04 | Insecure Design | Pass | Director approval is a single-factor control appropriate for internal automation; role boundaries enforced |
| A05 | Security Misconfiguration | Pass | Secrets in GitHub Actions Secrets; `wrangler.jsonc` vars are non-sensitive; `.gitignore` excludes `.env` and `squad-config.yaml` |
| A06 | Vulnerable and Outdated Components | Low risk | See FIND-003; first-party GitHub Actions at major version tags; no high-CVE packages in minimal dependency set |
| A07 | Identification and Authentication Failures | Pass (after fix) | FIND-002 fixed — HMAC signature verification now always enforced on webhook POST; verify token enforced on GET |
| A08 | Software and Data Integrity Failures | Low risk | See FIND-003; Actions not pinned to SHA; CI pipeline uses `actions/checkout@v4` and `actions/setup-python@v5` |
| A09 | Security Logging and Monitoring Failures | Pass | Unauthorized approval attempts are logged as GitHub issue comments; non-Director WhatsApp messages warned via `console.warn` |
| A10 | Server-Side Request Forgery (SSRF) | Pass | No user-controlled URLs used in server-side fetch calls; all external endpoints are hardcoded (GitHub API, Meta API) |

---

## Findings

### FIND-001: GitHub Actions script injection via user-controlled `${{ github.event.* }}` values

| Field | Value |
| ----- | ----- |
| Severity | **High** |
| Location | `.github/workflows/director-gate.yml` — "Gate Director comment approval" step; `.github/workflows/squad-orchestrator.yml` — "Verify director-approved sender" step |
| Description | User-controlled GitHub event context values were directly interpolated into `run:` shell expressions using `${{ github.event.comment.body }}` and `${{ github.event.sender.login }}`. The Actions expression engine substitutes these values into the shell script before execution, so a malicious comment body containing shell metacharacters (e.g., `"; rm -rf /; "`) could execute arbitrary commands in the runner. The `comment.body` case is the critical vector — any GitHub user who can comment on a squad issue could trigger injection. `sender.login` is constrained to `[a-zA-Z0-9-]` by GitHub, but was also moved to an env var for consistency. |
| Remediation | Pass user-controlled GitHub context values through step-level `env:` mappings. Environment variable values are treated as data (not code) by the shell — they are not re-expanded by the Actions expression parser. Applied to `comment.body`, `comment.user.login`, `label.name`, and `sender.login`. |
| Status | **Fixed** — `.github/workflows/director-gate.yml` and `.github/workflows/squad-orchestrator.yml` updated in this PR |

---

### FIND-002: `WHATSAPP_APP_SECRET` optional — unsigned webhook POST accepted

| Field | Value |
| ----- | ----- |
| Severity | **Medium** |
| Location | `workers/whatsapp-webhook/src/index.ts` (guard block) · `workers/whatsapp-webhook/src/env.d.ts` |
| Description | `WHATSAPP_APP_SECRET` was typed as `string?` (optional). When the secret was absent, the Worker skipped `X-Hub-Signature-256` verification entirely, accepting POST requests from any source — not just Meta — as valid webhook events. This could allow an attacker to forge inbound "Director messages" and trigger unauthorized label approvals on squad issues. |
| Remediation | Declare `WHATSAPP_APP_SECRET` as required (`string`) in `env.d.ts`; remove the conditional guard in `index.ts` so signature verification is always enforced. Document as required in `README.md`. |
| Status | **Fixed** — `env.d.ts`, `index.ts`, and `README.md` updated in this PR |

---

### FIND-003: GitHub Actions pinned by mutable version tags, not commit SHAs

| Field | Value |
| ----- | ----- |
| Severity | **Low** |
| Location | All `.github/workflows/*.yml` — `actions/checkout@v4`, `actions/setup-python@v5` |
| Description | Action tags (`@v4`, `@v5`) are mutable references. A compromised release of a dependency action could introduce malicious code without a visible tag change. Risk is low because these are first-party GitHub-maintained actions with a strong security track record and verified signing. |
| Remediation | For maximum supply-chain security, pin actions to their full commit SHA (e.g., `actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683`). Tooling such as `pinact` or Dependabot can automate this. |
| Status | **Open — accepted risk** (first-party GitHub actions; low exploitation probability) |

---

### FIND-004: Obfuscation pattern may miss non-alphanumeric API key formats

| Field | Value |
| ----- | ----- |
| Severity | **Informational** |
| Location | `src/ai_alpha_squad/seeker_qa.py` — `OBFUSCATION_PATTERNS["long_api_key"]` |
| Description | The `long_api_key` regex (`[A-Za-z0-9_]{32,}`) matches alphanumeric+underscore sequences only. Common API key formats including OpenAI (`sk-proj-…`), Anthropic, Stripe, and others contain hyphens, dots, or prefixes separated by non-alphanumeric characters and would not be matched by this pattern. Conversely, benign long Base64 strings could trigger false positives. |
| Remediation | Extend `OBFUSCATION_PATTERNS` with format-specific regexes for key providers used by seeker once the seeker source is reviewed. Consider adding patterns for `sk-[a-zA-Z0-9-_]{20,}` (OpenAI style) and `****** (Authorization header leaks). |
| Status | **Open — informational** (no active key formats confirmed in seeker; extend once seeker PR is available) |

---

### FIND-005: Seeker target repo not available for full security review

| Field | Value |
| ----- | ----- |
| Severity | **Informational** |
| Location | Target repo: `eduardocerqueira/seeker` |
| Description | The seeker developer modernization PR is blocked/pending. Full security review of seeker's authentication mechanisms, dependency tree, obfuscation pipeline integration, and CI/CD workflow permissions has not yet been performed. The QA report (FR-006 tests) validates the obfuscation contract from the ai-alpha-squad side but does not substitute for a source-level review of seeker itself. |
| Remediation | Once the seeker developer PR is available: (1) review seeker's updated dependencies for CVEs; (2) verify obfuscation is applied at all data-egress points; (3) confirm workflow permissions follow least-privilege; (4) update this report with seeker-specific findings. |
| Status | **Open — pending seeker PR** |

---

## Requirements Traceability

| ID | Source | Criterion | Status |
| --- | ------ | --------- | ------ |
| FR-006 | Tech spec | Obfuscation safeguards retained | **Pass** — `redact_sensitive_data()` + `validate_obfuscated_output()` verified by 12 unit tests; FIND-004 noted as informational |
| FR-007 | Tech spec | Security gate before release | **Pass** — This report is the security gate artefact |
| BR-006 | Business analysis | Preserve sensitive-data obfuscation | **Pass** — Obfuscation contract validated; see FR-006 |
| BR-007 | Business analysis | Security validation before release | **Pass** — Security report posted; FIND-001 (High) and FIND-002 (Medium) fixed |

---

## Release Recommendation

| Field | Value |
| ----- | ----- |
| Approved for release | **NO — conditional** |
| Blockers | FIND-005: seeker developer PR not yet reviewed; full end-to-end security evidence pending |
| Conditions | (1) Merge seeker developer PR → (2) Security agent reviews seeker source, dependencies, and CI workflows → (3) Confirm no new High/Critical findings → (4) Re-issue PASS before Release Manager proceeds |
| Accepted risks (Director acknowledged) | FIND-003 (low — first-party action tags); FIND-004 (informational — extend obfuscation patterns post-seeker-review) |
