"""Tests for issue-first planning promotion helpers."""
from __future__ import annotations

from ai_alpha_squad.planning_delivery import (
    PLANNING_FILE_HINTS,
    extract_deliverable_from_sources,
    phase_for_labels,
)


def test_phase_for_labels_business_owner() -> None:
    assert phase_for_labels({"new", "medium"}) == "business-owner"
    assert phase_for_labels({"business-owner"}) == "business-owner"
    assert phase_for_labels({"awaiting-approval", "business-owner"}) is None


def test_phase_for_labels_architect() -> None:
    assert phase_for_labels({"director-approved"}) == "architect"
    assert phase_for_labels({"director-approved", "designed"}) is None


def test_extract_deliverable_from_branch_markdown() -> None:
    marker = "# Business Analysis"
    body = "## Summary\nCopilot handoff PR only."
    files = {
        "docs/business-analysis.md": (
            "# Business Analysis\n\n"
            "## Metadata\n| Field | Value |\n| Job | Squad Director |\n\n"
            "## Scope\n"
            + ("Detailed scope paragraph. " * 30)
        ),
    }
    section = extract_deliverable_from_sources(body, files, marker)
    assert section is not None
    assert section.startswith(marker)
    assert PLANNING_FILE_HINTS.search("docs/business-analysis.md")


def test_extract_prefers_body_when_substantive() -> None:
    marker = "# Technical Specification"
    body = (
        "# Technical Specification\n\n"
        "## Architecture\n"
        + ("Component design notes. " * 25)
    )
    files = {"notes.md": "# Technical Specification\n\nstub ..."}
    section = extract_deliverable_from_sources(body, files, marker)
    assert section is not None
    assert "Architecture" in section
