#!/usr/bin/env python3
"""Run autonomous planning fallback (job pack → issue comment) when Copilot stalls."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_alpha_squad.autonomous_planning import try_autonomous_planning_fallback  # noqa: E402
from ai_alpha_squad.nudge import PHASE_MARKERS, issue_has_deliverable  # noqa: E402
from ai_alpha_squad.planning_delivery import copilot_prs_for_issue, phase_for_labels  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo")
    parser.add_argument("issue", type=int)
    parser.add_argument(
        "--phase",
        choices=sorted(PHASE_MARKERS),
        help="Override phase (default: infer from labels)",
    )
    parser.add_argument("--force", action="store_true", help="Run even if nudge threshold not met")
    args = parser.parse_args()

    data = json.loads(
        subprocess.check_output(
            [
                "gh",
                "issue",
                "view",
                str(args.issue),
                "--repo",
                args.repo,
                "--json",
                "title,body,comments,labels,createdAt",
            ],
            text=True,
        )
    )
    labels = {x["name"] for x in data.get("labels", [])}
    phase = args.phase or phase_for_labels(labels)
    if not phase:
        print(f"Issue #{args.issue}: not in a planning phase")
        return 0

    marker = PHASE_MARKERS[phase]
    comments = data.get("comments", [])
    if issue_has_deliverable(comments, marker):
        print(f"Issue #{args.issue}: already has {marker!r}")
        return 0

    has_prs = bool(copilot_prs_for_issue(args.repo, args.issue))
    if try_autonomous_planning_fallback(
        args.repo,
        args.issue,
        phase,
        ROOT,
        issue_title=data.get("title", ""),
        issue_body=data.get("body", ""),
        comments=comments,
        has_open_copilot_pr=has_prs,
        issue_created_at=data.get("createdAt"),
        force=args.force,
    ):
        sync = ROOT / "scripts" / "squad-sync-planning-labels.sh"
        subprocess.run([str(sync), args.repo, str(args.issue)], check=False)
        project_sync = ROOT / "scripts" / "squad_project_sync.py"
        subprocess.run(
            ["python3", str(project_sync), "--repo", args.repo, "sync-issue", str(args.issue)],
            check=False,
        )
        print(f"Issue #{args.issue}: autonomous {phase} fallback applied")
        return 0

    print(f"Issue #{args.issue}: autonomous fallback did not run or failed", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
