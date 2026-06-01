"""Tests for Director dashboard classification."""

import json
from pathlib import Path

from ai_alpha_squad.director_dashboard import (
    GhCliError,
    _classify_bucket,
    _effective_phase,
    _headline_for_card,
    _is_parent_job,
    fetch_dashboard_json,
)
from ai_alpha_squad.project_sync import AGENT_PENDING_ON_ISSUE, PlanningDeliverables


def test_is_parent_job_excludes_subissue():
    assert _is_parent_job("[Developer] foo", "| Parent Issue | #64 |") is False
    assert _is_parent_job("[Job 1] VS Code", "Target repo") is True


def test_classify_needs_you():
    bucket = _classify_bucket(
        state="OPEN",
        lifecycle="awaiting-approval",
        active_agent="Director",
        needs_director="Yes",
        planning=PlanningDeliverables(has_business_analysis=True),
        stuck_reasons=(),
    )
    assert bucket == "needs_you"


def test_classify_stuck_missing_ba():
    bucket = _classify_bucket(
        state="OPEN",
        lifecycle="new",
        active_agent=AGENT_PENDING_ON_ISSUE,
        needs_director="No",
        planning=PlanningDeliverables(has_business_analysis=False),
        stuck_reasons=(),
    )
    assert bucket == "stuck"


def test_classify_in_progress_designed():
    bucket = _classify_bucket(
        state="OPEN",
        lifecycle="designed",
        active_agent="developer",
        needs_director="No",
        planning=PlanningDeliverables(has_business_analysis=True, has_technical_spec=True),
        stuck_reasons=(),
    )
    assert bucket == "in_progress"


def test_classify_stuck_when_pipeline_reasons():
    bucket = _classify_bucket(
        state="OPEN",
        lifecycle="implemented",
        active_agent="developer",
        needs_director="No",
        planning=PlanningDeliverables(has_business_analysis=True, has_technical_spec=True),
        stuck_reasons=("PR merged but validation not started",),
    )
    assert bucket == "stuck"


def test_closed_issue_not_blocked_when_pipeline_stale():
    bucket = _classify_bucket(
        state="CLOSED",
        lifecycle="implemented",
        active_agent="developer",
        needs_director="No",
        planning=PlanningDeliverables(has_business_analysis=True, has_technical_spec=True),
        stuck_reasons=("Parent has `implemented` but validation agents were never dispatched",),
    )
    assert bucket == "completed"


def test_effective_phase_advances_past_blocked_label_with_artifacts():
    # #111-style: labels say blocked + director-approved, but a dev PR is open.
    # Trust the artifacts — the real phase is `implemented`, not blocked.
    phase = _effective_phase(
        "blocked",
        ("blocked", "director-approved"),
        has_spec=True,
        pr_url="https://github.com/o/r/pull/14",
        pr_merged=False,
    )
    assert phase == "implemented"


def test_effective_phase_keeps_label_when_no_artifacts():
    phase = _effective_phase(
        "director-approved",
        ("director-approved",),
        has_spec=False,
        pr_url=None,
        pr_merged=False,
    )
    assert phase == "director-approved"


def test_headline_needs_you_approval():
    assert "Business Analysis" in _headline_for_card(
        "needs_you", "awaiting-approval", (), False
    )


def test_fetch_dashboard_json_uses_cache_on_gh_error(tmp_path: Path, monkeypatch) -> None:
    cache = tmp_path / "jobs.json"
    cache.write_text(
        json.dumps(
            {
                "generated_at": "2026-01-01T00:00:00Z",
                "repo": "o/r",
                "counts": {"needs_you": 1, "in_progress": 0, "stuck": 0, "completed": 0},
                "needs_you": [{"number": 1, "title": "t", "url": "u", "headline": "h"}],
                "in_progress": [],
                "stuck": [],
                "completed": [],
            }
        ),
        encoding="utf-8",
    )

    def boom(_repo: str, *, include_closed: int = 15):
        raise GhCliError(["issue", "list"], 1, "API rate limit exceeded")

    monkeypatch.setattr(
        "ai_alpha_squad.director_dashboard.build_dashboard",
        boom,
    )
    data = fetch_dashboard_json("o/r", cache_path=cache)
    assert data["stale"] is True
    assert "rate limit" in data["fetch_error"].lower()
    assert data["counts"]["needs_you"] == 1

