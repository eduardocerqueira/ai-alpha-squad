"""Tests for queue-repo product PR detection."""
from __future__ import annotations

from ai_alpha_squad.pr_guard import (
    is_copilot_assignee,
    is_work_queue_repo,
    issue_numbers_from_pr_text,
    pick_guard_issue_number,
    pr_looks_like_planning_handoff,
    pr_looks_like_product_handoff,
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


def test_ba_handoff_not_product_pr_when_diff_empty() -> None:
    title = "Business Analysis handoff for Job 1: Squad Director (issue-first)"
    body = "Squad Director VS Code extension scope. # Business Analysis in summary."
    assert pr_looks_like_planning_handoff(title, body) is True
    assert pr_looks_like_product_handoff(title, body) is False
    close, reason = should_close_queue_product_pr(
        "eduardocerqueira/ai-alpha-squad",
        changed_paths=[],
        title=title,
        body=body,
    )
    assert close is False
    assert reason == ""


def test_no_close_on_target_repo() -> None:
    close, reason = should_close_queue_product_pr(
        "eduardocerqueira/vscode-squad-director",
        changed_paths=["package.json", "src/extension.ts"],
        title="VS Code extension",
    )
    assert close is False
    assert reason == ""


def test_pick_open_issue_over_closed_closes() -> None:
    picked = pick_guard_issue_number(
        [15],
        [17],
        state_by_number={15: "CLOSED", 17: "OPEN"},
    )
    assert picked == 17


def test_pick_highest_open_when_multiple() -> None:
    picked = pick_guard_issue_number(
        [],
        [12, 17],
        state_by_number={12: "OPEN", 17: "OPEN"},
    )
    assert picked == 17


def test_no_pick_when_all_closed() -> None:
    assert (
        pick_guard_issue_number(
            [15],
            [],
            state_by_number={15: "CLOSED"},
        )
        is None
    )


def test_issue_numbers_from_pr_text() -> None:
    nums = issue_numbers_from_pr_text("Closes #15\nRelated to issue #17")
    assert nums == [15, 17]


def test_is_copilot_assignee() -> None:
    assert is_copilot_assignee("Copilot")
    assert is_copilot_assignee("app/copilot-swe-agent")
    assert not is_copilot_assignee("eduardocerqueira")
