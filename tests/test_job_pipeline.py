"""Tests for job pipeline stuck detection."""

from ai_alpha_squad.job_pipeline import (
    build_agent_roster,
    detect_stuck_reasons,
    effective_lifecycle_from_labels,
)
from ai_alpha_squad.project_sync import PlanningDeliverables
from ai_alpha_squad.validation_dispatch import (
    VALIDATION_DISPATCH_MARKER,
    role_dispatch_marker,
)


def test_effective_lifecycle_prefers_implemented_over_designed():
    assert effective_lifecycle_from_labels({"designed", "implemented"}) == "implemented"


def test_released_marks_validation_agents_done():
    # A released job (v2 may not create per-role sub-issues) must not leave
    # validation agents stuck on "waiting".
    agents = build_agent_roster(
        "org/repo",
        128,
        labels={"released"},
        comments=[],
        lifecycle="released",
        pr_url="https://github.com/org/target/pull/9",
        pr_merged=True,
    )
    for role in ("qa", "security", "devops", "tech-writer"):
        a = next(x for x in agents if x.role == role)
        assert a.status == "done", f"{role} should be done on a released job, got {a.status}"


def test_stuck_when_pr_merged_validation_not_dispatched():
    agents = build_agent_roster(
        "org/repo",
        64,
        labels={"implemented"},
        comments=[],
        lifecycle="implemented",
        pr_url="https://github.com/org/target/pull/1",
        pr_merged=True,
    )
    reasons = detect_stuck_reasons(
        labels={"designed", "implemented"},
        lifecycle="implemented",
        comments=[],
        pr_url="https://github.com/org/target/pull/1",
        pr_merged=True,
        agents=agents,
    )
    assert any("validation" in r.lower() for r in reasons)


def test_no_stuck_when_validation_dispatched():
    role = "qa"
    comments = [
        {"body": VALIDATION_DISPATCH_MARKER},
        {"body": role_dispatch_marker(role)},
    ]
    agents = build_agent_roster(
        "org/repo",
        64,
        labels={"implemented"},
        comments=comments,
        lifecycle="implemented",
        pr_url="https://github.com/org/target/pull/1",
        pr_merged=True,
    )
    qa = next(a for a in agents if a.role == "qa")
    assert qa.status in ("active", "waiting", "done")
    reasons = detect_stuck_reasons(
        labels={"implemented"},
        lifecycle="implemented",
        comments=comments,
        pr_url="https://github.com/org/target/pull/1",
        pr_merged=True,
        agents=agents,
    )
    assert not any("never dispatched" in r for r in reasons)
