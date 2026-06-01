"""Regression checks for scheduled Copilot planning PR scan."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_pr_guard_workflow_has_scheduled_scan() -> None:
    text = (ROOT / ".github/workflows/squad-copilot-pr-guard.yml").read_text(encoding="utf-8")
    assert "schedule:" in text
    assert "squad-scan-planning-prs.sh" in text


def test_scan_script_lists_copilot_authors() -> None:
    text = (ROOT / "scripts/squad-scan-planning-prs.sh").read_text(encoding="utf-8")
    assert "copilot-swe-agent" in text
    assert "squad-copilot-pr-guard.sh" in text
