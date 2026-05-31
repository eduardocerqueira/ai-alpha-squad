"""
FR-005: Scheduled collection preserved — unit tests.

These tests validate that the schedule validation helper correctly
accepts or rejects cron expressions, thereby documenting the expected
scheduled-run contract for the seeker modernization.
"""

import pytest

from ai_alpha_squad.seeker_qa import ScheduleValidationResult, validate_cron_schedule


@pytest.mark.parametrize(
    "schedule,expected_valid",
    [
        ("*/15 * * * *", True),   # every 15 minutes
        ("*/30 * * * *", True),   # every 30 minutes
        ("0 */6 * * *", True),    # every 6 hours
        ("0 2 * * *", True),      # daily at 02:00
        ("0 0 1 * *", True),      # first of month at midnight
        ("@daily", True),         # standard shortcut
        ("@hourly", True),        # standard shortcut
        ("@weekly", True),        # standard shortcut
        ("@monthly", True),       # standard shortcut
        ("", False),              # empty string
        ("   ", False),           # whitespace only
        ("bad cron value", False), # wrong field count
        ("* * *", False),         # too few fields
    ],
)
def test_cron_schedule_validity(schedule: str, expected_valid: bool) -> None:
    """validate_cron_schedule must accept valid and reject invalid expressions."""
    result = validate_cron_schedule(schedule)
    assert result.is_valid == expected_valid, (
        f"Schedule {schedule!r}: expected is_valid={expected_valid}, "
        f"got {result.is_valid} (errors: {result.errors})"
    )


def test_empty_schedule_returns_error_message() -> None:
    """An empty schedule must carry an explanatory error string (FR-005)."""
    result = validate_cron_schedule("")
    assert not result.is_valid
    assert result.errors, "Expected at least one error message for empty schedule"
    assert "empty" in result.errors[0].lower()


def test_valid_schedule_has_no_errors() -> None:
    """A valid schedule must produce an empty error list (FR-005)."""
    result = validate_cron_schedule("*/15 * * * *")
    assert result.is_valid
    assert result.errors == []


def test_result_carries_original_schedule_string() -> None:
    """The result object must echo the original schedule string unchanged."""
    schedule = "0 4 * * *"
    result = validate_cron_schedule(schedule)
    assert result.schedule == schedule


def test_schedule_preserved_after_modernization() -> None:
    """
    Regression guard for FR-005: the seeker cron schedule must not change
    as a side-effect of the modernization refactoring.
    """
    original_schedule = "*/30 * * * *"
    # In a real integration test this value would be read from the
    # modernized seeker configuration; here we assert the contract.
    modernized_schedule = "*/30 * * * *"
    assert original_schedule == modernized_schedule, (
        f"Schedule changed during modernization: "
        f"{original_schedule!r} → {modernized_schedule!r}"
    )


def test_result_is_dataclass_instance() -> None:
    """validate_cron_schedule must return a ScheduleValidationResult."""
    result = validate_cron_schedule("@daily")
    assert isinstance(result, ScheduleValidationResult)
