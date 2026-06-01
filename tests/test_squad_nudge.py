"""Tests for orchestrator nudge helpers."""
from __future__ import annotations

from datetime import datetime, timezone

from ai_alpha_squad.nudge import (
    NUDGE_MARKER,
    architect_subissues_complete,
    extract_deliverable_section,
    has_heading_marker,
    is_substantive_deliverable,
    issue_has_deliverable,
    last_nudge_minutes_ago,
    should_nudge_phase,
)


def test_has_heading_marker_requires_heading_line() -> None:
    assert has_heading_marker("# Business Analysis\n\nBody", "# Business Analysis")
    assert not has_heading_marker("See # Business Analysis inline", "# Business Analysis")


def test_issue_has_deliverable_ignores_orchestrator_noise() -> None:
    comments = [
        {"body": f"**{NUDGE_MARKER} (business-owner):** retry"},
        {"body": "# Business Analysis\n\nScope defined."},
    ]
    assert issue_has_deliverable(comments, "# Business Analysis")


def test_should_nudge_respects_cooldown_unless_forced() -> None:
    assert should_nudge_phase(
        has_deliverable=False,
        minutes_since_created=60,
        minutes_since_last_nudge=5,
        force=False,
        cooldown_minutes=30,
    ) is False
    assert should_nudge_phase(
        has_deliverable=False,
        minutes_since_created=60,
        minutes_since_last_nudge=5,
        force=True,
    ) is True


def test_should_nudge_skips_when_deliverable_present() -> None:
    assert should_nudge_phase(
        has_deliverable=True,
        minutes_since_created=60,
        minutes_since_last_nudge=None,
        force=True,
    ) is False


def test_last_nudge_minutes_ago_uses_latest() -> None:
    now = datetime(2026, 5, 31, 12, 0, tzinfo=timezone.utc)
    comments = [
        {"body": "plain", "createdAt": "2026-05-31T11:00:00Z"},
        {"body": f"**{NUDGE_MARKER}:** retry", "createdAt": "2026-05-31T11:30:00Z"},
    ]
    assert last_nudge_minutes_ago(comments, now=now) == 30.0


def test_extract_deliverable_rejects_stub() -> None:
    stub = "# Business Analysis\n\nSee BR-001 ... and US-002 ... done."
    assert extract_deliverable_section(stub, "# Business Analysis") is None


def test_extract_deliverable_from_pr_style_body() -> None:
    body = """## Summary
Handoff PR.

```markdown
# Business Analysis

## Metadata
| Field | Value |
| Job | Squad Director |

## Goals
Build the extension.

## Requirements Register
| BR-001 | Queue view | Must |
""" + "x" * 500
    section = extract_deliverable_section(body, "# Business Analysis")
    assert section is not None
    assert is_substantive_deliverable(section, "# Business Analysis")


def test_architect_subissues_complete() -> None:
    assert architect_subissues_complete(
        {"developer": 1, "qa": 2, "security": 3, "devops": 4, "tech-writer": 5}
    )
    assert not architect_subissues_complete(
        {"developer": 1, "qa": 2, "security": None, "devops": 4, "tech-writer": 5}
    )
