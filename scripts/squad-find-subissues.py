#!/usr/bin/env python3
"""Squad sub-issue discovery and deliverable completion checks."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys

VALIDATION_ROLES = ("qa", "security", "devops", "tech-writer")

DELIVERABLE_MARKERS: dict[str, tuple[str, ...]] = {
    "qa": ("# qa report",),
    "security": ("# security report",),
    "devops": ("# deployment checklist", "deployment checklist"),
    "tech-writer": ("# release notes",),
}


def gh_json(args: list[str]) -> list[dict] | dict:
    proc = subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout)


def parent_needle(parent: int) -> str:
    return f"issues/{parent}"


def find_subissue(repo: str, parent: int, role_label: str, *, state: str = "open") -> int | None:
    items = gh_json(
        [
            "issue",
            "list",
            "--repo",
            repo,
            "--label",
            role_label,
            "--state",
            state,
            "--json",
            "number,body",
            "--limit",
            "50",
        ]
    )
    needle = parent_needle(parent)
    for item in items:
        if needle in (item.get("body") or ""):
            return int(item["number"])
    return None


def find_subissue_any_state(repo: str, parent: int, role_label: str) -> int | None:
    for state in ("open", "closed"):
        sub = find_subissue(repo, parent, role_label, state=state)
        if sub is not None:
            return sub
    return None


def extract_target_repo(body: str) -> str | None:
    for match in re.finditer(r"https://github.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)", body):
        repo = match.group(1)
        if "ai-alpha-squad" not in repo.lower():
            return repo
    return None


def issue_text(repo: str, issue_number: int) -> str:
    data = gh_json(
        [
            "issue",
            "view",
            str(issue_number),
            "--repo",
            repo,
            "--json",
            "body,comments",
        ]
    )
    parts = [data.get("body") or ""]
    for comment in data.get("comments") or []:
        parts.append(comment.get("body") or "")
    return "\n".join(parts).lower()


def subissue_complete(repo: str, issue_number: int, role: str) -> bool:
    data = gh_json(
        [
            "issue",
            "view",
            str(issue_number),
            "--repo",
            repo,
            "--json",
            "state,body,comments",
        ]
    )
    if (data.get("state") or "").upper() == "CLOSED":
        return True
    text = issue_text(repo, issue_number)
    markers = DELIVERABLE_MARKERS.get(role, ())
    return any(marker in text for marker in markers)


def validation_matrix(repo: str, parent: int) -> dict[str, int]:
    found: dict[str, int] = {}
    for role in VALIDATION_ROLES:
        sub = find_subissue_any_state(repo, parent, role)
        if sub is not None:
            found[role] = sub
    return found


def validation_complete(repo: str, parent: int) -> tuple[bool, dict[str, bool]]:
    matrix = validation_matrix(repo, parent)
    if len(matrix) != len(VALIDATION_ROLES):
        return False, {role: False for role in VALIDATION_ROLES}
    status = {role: subissue_complete(repo, num, role) for role, num in matrix.items()}
    return all(status.values()), status


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", help="owner/name work queue repo")
    parser.add_argument("parent", type=int, help="parent issue number")
    parser.add_argument(
        "role",
        nargs="?",
        choices=[*VALIDATION_ROLES, "developer"],
        help="role label to find (omit to list validation sub-issues)",
    )
    parser.add_argument(
        "--target-repo",
        action="store_true",
        help="print target product repo from parent issue body",
    )
    parser.add_argument(
        "--state",
        default="open",
        choices=("open", "closed", "all"),
        help="sub-issue state filter (default: open)",
    )
    parser.add_argument(
        "--validation-complete",
        action="store_true",
        help="exit 0 when all validation sub-issues have deliverables",
    )
    parser.add_argument(
        "--validation-status",
        action="store_true",
        help="print JSON map of role -> complete bool",
    )
    args = parser.parse_args()

    if args.target_repo:
        issue = gh_json(["issue", "view", str(args.parent), "--repo", args.repo, "--json", "body"])
        target = extract_target_repo(issue.get("body") or "")
        if not target:
            return 1
        print(target)
        return 0

    if args.validation_complete:
        complete, _ = validation_complete(args.repo, args.parent)
        return 0 if complete else 1

    if args.validation_status:
        _, status = validation_complete(args.repo, args.parent)
        print(json.dumps(status))
        return 0

    if args.role:
        if args.state == "all":
            sub = find_subissue_any_state(args.repo, args.parent, args.role)
        else:
            sub = find_subissue(args.repo, args.parent, args.role, state=args.state)
        if sub is None:
            return 1
        print(sub)
        return 0

    found = validation_matrix(args.repo, args.parent)
    if not found:
        return 1
    print(json.dumps(found))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
