#!/usr/bin/env python3
"""Resolve which issue a Copilot PR guard action should target."""
from __future__ import annotations

import json
import subprocess
import sys

from ai_alpha_squad.pr_guard import issue_numbers_from_pr_text, pick_guard_issue_number


def main() -> int:
    if len(sys.argv) != 4:
        print("usage: squad-resolve-guard-issue.py <owner/repo> <pr_number> <pr_text>", file=sys.stderr)
        return 2

    repo = sys.argv[1]
    pr_number = int(sys.argv[2])
    pr_text = sys.argv[3]

    owner, name = repo.split("/", 1)
    query = (
        "query($owner: String!, $name: String!, $pr: Int!) {"
        " repository(owner: $owner, name: $name) {"
        " pullRequest(number: $pr) {"
        " closingIssuesReferences(first: 10) { nodes { number state } }"
        " } } }"
    )
    proc = subprocess.run(
        [
            "gh",
            "api",
            "graphql",
            "-f",
            f"query={query}",
            "-f",
            f"owner={owner}",
            "-f",
            f"name={name}",
            "-F",
            f"pr={pr_number}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    closing: list[int] = []
    state_by_number: dict[int, str] = {}
    if proc.returncode == 0:
        payload = json.loads(proc.stdout)
        nodes = (
            payload.get("data", {})
            .get("repository", {})
            .get("pullRequest", {})
            .get("closingIssuesReferences", {})
            .get("nodes", [])
        )
        for node in nodes:
            num = int(node["number"])
            closing.append(num)
            state_by_number[num] = node.get("state") or "OPEN"

    body_numbers = issue_numbers_from_pr_text(pr_text)
    for num in body_numbers:
        if num in state_by_number:
            continue
        view = subprocess.run(
            ["gh", "issue", "view", str(num), "--repo", repo, "--json", "state"],
            capture_output=True,
            text=True,
            check=False,
        )
        if view.returncode == 0:
            state_by_number[num] = json.loads(view.stdout).get("state", "OPEN")

    picked = pick_guard_issue_number(closing, body_numbers, state_by_number=state_by_number)
    if picked is not None:
        print(picked)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
