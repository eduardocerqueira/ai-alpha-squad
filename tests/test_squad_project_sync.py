"""Unit tests for squad project lifecycle/agent derivation."""
from ai_alpha_squad.project_sync import (
    AGENT_PENDING_ON_ISSUE,
    PARALLEL_VALIDATION_AGENT,
    PlanningDeliverables,
    derive_state,
    format_active_agent,
)


def test_new_without_ba_shows_blocked_on_issue() -> None:
    derived = derive_state(
        {"new", "medium"},
        planning=PlanningDeliverables(has_business_analysis=False),
    )
    assert derived.lifecycle == "new"
    assert derived.active_agent == AGENT_PENDING_ON_ISSUE


def test_new_with_ba_shows_business_owner() -> None:
    derived = derive_state(
        {"new", "medium"},
        planning=PlanningDeliverables(has_business_analysis=True),
    )
    assert derived.active_agent == "business-owner"


def test_awaiting_approval_shows_director():
    derived = derive_state({"business-owner", "awaiting-approval", "medium"})
    assert derived.lifecycle == "awaiting-approval"
    assert derived.active_agent == "Director"
    assert derived.needs_director == "Yes"


def test_designed_shows_developer():
    derived = derive_state({"business-owner", "developer", "designed"})
    assert derived.lifecycle == "designed"
    assert derived.active_agent == "developer"
    assert derived.needs_director == "No"


def test_subissue_qa():
    derived = derive_state({"qa", "implemented"})
    assert derived.lifecycle == "implemented"
    assert derived.active_agent == "qa"


def test_implemented_parallel_validation_agents():
    derived = derive_state({"qa", "security", "devops", "implemented"})
    assert derived.active_agent == PARALLEL_VALIDATION_AGENT


def test_architect_copilot_session_suffix():
    derived = derive_state(
        {"director-approved", "business-owner"},
        copilot_sessions=2,
        planning=PlanningDeliverables(has_technical_spec=True),
    )
    assert derived.active_agent == "architect (Copilot x2)"


def test_format_active_agent_single_session():
    assert format_active_agent("architect", copilot_sessions=1) == "architect"


def test_blocked():
    derived = derive_state({"blocked", "business-owner", "new"})
    assert derived.lifecycle == "blocked"
    assert derived.active_agent == "Blocked"


def test_release_candidate():
    derived = derive_state({"release-candidate", "release-manager"})
    assert derived.lifecycle == "release-candidate"
    assert derived.active_agent == "Director"
    assert derived.needs_director == "Yes"
