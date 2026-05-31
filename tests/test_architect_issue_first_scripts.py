from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run(script_name: str, *args: str) -> subprocess.CompletedProcess[str]:
    script = REPO_ROOT / "scripts" / script_name
    return subprocess.run(["bash", str(script), *args], cwd=REPO_ROOT, text=True, capture_output=True, check=False)


def test_squad_label_dry_run_outputs_expected_commands() -> None:
    result = _run(
        "squad-label.sh",
        "--repo",
        "owner/repo",
        "--issue",
        "17",
        "--add",
        "designed,in-progress",
        "--remove",
        "director-approved",
        "--dry-run",
    )

    assert result.returncode == 0
    assert "gh issue edit 17 --repo owner/repo --add-label designed" in result.stdout
    assert "gh issue edit 17 --repo owner/repo --add-label in-progress" in result.stdout
    assert "gh issue edit 17 --repo owner/repo --remove-label director-approved" in result.stdout


def test_squad_delivery_complete_dry_run_outputs_comment_command() -> None:
    result = _run(
        "squad-delivery-complete.sh",
        "--repo",
        "owner/repo",
        "--issue",
        "17",
        "--dry-run",
    )

    assert result.returncode == 0
    assert "gh issue comment 17 --repo owner/repo" in result.stdout
    assert "Squad deliverable complete on this issue." in result.stdout


def test_close_copilot_planning_pr_dry_run_outputs_close_commands() -> None:
    result = _run(
        "close-copilot-planning-pr.sh",
        "--repo",
        "owner/repo",
        "--pr",
        "18",
        "--issue",
        "17",
        "--dry-run",
    )

    assert result.returncode == 0
    assert "gh pr comment 18 --repo owner/repo" in result.stdout
    assert "gh pr close 18 --repo owner/repo" in result.stdout


def test_create_sub_issues_dry_run_generates_five_issues() -> None:
    result = _run(
        "squad-create-sub-issues.sh",
        "--repo",
        "owner/repo",
        "--parent-issue",
        "17",
        "--target-repo",
        "owner/target",
        "--spec-link",
        "https://github.com/owner/repo/issues/17#issuecomment-1",
        "--dry-run",
    )

    assert result.returncode == 0
    assert result.stdout.count("gh issue create --repo owner/repo") == 5
    assert "Sub-issue creation complete for parent issue #17" in result.stdout
