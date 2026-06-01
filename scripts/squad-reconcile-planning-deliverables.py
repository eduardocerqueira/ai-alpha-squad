#!/usr/bin/env python3
"""Reconcile issue-first planning: promote from Copilot PRs, run guard, sync labels."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_alpha_squad.nudge import PHASE_MARKERS, issue_has_deliverable  # noqa: E402
from ai_alpha_squad.planning_delivery import (  # noqa: E402
    copilot_prs_for_issue,
    phase_for_labels,
    promote_pr_to_issue,
)


def issue_labels(repo: str, issue: int) -> set[str]:
    data = json.loads(
        subprocess.check_output(
            ["gh", "issue", "view", str(issue), "--repo", repo, "--json", "labels"],
            text=True,
        )
    )
    return {x["name"] for x in data.get("labels", [])}


def issue_comments(repo: str, issue: int) -> list[dict]:
    data = json.loads(
        subprocess.check_output(
            ["gh", "issue", "view", str(issue), "--repo", repo, "--json", "comments"],
            text=True,
        )
    )
    return data.get("comments", [])


def run_script(script: Path, *args: str) -> None:
    subprocess.run([str(script), *args], check=False)


def reconcile_once(repo: str, issue: int, root: Path) -> bool:
    """Return True when the issue has the expected planning deliverable."""
    labels = issue_labels(repo, issue)
    phase = phase_for_labels(labels)
    if not phase:
        print(f"Issue #{issue}: not in planning reconcile phase")
        return True

    marker = PHASE_MARKERS[phase]
    comments = issue_comments(repo, issue)
    if issue_has_deliverable(comments, marker):
        print(f"Issue #{issue}: already has {marker!r}")
        return True

    prs = copilot_prs_for_issue(repo, issue)
    if not prs:
        print(f"Issue #{issue}: no open Copilot PRs linked")
        return False

    approve = root / "scripts" / "squad-approve-copilot-workflows.sh"
    guard = root / "scripts" / "squad-copilot-pr-guard.sh"
    for pr in prs:
        print(f"Issue #{issue}: PR #{pr} phase={phase}")
        promote_pr_to_issue(repo, issue, pr, phase)
        run_script(approve, repo, str(pr))
        run_script(guard, repo, str(pr))

    comments = issue_comments(repo, issue)
    return issue_has_deliverable(comments, marker)


def finalize(repo: str, issue: int, root: Path) -> None:
    labels = issue_labels(repo, issue)
    phase = phase_for_labels(labels)
    if not phase:
        return
    sync = root / "scripts" / "squad-sync-planning-labels.sh"
    run_script(sync, repo, str(issue), phase)
    project_sync = root / "scripts" / "squad_project_sync.py"
    if project_sync.is_file():
        subprocess.run(
            ["python3", str(project_sync), "--repo", repo, "sync-issue", str(issue)],
            check=False,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo")
    parser.add_argument("issue", type=int)
    parser.add_argument(
        "--wait-minutes",
        type=int,
        default=0,
        help="Poll every 3 minutes until deliverable or timeout",
    )
    args = parser.parse_args()
    root = ROOT

    if args.wait_minutes <= 0:
        ok = reconcile_once(args.repo, args.issue, root)
        finalize(args.repo, args.issue, root)
        return 0 if ok else 1

    deadline = time.time() + args.wait_minutes * 60
    while time.time() < deadline:
        if reconcile_once(args.repo, args.issue, root):
            finalize(args.repo, args.issue, root)
            print(f"Issue #{args.issue}: reconciled")
            return 0
        time.sleep(180)

    finalize(args.repo, args.issue, root)
    print(f"Issue #{args.issue}: reconcile window ended without deliverable", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
