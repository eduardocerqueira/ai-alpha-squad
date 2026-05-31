"""Tests for squad sub-issue finder."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "squad_find_subissues",
    ROOT / "scripts" / "squad-find-subissues.py",
)
mod = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(mod)


def test_extract_target_repo_skips_work_queue() -> None:
    body = """
    Target repo: https://github.com/eduardocerqueira/seeker
    Tracking: https://github.com/eduardocerqueira/ai-alpha-squad/issues/1
    """
    assert mod.extract_target_repo(body) == "eduardocerqueira/seeker"


def test_extract_target_repo_none_when_missing() -> None:
    assert mod.extract_target_repo("no links here") is None


def test_subissue_complete_detects_marker() -> None:
    text = "Some work\n\n# QA Report\n\nResult: PASS"
    markers = mod.DELIVERABLE_MARKERS["qa"]
    assert any(m in text.lower() for m in markers)


def test_deliverable_markers_cover_all_validation_roles() -> None:
    assert set(mod.DELIVERABLE_MARKERS) == set(mod.VALIDATION_ROLES)
