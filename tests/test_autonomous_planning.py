"""Tests for autonomous planning fallback."""
from __future__ import annotations

from pathlib import Path

from ai_alpha_squad.autonomous_planning import (
    AUTONOMOUS_MARKER,
    build_business_analysis_from_job_pack,
    count_planning_nudges,
    resolve_job_pack_path,
    should_run_autonomous_fallback,
)
from ai_alpha_squad.nudge import NUDGE_MARKER, PHASE_MARKERS, is_substantive_deliverable


ROOT = Path(__file__).resolve().parents[1]
JOB_PACK = ROOT / "docs/jobs/job-1-vscode-squad-director.md"


def test_resolve_job_pack_from_issue_body():
    body = "See docs/jobs/job-1-vscode-squad-director.md for scope."
    path = resolve_job_pack_path(body, ROOT)
    assert path == JOB_PACK


def test_ba_from_job_pack_is_substantive():
    job_md = JOB_PACK.read_text(encoding="utf-8")
    ba = build_business_analysis_from_job_pack(
        job_md, issue_number=64, issue_title="Job 1 — Squad Director"
    )
    marker = PHASE_MARKERS["business-owner"]
    assert is_substantive_deliverable(ba, marker)
    assert "# Business Analysis" in ba


def test_should_run_after_nudges():
    comments = [{"body": f"{NUDGE_MARKER} missing BA"} for _ in range(2)]
    assert should_run_autonomous_fallback(comments, has_open_copilot_pr=False)


def test_should_not_run_when_disabled(monkeypatch):
    monkeypatch.setenv("SQUAD_AUTONOMOUS_PLANNING", "0")
    comments = [{"body": f"{NUDGE_MARKER} x"} for _ in range(5)]
    assert not should_run_autonomous_fallback(comments, has_open_copilot_pr=False)


def test_count_planning_nudges():
    comments = [
        {"body": "normal"},
        {"body": f"**{NUDGE_MARKER}** please post"},
    ]
    assert count_planning_nudges(comments) == 1
