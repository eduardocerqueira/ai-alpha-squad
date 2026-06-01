#!/usr/bin/env python3
"""Promote a planning deliverable from a Copilot PR body onto the linked issue."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_alpha_squad.nudge import (  # noqa: E402
    PHASE_MARKERS,
    PROMOTE_MARKER,
    extract_deliverable_section,
    issue_has_deliverable,
)


def gh_json(args: list[str]) -> dict | list:
    proc = subprocess.run(["gh", *args], capture_output=True, text=True, check=True)
    return json.loads(proc.stdout)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", help="owner/name")
    parser.add_argument("issue", type=int, help="Issue number")
    parser.add_argument("pr", type=int, help="Pull request number")
    parser.add_argument(
        "--phase",
        choices=sorted(PHASE_MARKERS),
        required=True,
        help="Planning phase (maps to deliverable marker)",
    )
    args = parser.parse_args()

    marker = PHASE_MARKERS[args.phase]
    pr_view = gh_json(
        [
            "pr",
            "view",
            str(args.pr),
            "--repo",
            args.repo,
            "--json",
            "body,title",
        ]
    )
    text = f"{pr_view.get('title', '')}\n{pr_view.get('body', '')}"
    section = extract_deliverable_section(text, marker)
    if not section:
        print(f"No substantive {marker!r} section in PR #{args.pr}", file=sys.stderr)
        return 1

    issue_data = gh_json(
        [
            "issue",
            "view",
            str(args.issue),
            "--repo",
            args.repo,
            "--json",
            "comments",
        ]
    )
    comments = issue_data.get("comments") or []
    if issue_has_deliverable(comments, marker):
        print(f"Issue #{args.issue} already has {marker}")
        return 0

    body = (
        f"**{PROMOTE_MARKER}** — Copilot posted this on PR #{args.pr}; "
        "orchestrator copied it here for issue-first policy.\n\n"
        f"{section}\n"
    )
    subprocess.run(
        [
            "gh",
            "issue",
            "comment",
            str(args.issue),
            "--repo",
            args.repo,
            "--body",
            body,
        ],
        check=True,
    )
    print(f"Promoted {marker} from PR #{args.pr} to issue #{args.issue}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
