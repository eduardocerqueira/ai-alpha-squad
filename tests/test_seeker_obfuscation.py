"""
FR-006: Obfuscation safeguards retained — unit tests.

These tests validate that the obfuscation helper correctly detects
and redacts sensitive values, thereby documenting the expected
obfuscation contract for the seeker modernization.
"""

import pytest

from ai_alpha_squad.seeker_qa import (
    REDACTED,
    ObfuscationValidationResult,
    redact_sensitive_data,
    validate_obfuscated_output,
)


# ---------------------------------------------------------------------------
# validate_obfuscated_output
# ---------------------------------------------------------------------------


def test_clean_output_passes_validation() -> None:
    """Output with no sensitive patterns must be considered clean (FR-006)."""
    clean = "Collection completed: 42 records processed. No errors."
    result = validate_obfuscated_output(clean)
    assert result.is_clean
    assert result.violations == []


def test_email_in_output_is_a_violation() -> None:
    """A bare e-mail address in seeker output must be flagged as a violation."""
    text = "User user@example.com submitted a record."
    result = validate_obfuscated_output(text)
    assert not result.is_clean
    assert any("email" in v.lower() for v in result.violations)


def test_token_url_in_output_is_a_violation() -> None:
    """A URL carrying an inline token must be flagged as a violation."""
    text = "Fetched https://api.example.com/data?token=abc123secretXXXXXXXXXXXX"
    result = validate_obfuscated_output(text)
    assert not result.is_clean
    assert any("token" in v.lower() for v in result.violations)


def test_multiple_violations_all_reported() -> None:
    """When multiple sensitive patterns are present, all are reported."""
    text = "User user@test.com and admin@test.com logged in."
    result = validate_obfuscated_output(text)
    assert not result.is_clean
    assert len(result.violations) >= 1


def test_patterns_checked_is_non_empty() -> None:
    """The result must list which pattern categories were checked."""
    result = validate_obfuscated_output("some text")
    assert len(result.patterns_checked) > 0


def test_result_is_dataclass_instance() -> None:
    """validate_obfuscated_output must return an ObfuscationValidationResult."""
    result = validate_obfuscated_output("text")
    assert isinstance(result, ObfuscationValidationResult)


# ---------------------------------------------------------------------------
# redact_sensitive_data
# ---------------------------------------------------------------------------


def test_redact_removes_emails() -> None:
    """redact_sensitive_data must replace e-mail addresses with REDACTED."""
    text = "Contact admin@seeker.io for help."
    redacted = redact_sensitive_data(text)
    assert "admin@seeker.io" not in redacted
    assert REDACTED in redacted


def test_redact_removes_token_urls() -> None:
    """redact_sensitive_data must replace token-bearing URLs with REDACTED."""
    text = "Fetched from https://api.example.com/data?token=abc123secrettoken1234"
    redacted = redact_sensitive_data(text)
    assert "abc123secrettoken1234" not in redacted
    assert REDACTED in redacted


def test_redact_is_idempotent_on_clean_text() -> None:
    """redact_sensitive_data must leave clean text unchanged."""
    clean = "All 100 records collected successfully at 2026-05-31."
    assert redact_sensitive_data(clean) == clean


def test_redacted_output_passes_obfuscation_check() -> None:
    """
    Regression guard for FR-006: after redaction the output must pass the
    obfuscation validator — no sensitive data must survive.
    """
    sensitive = "admin@example.com accessed https://api.io/v1?token=supersecret123456789012"
    redacted = redact_sensitive_data(sensitive)
    result = validate_obfuscated_output(redacted)
    assert result.is_clean, f"Violations after redaction: {result.violations}"


@pytest.mark.parametrize(
    "sensitive_input",
    [
        "admin@example.com is the contact",
        "https://api.io/v1?token=supersecretkey12345678901234",
    ],
)
def test_redact_makes_each_input_clean(sensitive_input: str) -> None:
    """Parametrised FR-006 regression: every known sensitive pattern is redacted."""
    redacted = redact_sensitive_data(sensitive_input)
    result = validate_obfuscated_output(redacted)
    assert result.is_clean, (
        f"Input {sensitive_input!r} still has violations after redaction: "
        f"{result.violations}"
    )
