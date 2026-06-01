"""Tests for minimal squad v2 phase logic."""

from ai_alpha_squad.squad_v2 import (
    IssueView,
    has_deliverable,
    is_squad_internal_comment,
    next_action,
    run_in_progress,
)


def test_new_dispatches_business_owner():
    act = next_action(IssueView(1, "OPEN", frozenset({"new"}), (), "Target: https://github.com/o/r"))
    assert act.kind == "dispatch"
    assert act.agent == "business-owner"


def test_awaiting_approval_is_gate():
    act = next_action(
        IssueView(
            1,
            "OPEN",
            frozenset({"awaiting-approval"}),
            ({"body": "# Business Analysis\n\ncontent"},),
            "",
        )
    )
    assert act.kind == "gate"


def test_director_approved_dispatches_developer():
    act = next_action(
        IssueView(
            1,
            "OPEN",
            frozenset({"director-approved"}),
            (),
            "https://github.com/org/target",
        )
    )
    assert act.kind == "dispatch"
    assert act.agent == "developer"


def test_sequential_blocks_second_dispatch():
    comments = ({"body": "squad-v2-run:in_progress:business-owner"},)
    assert run_in_progress(comments) == "business-owner"
    act = next_action(IssueView(1, "OPEN", frozenset({"new"}), comments, ""))
    assert act.kind == "idle"


def test_in_progress_ignored_after_failed_run():
    comments = (
        {"body": "squad-v2-run:in_progress:developer"},
        {"body": "squad-v2-run:failed:developer — timeout"},
    )
    assert run_in_progress(comments) is None


def test_in_progress_active_when_failure_before_latest_marker():
    comments = (
        {"body": "squad-v2-run:failed:developer — old"},
        {"body": "squad-v2-run:in_progress:developer"},
    )
    assert run_in_progress(comments) == "developer"


def test_squad_work_branch():
    from ai_alpha_squad.squad_v2 import squad_work_branch

    assert squad_work_branch("developer", 94) == "squad/developer-issue-94"


def test_stale_in_progress_ignored_after_deliverable():
    comments = (
        {"body": "squad-v2-run:in_progress:business-owner"},
        {"body": "# Business Analysis\n\n" + "x" * 50},
    )
    assert run_in_progress(comments) is None


def test_ba_detected():
    assert has_deliverable(({"body": "# Business Analysis\n\nx" * 50},), "business-owner")


def test_internal_comment_detection():
    assert is_squad_internal_comment("squad-v2-run:in_progress:developer")
    assert is_squad_internal_comment("**Squad HF agent result** — foo")
    assert not is_squad_internal_comment("approve")


def test_developer_deliverable_requires_heading_not_inline_mention():
    ba_plan = (
        "# Business Analysis\n\n"
        "5. Post the PR link as a comment (heading `# Developer Deliverable`).\n"
    )
    assert not has_deliverable(({"body": ba_plan},), "developer")
    assert has_deliverable(
        ({"body": "# Developer Deliverable\n\nPR: https://github.com/o/r/pull/1\n" + "x" * 400},),
        "developer",
    )
