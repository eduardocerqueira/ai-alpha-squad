"""Create Architect validation sub-issues when HF cannot run gh issue create."""

from __future__ import annotations

import json
import re
import subprocess
import sys

from ai_alpha_squad.agent_models import repo_root
from ai_alpha_squad.autonomous_planning import create_architect_subissues
from ai_alpha_squad.nudge import PHASE_MARKERS, architect_subissues_complete, issue_has_deliverable


def parse_target_repo(issue_body: str) -> str | None:
    patterns = (
        r"Target repo:\s*`?([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)`?",
        r"github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, issue_body or "", re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def _gh_json(args: list[str]) -> dict:
    proc = subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout)


def _existing_subissue_counts(queue_repo: str, parent: int) -> dict[str, int | None]:
    subs: dict[str, int | None] = {}
    for role in ("developer", "qa", "security", "devops", "tech-writer"):
        proc = subprocess.run(
            [
                "python3",
                str(repo_root() / "scripts/squad-find-subissues.py"),
                queue_repo,
                str(parent),
                role,
                "--state",
                "all",
            ],
            capture_output=True,
            text=True,
            cwd=repo_root(),
        )
        subs[role] = int(proc.stdout.strip()) if proc.returncode == 0 else None
    return subs


def ensure_architect_subissues(queue_repo: str, parent: int) -> dict[str, int]:
    """
    Create missing Architect sub-issues after tech spec is on the parent issue.

    Returns role -> issue number for created or existing (empty if tech spec missing).
    """
    data = _gh_json(
        [
            "issue",
            "view",
            str(parent),
            "--repo",
            queue_repo,
            "--json",
            "title,body,comments",
        ]
    )
    comments = data.get("comments") or []
    if not issue_has_deliverable(comments, PHASE_MARKERS["architect"]):
        return {}

    subs = _existing_subissue_counts(queue_repo, parent)
    if architect_subissues_complete(subs):
        return {k: v for k, v in subs.items() if v is not None}

    target_repo = parse_target_repo(data.get("body") or "") or "eduardocerqueira/vscode-squad-director"
    title = (data.get("title") or f"Job #{parent}").strip()
    created = create_architect_subissues(queue_repo, parent, target_repo, title)
    try:
        from ai_alpha_squad.director_visibility import post_director_status, sync_project_family

        post_director_status(queue_repo, parent)
        sync_project_family(queue_repo, parent)
    except Exception as exc:
        print(f"Director visibility sync skipped: {exc}", file=sys.stderr)
    return created
