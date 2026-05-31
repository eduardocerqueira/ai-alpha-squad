"""Unit tests for squad project lifecycle/agent derivation."""
from ai_alpha_squad.project_sync import derive_state


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


def test_blocked():
    derived = derive_state({"blocked", "business-owner", "new"})
    assert derived.lifecycle == "blocked"
    assert derived.active_agent == "Blocked"


def test_release_candidate():
    derived = derive_state({"release-candidate", "release-manager"})
    assert derived.lifecycle == "release-candidate"
    assert derived.active_agent == "Director"
    assert derived.needs_director == "Yes"
