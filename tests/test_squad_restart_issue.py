"""Tests for squad-restart-issue helper logic."""
from __future__ import annotations

import runpy
from pathlib import Path


MODULE = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "scripts" / "squad-restart-issue.py")
)
collapse_reset_banners = MODULE["collapse_reset_banners"]
prepend_reset_banner = MODULE["prepend_reset_banner"]


def test_collapse_reset_banners_drops_duplicates() -> None:
    body = (
        "> **Director reset (2026-06-01):** Job restarted on this issue. Previous run: #57.\n"
        "> more context\n\n"
        "> **Director reset (2026-06-01):** Job restarted on this issue. Previous run: #17.\n"
        "> duplicate context\n\n"
        "## Summary\nWork details.\n"
    )
    out = collapse_reset_banners(body)
    assert out.count("> **Director reset") == 1
    assert "Previous run: #57" in out
    assert "Previous run: #17" not in out


def test_prepend_reset_banner_keeps_single_banner() -> None:
    body = (
        "> **Director reset (2026-06-01):** Job restarted on this issue. Previous run: #57.\n\n"
        "## Summary\nWork details.\n"
    )
    out = prepend_reset_banner(body, 64)
    assert out.count("> **Director reset") == 1
    assert "Previous run: #64 (closed for clean restart)." in out
