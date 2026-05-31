"""Tests for WhatsApp lifecycle message templates."""

from ai_alpha_squad.whatsapp.lifecycle import LIFECYCLE_STEPS, format_lifecycle_message


def test_all_lifecycle_steps_format() -> None:
    for step in LIFECYCLE_STEPS:
        body = format_lifecycle_message(step, 1, "Review and modernize seeker")
        assert "[AI Alpha Squad]" in body
        assert "#1" in body
        assert "Now:" in body
        assert "Next:" in body
        assert "github.com" in body


def test_awaiting_approval_is_short_and_actionable() -> None:
    body = format_lifecycle_message("awaiting-approval", 1, "Seeker job")
    assert "APPROVE" in body
    assert "REJECT" in body


def test_format_with_extra() -> None:
    body = format_lifecycle_message(
        "awaiting-approval",
        1,
        "Seeker",
        extra="Summary: incremental modernization.",
    )
    assert "Summary: incremental modernization." in body
