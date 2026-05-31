"""
QA validation helpers for seeker modernization.

FR-005: Scheduled collection preserved
FR-006: Obfuscation safeguards retained

These helpers model the expected behaviour of the seeker scheduled-collection
and obfuscation subsystems so that regression tests can run in CI without
requiring the target seeker repository to be checked out alongside this one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

__all__ = [
    "OBFUSCATION_PATTERNS",
    "REDACTED",
    "ObfuscationValidationResult",
    "ScheduleValidationResult",
    "redact_sensitive_data",
    "validate_cron_schedule",
    "validate_obfuscated_output",
]

# ---------------------------------------------------------------------------
# FR-005 — Scheduled collection
# ---------------------------------------------------------------------------

# Cron patterns that are considered valid for seeker schedule strings.
_VALID_CRON_RE = (
    re.compile(r"^\*/\d+ \* \* \* \*$"),           # every N minutes
    re.compile(r"^\d+ \*/\d+ \* \* \*$"),           # every N hours
    re.compile(r"^\d+ \d+ \* \* \*$"),              # daily at HH:MM
    re.compile(r"^\d+ \d+ \d+ \* \*$"),             # monthly
    re.compile(r"^@(hourly|daily|weekly|monthly)$"), # standard shortcuts
)


@dataclass
class ScheduleValidationResult:
    is_valid: bool
    schedule: str
    errors: list[str] = field(default_factory=list)


def validate_cron_schedule(schedule: str) -> ScheduleValidationResult:
    """Return whether *schedule* is a non-empty, well-formed cron expression."""
    stripped = (schedule or "").strip()
    if not stripped:
        return ScheduleValidationResult(
            is_valid=False,
            schedule=schedule,
            errors=["Schedule is empty or blank"],
        )

    for pattern in _VALID_CRON_RE:
        if pattern.match(stripped):
            return ScheduleValidationResult(is_valid=True, schedule=schedule)

    # Fall back to field-count heuristic (5 standard fields).
    fields = stripped.split()
    if len(fields) != 5:
        return ScheduleValidationResult(
            is_valid=False,
            schedule=schedule,
            errors=[f"Expected 5 cron fields, got {len(fields)}"],
        )

    return ScheduleValidationResult(is_valid=True, schedule=schedule)


# ---------------------------------------------------------------------------
# FR-006 — Obfuscation safeguards
# ---------------------------------------------------------------------------

#: Sentinel used when a sensitive value is redacted.
REDACTED = "[REDACTED]"

#: Named patterns for categories of sensitive data the seeker must obfuscate.
OBFUSCATION_PATTERNS: dict[str, re.Pattern[str]] = {
    "email": re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"),
    "url_token": re.compile(r"https?://[^\s]*[?&]token=[^\s&]+"),
    "long_api_key": re.compile(r"(?<![A-Za-z0-9_])[A-Za-z0-9_]{32,}(?![A-Za-z0-9_])"),
}


@dataclass
class ObfuscationValidationResult:
    is_clean: bool
    violations: list[str] = field(default_factory=list)
    patterns_checked: list[str] = field(default_factory=list)


def validate_obfuscated_output(text: str) -> ObfuscationValidationResult:
    """Return whether *text* contains no unredacted sensitive patterns."""
    violations: list[str] = []
    for name, pattern in OBFUSCATION_PATTERNS.items():
        matches = pattern.findall(text)
        if matches:
            violations.append(
                f"Potential {name} found: {len(matches)} occurrence(s)"
            )
    return ObfuscationValidationResult(
        is_clean=len(violations) == 0,
        violations=violations,
        patterns_checked=list(OBFUSCATION_PATTERNS),
    )


def redact_sensitive_data(text: str) -> str:
    """Replace all recognised sensitive patterns in *text* with ``REDACTED``."""
    result = text
    for pattern in OBFUSCATION_PATTERNS.values():
        result = pattern.sub(REDACTED, result)
    return result
