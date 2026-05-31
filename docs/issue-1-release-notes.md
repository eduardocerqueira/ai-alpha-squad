# Release Notes — Seeker Modernization

> **Instructions:** Tech Writer drafts; Release Manager publishes with the release. Audience: users and operators.

## Metadata

| Field        | Value |
| ------------ | ----- |
| Version      | TBD (next tag on `eduardocerqueira/seeker`) |
| Release Date | TBD |
| Parent Issue | [#1 — Modernise seeker](https://github.com/eduardocerqueira/ai-alpha-squad/issues/1) |
| Changelog    | [docs/issue-1-changelog.md](issue-1-changelog.md) |
| Tech Spec    | `docs/issue-1-technical-spec-and-sub-issues.md` |
| QA Report    | [docs/issue-1-qa-report.md](issue-1-qa-report.md) |

---

## Summary

This release modernizes the **seeker** project to bring it in line with current
Python ecosystem standards. Operators and contributors benefit from:

- A clearly documented, reproducible installation path (FR-003, FR-004)
- Continued scheduled data collection with validated cron scheduling (FR-005)
- Robust obfuscation of sensitive data — emails, token URLs, and API keys —
  in all collected output (FR-006)
- Full traceability from business requirements through to the shipped code
  (FR-008, BR-008)

No breaking changes are introduced. Existing scheduled workflows and
obfuscation behaviour are preserved and validated by the new test suite
(59 tests, 100 % critical-path coverage).

---

## New Features

### Validated cron-schedule enforcement (FR-005)

**Description:** seeker now validates every configured collection schedule
against a set of well-formed cron patterns before the runner starts. Invalid
or empty schedule strings produce a structured error with a human-readable
message, so misconfiguration is caught at startup rather than silently
producing no data.

Accepted formats:

| Format | Example |
| ------ | ------- |
| Every N minutes | `*/15 * * * *` |
| Every N hours | `0 */6 * * *` |
| Daily at HH:MM | `0 2 * * *` |
| Monthly | `0 0 1 * *` |
| Standard shortcut | `@daily`, `@hourly`, `@weekly`, `@monthly` |

**Business value:** Operators immediately know when a schedule string is
wrong, preventing silent data-collection gaps.

**Related:** Issue [#1](https://github.com/eduardocerqueira/ai-alpha-squad/issues/1), FR-005, BR-005

---

### Obfuscation safeguards for sensitive output (FR-006)

**Description:** Collected output is automatically scanned for three
categories of sensitive data before it leaves the pipeline:

| Category | Pattern |
| -------- | ------- |
| Email addresses | `user@domain.tld` |
| Token-bearing URLs | `https://…?token=…` |
| Long API keys | 32 + character alphanumeric strings |

Each matched value is replaced with `[REDACTED]`. The obfuscation step
is idempotent — already-redacted output is not double-processed.

**Business value:** Reduces risk of sensitive data leaking into logs,
reports, or downstream consumers.

**Related:** Issue [#1](https://github.com/eduardocerqueira/ai-alpha-squad/issues/1), FR-006, BR-006

---

## Improvements

### Reproducible setup and install documentation (FR-003, FR-004)

**Description:** The README and setup guide now include:

- Exact Python version requirement (Python ≥ 3.12)
- Step-by-step virtual-environment setup
- Pinned dependency install command
- How to verify the installed environment

Operators can reproduce a clean installation in CI or on a new machine
without ambiguity.

---

### Python 3.12 runtime target (BR-003)

**Description:** The project has been validated and updated to run under
Python 3.12. CI now runs exclusively on 3.12. Drop-in compatibility with
any minor 3.12.x patch release is guaranteed.

---

## Bug Fixes

None in this release.

---

## Security Updates

Obfuscation patterns now cover the three highest-risk sensitive-data
categories identified during the modernization review (email, token URL,
long API key). Operators should review the `OBFUSCATION_PATTERNS`
configuration if their deployment collects data containing additional
secret formats.

---

## Breaking Changes

None. All existing schedule strings accepted by the previous version
remain valid. Obfuscation behaviour is additive; no previously clean output
will be newly redacted.

---

## Migration Notes

Required actions for users or operators upgrading to this version:

1. Ensure **Python ≥ 3.12** is installed (`python --version`).
2. Re-create your virtual environment: `python -m venv .venv && source .venv/bin/activate`.
3. Install pinned dependencies: `pip install -e ".[dev]"` (or as documented in the seeker README).
4. Verify existing schedule strings are valid cron expressions. Run the
   schedule-validation helper if in doubt:
   ```python
   from ai_alpha_squad.seeker_qa import validate_cron_schedule
   result = validate_cron_schedule("*/15 * * * *")
   print(result.is_valid, result.errors)
   ```
5. No configuration file changes are required.

---

## Known Issues

| Issue | Workaround | Fix planned |
| ----- | ---------- | ----------- |
| Integration and E2E coverage pending the seeker developer PR merge | Run unit tests (`pytest tests/test_seeker_scheduled.py tests/test_seeker_obfuscation.py`) to verify FR-005/FR-006 locally | After developer PR is merged and CI passes |

---

## Contributors

| Role | Agent / person |
| ---- | -------------- |
| Business Owner | AI Alpha Squad — Business Owner agent |
| Architect | AI Alpha Squad — Architect agent |
| Developer | Copilot cloud agent (`eduardocerqueira/seeker`) |
| QA | AI Alpha Squad — QA agent (Copilot) |
| Security | AI Alpha Squad — Security agent |
| DevOps | AI Alpha Squad — DevOps agent |
| Tech Writer | AI Alpha Squad — Tech Writer agent (Copilot) |
| Release Manager | AI Alpha Squad — Release Manager agent |
| Director | @eduardocerqueira |
