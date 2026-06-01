"""Tests for Director dashboard classification."""

from ai_alpha_squad.director_dashboard import _classify_bucket, _is_parent_job
from ai_alpha_squad.project_sync import PlanningDeliverables
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
