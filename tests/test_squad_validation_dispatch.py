"""Tests for Phase 4 parallel validation dispatch helpers."""
from __future__ import annotations

from ai_alpha_squad.validation_dispatch import (
    VALIDATION_DISPATCH_MARKER,
    VALIDATION_ROLES,
    parent_has_validation_dispatch,
    role_dispatch_marker,
)


def test_validation_roles_match_orchestrator_phase_four() -> None:
    assert VALIDATION_ROLES == ("qa", "security", "devops", "tech-writer")


def test_role_dispatch_marker_is_stable() -> None:
    assert role_dispatch_marker("qa") == "validation-dispatch:qa"


def test_parent_has_validation_dispatch_all_roles() -> None:
    comments = [{"body": f"**{VALIDATION_DISPATCH_MARKER}** on parent #17."}]
    assert parent_has_validation_dispatch(comments)


def test_parent_has_validation_dispatch_per_role() -> None:
    comments = [{"body": "validation-dispatch:security — assigned"}]
    assert parent_has_validation_dispatch(comments, role="security")
    assert not parent_has_validation_dispatch(comments, role="qa")
