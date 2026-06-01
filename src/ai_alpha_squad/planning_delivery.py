"""Issue-first planning: promote Copilot PR content onto queue-repo issues."""
from __future__ import annotations

import base64
import re
import subprocess
from urllib.parse import quote

from ai_alpha_squad.nudge import (
    PHASE_MARKERS,
    PROMOTE_MARKER,
    extract_deliverable_section,
    has_heading_marker,
    is_substantive_deliverable,
    issue_has_deliverable,
)
from ai_alpha_squad.pr_guard import (
    issue_numbers_from_pr_text,
    is_copilot_assignee,
    pick_guard_issue_number,
)

# Markdown paths Copilot often uses for planning deliverables on a PR branch.
PLANNING_FILE_HINTS = re.compile(
    r"(business[-_]?analysis|ba\.md$|tech[-_]?spec|technical[-_]?spec)",
    re.IGNORECASE,
)


def phase_for_labels(labels: set[str]) -> str | None:
    if "director-approved" in labels and "designed" not in labels:
        return "architect"
    if "new" in labels or ("business-owner" in labels and "awaiting-approval" not in labels):
        return "business-owner"
    return None


def extract_deliverable_from_sources(
    text: str,
    markdown_files: dict[str, str],
    marker: str,
) -> str | None:
    """Try PR body/title, then each markdown file on the PR branch."""
    if section := extract_deliverable_section(text, marker):
        return section
    for path in sorted(markdown_files, key=lambda p: (not PLANNING_FILE_HINTS.search(p), p)):
        content = markdown_files[path]
        if not content.strip():
            continue
        if section := extract_deliverable_section(content, marker):
            return section
        if has_heading_marker(content, marker) and is_substantive_deliverable(content, marker):
            return content.strip()
    return None


def list_pr_changed_markdown_paths(repo: str, pr_number: int) -> list[str]:
    owner, name = repo.split("/", 1)
    proc = subprocess.run(
        [
            "gh",
            "api",
            f"repos/{owner}/{name}/pulls/{pr_number}/files",
            "--paginate",
            "-q",
            '.[] | select(.filename | endswith(".md")) | select(.status != "removed") | .filename',
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def fetch_ref_file_text(repo: str, path: str, ref: str) -> str | None:
    owner, name = repo.split("/", 1)
    encoded = quote(path, safe="")
    proc = subprocess.run(
        [
            "gh",
            "api",
            f"repos/{owner}/{name}/contents/{encoded}",
            "-f",
            f"ref={ref}",
            "-q",
            ".content",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    try:
        return base64.b64decode(proc.stdout.strip()).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None


def load_pr_markdown_files(repo: str, pr_number: int) -> dict[str, str]:
    ref = subprocess.run(
        ["gh", "pr", "view", str(pr_number), "--repo", repo, "--json", "headRefName", "-q", ".headRefName"],
        capture_output=True,
        text=True,
        check=False,
    )
    if ref.returncode != 0:
        return {}
    branch = ref.stdout.strip()
    if not branch:
        return {}
    out: dict[str, str] = {}
    for path in list_pr_changed_markdown_paths(repo, pr_number):
        text = fetch_ref_file_text(repo, path, branch)
        if text:
            out[path] = text
    return out


def promote_pr_to_issue(
    repo: str,
    issue: int,
    pr_number: int,
    phase: str,
) -> bool:
    """Post deliverable on issue when found in PR body or branch markdown files."""
    marker = PHASE_MARKERS[phase]
    proc = subprocess.run(
        ["gh", "issue", "view", str(issue), "--repo", repo, "--json", "comments"],
        capture_output=True,
        text=True,
        check=True,
    )
    import json

    comments = json.loads(proc.stdout)["comments"]
    if issue_has_deliverable(comments, marker):
        return True

    pr_proc = subprocess.run(
        ["gh", "pr", "view", str(pr_number), "--repo", repo, "--json", "body,title"],
        capture_output=True,
        text=True,
        check=True,
    )
    pr_data = json.loads(pr_proc.stdout)
    text = f"{pr_data.get('title', '')}\n{pr_data.get('body', '')}"
    files = load_pr_markdown_files(repo, pr_number)
    section = extract_deliverable_from_sources(text, files, marker)
    if not section:
        return False

    body = (
        f"**{PROMOTE_MARKER}** — Copilot posted this on PR #{pr_number}; "
        "orchestrator copied it here for issue-first policy.\n\n"
        f"{section}\n"
    )
    subprocess.run(
        ["gh", "issue", "comment", str(issue), "--repo", repo, "--body", body],
        check=True,
    )
    return True


def resolve_pr_issue_number(repo: str, pr_number: int) -> int | None:
    """Same resolution rules as squad-resolve-guard-issue.py."""
    import json

    owner, name = repo.split("/", 1)
    pr_view = subprocess.run(
        ["gh", "pr", "view", str(pr_number), "--repo", repo, "--json", "body,title"],
        capture_output=True,
        text=True,
        check=False,
    )
    pr_text = ""
    if pr_view.returncode == 0:
        data = json.loads(pr_view.stdout)
        pr_text = f"{data.get('title', '')}\n{data.get('body', '')}"

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
        nodes = (
            json.loads(proc.stdout)
            .get("data", {})
            .get("repository", {})
            .get("pullRequest", {})
            .get("closingIssuesReferences", {})
            .get("nodes", [])
        )
        for node in nodes:
            num = int(node["number"])
            closing.append(num)
            state_by_number[num] = node.get("state") or "OPEN"

    for num in issue_numbers_from_pr_text(pr_text):
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

    return pick_guard_issue_number(closing, issue_numbers_from_pr_text(pr_text), state_by_number=state_by_number)


def list_open_copilot_pr_numbers(repo: str) -> list[int]:
    import json

    proc = subprocess.run(
        [
            "gh",
            "pr",
            "list",
            "--repo",
            repo,
            "--state",
            "open",
            "--limit",
            "30",
            "--json",
            "number,author",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    numbers: list[int] = []
    for pr in json.loads(proc.stdout):
        login = (pr.get("author") or {}).get("login", "")
        if is_copilot_assignee(login):
            numbers.append(int(pr["number"]))
    return numbers


def copilot_prs_for_issue(repo: str, issue: int) -> list[int]:
    matched: list[int] = []
    for pr in list_open_copilot_pr_numbers(repo):
        if resolve_pr_issue_number(repo, pr) == issue:
            matched.append(pr)
    return matched
