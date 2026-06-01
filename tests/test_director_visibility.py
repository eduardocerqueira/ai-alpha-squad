"""Tests for Director status and project sync helpers."""

from ai_alpha_squad.project_sync import derive_state


def test_subissue_inherits_parent_lifecycle_on_board() -> None:
    derived = derive_state(
        {"developer", "medium"},
        parent_labels={"designed", "medium"},
    )
    assert derived.lifecycle == "designed"
    assert derived.active_agent == "developer"


def test_subissue_qa_shows_qa_not_developer_when_parent_designed() -> None:
    derived = derive_state(
        {"qa", "medium"},
        parent_labels={"designed", "medium"},
    )
    assert derived.lifecycle == "designed"
    assert derived.active_agent == "qa"
