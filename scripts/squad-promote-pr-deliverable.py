#!/usr/bin/env python3
"""Promote a planning deliverable from a Copilot PR (body or branch .md files) onto the issue."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_alpha_squad.nudge import PHASE_MARKERS  # noqa: E402
from ai_alpha_squad.planning_delivery import promote_pr_to_issue  # noqa: E402


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

    if promote_pr_to_issue(args.repo, args.issue, args.pr, args.phase):
        print(f"Promoted {PHASE_MARKERS[args.phase]!r} from PR #{args.pr} to issue #{args.issue}")
        return 0
    print(
        f"No substantive {PHASE_MARKERS[args.phase]!r} in PR #{args.pr} body or branch markdown",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
