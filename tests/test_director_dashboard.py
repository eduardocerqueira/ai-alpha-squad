"""Tests for Director dashboard classification."""

import json
from pathlib import Path

from ai_alpha_squad.director_dashboard import (
    GhCliError,
    _classify_bucket,
    _effective_phase,
    _headline_for_card,
    _is_parent_job,
    _load_job_card_v2,
    fetch_dashboard_json,
)


def _v2_row(number, labels, comments, state="OPEN"):
    return {
        "number": number,
        "title": "[Request]: demo job",
        "body": "Target repo: https://github.com/acme/target",
        "labels": [{"name": n} for n in labels],
        "state": state,
        "updatedAt": "2026-06-01T00:00:00Z",
        "comments": comments,
    }


def test_v2_card_three_agents_only():
    card = _load_job_card_v2("o/r", _v2_row(200, ["new"], []))
    assert [a["role"] for a in card.agents] == ["business-owner", "developer", "qa"]


def test_v2_released_all_done():
    card = _load_job_card_v2(
        "o/r", _v2_row(201, ["released"], [{"body": "# Business Analysis\nok"}], state="CLOSED")
    )
    assert card.bucket == "completed"
    assert all(a["status"] == "done" for a in card.agents)


def test_v2_qa_fail_shows_rework():
    comments = [
        {"body": "# Business Analysis\nok"},
        {"body": "# Developer Deliverable\n\nhttps://github.com/acme/target/pull/10\n" + "x" * 200},
        {
            "body": (
                "# QA Report\n\n## Criteria\n- ❌ gap\n\n## Fixes required\n"
                "1. [BLOCKER] src/Foo.java — fix\n\nsquad-v2-qa:fail\n"
            )
        },
    ]
    card = _load_job_card_v2("o/r", _v2_row(202, ["director-approved"], comments))
    assert card.bucket == "in_progress"
    assert "Queued" in card.headline
    qa = next(a for a in card.agents if a["role"] == "qa")
    dev = next(a for a in card.agents if a["role"] == "developer")
    assert qa["status"] == "done" and "round 1/3" in qa["detail"]
    assert dev["status"] == "waiting" and "pull/10" in dev["detail"]


def test_v2_invalid_qa_fail_does_not_show_rework():
    comments = [
        {"body": "# Business Analysis\nok"},
        {"body": "# Developer Deliverable\n\nhttps://github.com/acme/target/pull/10\n" + "x" * 200},
        {
            "body": (
                "# QA Report\n\n## Criteria\n- ❌ gap\n\n"
                "- [REQUIRED] src/Foo.java — fix\n\nsquad-v2-qa:fail\n"
            )
        },
    ]
    card = _load_job_card_v2("o/r", _v2_row(207, ["director-approved"], comments))
    qa = next(a for a in card.agents if a["role"] == "qa")
    dev = next(a for a in card.agents if a["role"] == "developer")
    assert qa["status"] == "waiting" and "Queued" in qa["detail"]
    assert dev["status"] == "done"


def test_v2_blocked_closed_goes_to_blocked_not_done():
    # A blocked job that was closed must surface in the Blocked bucket, not hide
    # under Done (released still wins → Done).
    card = _load_job_card_v2(
        "o/r", _v2_row(204, ["blocked", "director-approved"], [{"body": "# Business Analysis\nok"}], state="CLOSED")
    )
    assert card.bucket == "stuck" and card.blocked is True
    rel = _load_job_card_v2("o/r", _v2_row(205, ["released"], [], state="CLOSED"))
    assert rel.bucket == "completed"


def test_v2_closed_director_approved_not_done():
    comments = [
        {"body": "# Business Analysis\nok", "createdAt": "2026-06-03T04:00:00Z"},
        {
            "body": "# Developer Deliverable\n\nhttps://github.com/acme/target/pull/10\n" + "x" * 200,
            "createdAt": "2026-06-03T04:01:00Z",
        },
        {"body": "squad-v2-run:in_progress:developer", "createdAt": "2026-06-03T04:02:00Z"},
    ]
    card = _load_job_card_v2(
        "o/r",
        _v2_row(208, ["director-approved"], comments, state="CLOSED"),
    )
    assert card.bucket == "in_progress"
    assert card.bucket != "completed"


def test_v2_closed_not_planned_is_done():
    comments = [
        {
            "body": "**Director reset:** Closing this run.\n\nContinue on #57",
            "createdAt": "2026-06-01T02:00:00Z",
        },
    ]
    card = _load_job_card_v2(
        "o/r",
        {
            **_v2_row(17, ["director-approved"], comments, state="CLOSED"),
            "stateReason": "NOT_PLANNED",
        },
    )
    assert card.bucket == "completed"


def test_v2_closed_stale_new_label_is_done():
    """Old closed intake jobs without recent v2 activity belong in Done."""
    card = _load_job_card_v2(
        "o/r",
        _v2_row(
            15,
            ["new", "business-owner"],
            [{"body": "# Business Analysis\nold", "createdAt": "2026-05-31T12:00:00Z"}],
            state="CLOSED",
        ),
    )
    assert card.bucket == "completed"


def test_v2_active_run_on_closed_shows_in_progress():
    # An agent actively running (in_progress marker, no terminal) shows In
    # progress even if the issue is closed.
    comments = [
        {"body": "# Business Analysis\nok"},
        {"body": "squad-v2-run:in_progress:developer — working"},
    ]
    card = _load_job_card_v2("o/r", _v2_row(206, ["director-approved"], comments, state="CLOSED"))
    assert card.bucket == "in_progress"


def test_v2_awaiting_approval_is_director_gate():
    comments = [{"body": "# Business Analysis\nok"}]
    card = _load_job_card_v2("o/r", _v2_row(203, ["awaiting-approval"], comments))
    assert card.bucket == "needs_you"
    gate = next(e for e in card.events if e["key"] == "awaiting-approval")
    assert gate["status"] == "director" and "action" in gate
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

