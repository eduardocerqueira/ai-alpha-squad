# Changelog Entry — Seeker Modernization

> **Instructions:** Release Manager adds entries per [Keep a Changelog](https://keepachangelog.com/) conventions. Group by version.

## [Unreleased] — TBD

> Replace `Unreleased` with the version tag and date once the Release Manager creates the GitHub Release.

### Added

- Schedule validation at runner startup: invalid or empty cron strings now produce a structured error with a clear message (Issue [#1](https://github.com/eduardocerqueira/ai-alpha-squad/issues/1), FR-005)
- Obfuscation safeguards: emails, token-bearing URLs, and long API keys are replaced with `[REDACTED]` in all collected output (Issue [#1](https://github.com/eduardocerqueira/ai-alpha-squad/issues/1), FR-006)
- 30 new unit tests covering FR-005 (schedule validation, 18 tests) and FR-006 (obfuscation, 12 tests); all 59 repository tests pass (QA report: `docs/issue-1-qa-report.md`)
- Reproducible setup documentation: Python ≥ 3.12 requirement, virtual-environment steps, and pinned-install command (FR-003, FR-004)

### Changed

- Runtime target upgraded to **Python 3.12**; CI runs exclusively on 3.12 (BR-003)
- README updated with current install, usage, schedule configuration, and troubleshooting sections (FR-003, FR-004)

### Deprecated

_(none)_

### Removed

_(none)_

### Fixed

_(none)_

### Security

- Obfuscation layer added as a first-class pipeline step to prevent sensitive data (email addresses, API tokens, token URLs) from appearing in collected output or logs (FR-006, BR-006)

---

## Links

| Resource | URL |
| -------- | --- |
| Release notes | [docs/issue-1-release-notes.md](issue-1-release-notes.md) |
| Full diff | Compare link (added by Release Manager at release time) |
| Parent epic / issue | [#1 — Modernise seeker](https://github.com/eduardocerqueira/ai-alpha-squad/issues/1) |
| QA report | [docs/issue-1-qa-report.md](issue-1-qa-report.md) |

---

## Upgrade Notes

Steps operators or users must take when moving to this version:

1. Install **Python ≥ 3.12** (check with `python --version`).
2. Recreate the virtual environment: `python -m venv .venv && source .venv/bin/activate`.
3. Install dependencies: `pip install -e ".[dev]"` (or the equivalent for your seeker install).
4. Confirm your schedule strings are valid cron expressions — accepted patterns are documented in the [release notes](issue-1-release-notes.md).
5. No other migration steps are required; behaviour is backward-compatible.
