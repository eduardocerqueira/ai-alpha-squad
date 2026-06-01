"""Tests for queue-repo product PR detection."""
from __future__ import annotations

from ai_alpha_squad.pr_guard import (
    is_work_queue_repo,
    product_paths_in_diff,
    should_close_queue_product_pr,
)


def test_work_queue_repo_detection() -> None:
    assert is_work_queue_repo("eduardocerqueira/ai-alpha-squad")
    assert not is_work_queue_repo("eduardocerqueira/vscode-squad-director")


def test_python_src_allowed() -> None:
    assert product_paths_in_diff(["src/ai_alpha_squad/nudge.py"]) == []


def test_extension_paths_flagged() -> None:
    flagged = product_paths_in_diff(["package.json", "src/extension.ts"])
    assert "package.json" in flagged
    assert "src/extension.ts" in flagged


def test_site_ts_allowed() -> None:
    assert product_paths_in_diff(["site/public/app.ts"]) == []


def test_close_on_product_diff() -> None:
    close, reason = should_close_queue_product_pr(
        "eduardocerqueira/ai-alpha-squad",
        changed_paths=["package.json"],
        title="Add feature",
    )
    assert close is True
    assert "work-queue repo" in reason


def test_close_on_wip_extension_title_when_diff_empty() -> None:
    close, _ = should_close_queue_product_pr(
        "eduardocerqueira/ai-alpha-squad",
        changed_paths=[],
        title="[WIP] Add VS Code extension for Squad Director",
        body="",
    )
    assert close is True


def test_no_close_on_target_repo() -> None:
    close, reason = should_close_queue_product_pr(
        "eduardocerqueira/vscode-squad-director",
        changed_paths=["package.json", "src/extension.ts"],
        title="VS Code extension",
    )
    assert close is False
    assert reason == ""
