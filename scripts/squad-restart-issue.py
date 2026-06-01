#!/usr/bin/env python3
"""Close an issue and open a restarted copy without duplicate reset banners."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone

RESET_LINE_RE = re.compile(
    r"^> \*\*Director reset \([^)]+\):\*\* Job restarted on this issue\..*$",
    re.MULTILINE,
)


def gh_json(args: list[str]) -> dict:
    proc = subprocess.run(["gh", *args], capture_output=True, text=True, check=True)
    return json.loads(proc.stdout)


def collapse_reset_banners(body: str) -> str:
    """Keep only the first reset banner block, drop duplicates."""
    lines = body.splitlines()
    out: list[str] = []
    seen = False
    i = 0
    while i < len(lines):
        line = lines[i]
        if RESET_LINE_RE.match(line):
            if seen:
                i += 1
                while i < len(lines) and lines[i].startswith(">"):
                    i += 1
                continue
            seen = True
        out.append(line)
        i += 1
    return "\n".join(out).strip() + "\n"


def prepend_reset_banner(body: str, previous_issue: int) -> str:
    body = collapse_reset_banners(body).lstrip()
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    banner = (
        f"> **Director reset ({stamp}):** Job restarted on this issue. "
        f"Previous run: #{previous_issue} (closed for clean restart). "
        "Follow issue-first: deliverables as **issue comments only** on "
        "`ai-alpha-squad`; code only on `vscode-squad-director`.\n\n"
    )
    return banner + body


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", help="owner/repo")
    parser.add_argument("issue", type=int, help="issue number to restart")
    parser.add_argument(
        "--label",
        action="append",
        default=["new", "medium"],
        help="label(s) to apply on the new issue (default: new, medium)",
    )
    args = parser.parse_args()

    issue = gh_json(
        [
            "issue",
            "view",
            str(args.issue),
            "--repo",
            args.repo,
            "--json",
            "title,body",
        ]
    )
    title = issue["title"]
    new_body = prepend_reset_banner(issue.get("body", ""), args.issue)

    subprocess.run(
        [
            "gh",
            "issue",
            "close",
            str(args.issue),
            "--repo",
            args.repo,
            "--comment",
            "Closed for clean restart; replacement issue opened by squad-restart-issue.py.",
        ],
        check=True,
    )

    cmd = ["gh", "issue", "create", "--repo", args.repo, "--title", title, "--body", new_body]
    for label in sorted(set(args.label)):
        cmd.extend(["--label", label])
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    print(proc.stdout.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
