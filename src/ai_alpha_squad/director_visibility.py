"""Director-facing job status comments and project-board sync for a parent + sub-issues."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ai_alpha_squad.comments import format_squad_comment
from ai_alpha_squad.hf_dispatch import parse_parent_issue_number, post_issue_comment
from ai_alpha_squad.nudge import ARCHITECT_SUBISSUE_ROLES, PHASE_MARKERS, issue_has_deliverable
from ai_alpha_squad.project_sync import current_lifecycle


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]

DIRECTOR_STATUS_MARKER = "Squad Director status"
DEFAULT_PROJECT_URL = "https://github.com/users/eduardocerqueira/projects/6/views/9"

_VALIDATION_MARKERS: dict[str, str] = {
    "qa": "# qa report",
    "security": "# security report",
    "devops": "# deployment checklist",
    "tech-writer": "# release notes",
}


def _validation_marker(role: str) -> str:
    return _VALIDATION_MARKERS.get(role, "")


@dataclass(frozen=True)
class Checkpoint:
    name: str
    status: str  # done | in_progress | pending | blocked
    detail: str
    link: str = ""


def _gh_issue_json(repo: str, issue: int, fields: str) -> dict:
    proc = subprocess.run(
        ["gh", "issue", "view", str(issue), "--repo", repo, "--json", fields],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout)


def _subissue_number(repo: str, parent: int, role: str) -> int | None:
    root = Path(os.environ.get("SQUAD_REPO_ROOT", _repo_root()))
    script = root / "scripts" / "squad-find-subissues.py"
    proc = subprocess.run(
        ["python3", str(script), "--state", "all", repo, str(parent), role],
        capture_output=True,
        text=True,
        cwd=root,
    )
    if proc.returncode != 0:
        return None
    try:
        return int(proc.stdout.strip())
    except ValueError:
        return None


def resolve_parent_issue(repo: str, issue: int) -> int:
    """Parent job issue when `issue` is a sub-issue; otherwise `issue` itself."""
    data = _gh_issue_json(repo, issue, "body")
    parent = parse_parent_issue_number(data.get("body") or "")
    return parent if parent and parent != issue else issue


def _lifecycle_label(labels: list[str]) -> str | None:
    return current_lifecycle(set(labels))


def _checkpoint_icon(status: str) -> str:
    return {
        "done": "✅",
        "in_progress": "🔄",
        "pending": "⬜",
        "blocked": "🚫",
    }.get(status, "⬜")


def build_checkpoints(
    repo: str,
    parent: int,
    *,
    agent: str = "",
    pr_url: str = "",
    target_repo: str = "",
) -> list[Checkpoint]:
    parent_data = _gh_issue_json(repo, parent, "title,labels,comments,body")
    labels = [item["name"] for item in parent_data.get("labels") or []]
    comments = parent_data.get("comments") or []
    lifecycle = _lifecycle_label(labels)

    has_ba = issue_has_deliverable(comments, PHASE_MARKERS["business-owner"])
    has_spec = issue_has_deliverable(comments, PHASE_MARKERS["architect"])

    subs: dict[str, int | None] = {
        role: _subissue_number(repo, parent, role) for role in ARCHITECT_SUBISSUE_ROLES
    }

    checkpoints: list[Checkpoint] = []

    ba_status = "done" if has_ba or lifecycle not in (None, "new") else "pending"
    if "awaiting-approval" in labels:
        ba_status = "in_progress"
    checkpoints.append(
        Checkpoint(
            "Business Analysis",
            ba_status,
            "Posted on parent issue" if has_ba else "Waiting for Business Owner",
            link=f"https://github.com/{repo}/issues/{parent}",
        )
    )

    spec_status = "done" if has_spec or lifecycle in ("designed", "implemented", "validation", "release-candidate", "released") else "pending"
    if lifecycle == "director-approved" and not has_spec:
        spec_status = "in_progress"
    checkpoints.append(
        Checkpoint(
            "Technical specification + sub-issues",
            spec_status,
            f"Sub-issues: {', '.join(f'#{n}' for n in subs.values() if n) or 'none'}",
            link=f"https://github.com/{repo}/issues/{parent}",
        )
    )

    dev_num = subs.get("developer")
    if pr_url:
        dev_status, dev_detail = "in_progress", f"PR ready for review — merge on `{target_repo}` when satisfied"
    elif lifecycle == "implemented":
        dev_status, dev_detail = "done", "Implementation phase complete"
    elif lifecycle == "designed" and agent == "developer":
        dev_status, dev_detail = "in_progress", "Developer agent running"
    else:
        dev_status, dev_detail = "pending", "Opens after design / in parallel with validation planning"
    dev_link = pr_url or (f"https://github.com/{repo}/issues/{dev_num}" if dev_num else "")
    checkpoints.append(Checkpoint("Developer implementation", dev_status, dev_detail, link=dev_link))

    validation_roles = ("qa", "security", "devops", "tech-writer")
    val_done = 0
    val_parts: list[str] = []
    for role in validation_roles:
        num = subs.get(role)
        if not num:
            val_parts.append(f"{role}: —")
            continue
        sub = _gh_issue_json(repo, num, "comments")
        marker = _validation_marker(role)
        complete = issue_has_deliverable(sub.get("comments") or [], marker) if marker else False
        if complete:
            val_done += 1
        val_parts.append(f"{role}: {'done' if complete else 'pending'} (#{num})")
    if lifecycle in ("validation", "release-candidate", "released"):
        val_status = "in_progress" if val_done < len(validation_roles) else "done"
    elif lifecycle == "implemented":
        val_status = "in_progress"
    else:
        val_status = "pending"
    checkpoints.append(
        Checkpoint(
            "Validation (QA, Security, DevOps, Docs)",
            val_status,
            "; ".join(val_parts),
        )
    )

    if "awaiting-approval" in labels:
        dir_status, dir_detail = "in_progress", "Reply **APPROVE** on the parent issue (Director only)"
    elif "release-candidate" in labels:
        dir_status, dir_detail = "in_progress", "Release candidate — approve or reject on parent issue"
    elif lifecycle == "released":
        dir_status, dir_detail = "done", "Shipped"
    else:
        dir_status, dir_detail = "pending", "No approval needed at this phase"
    checkpoints.append(Checkpoint("Director gate", dir_status, dir_detail, link=f"https://github.com/{repo}/issues/{parent}"))

    return checkpoints


def format_director_status_comment(
    repo: str,
    parent: int,
    *,
    agent: str = "",
    pr_url: str = "",
    target_repo: str = "",
    trigger_issue: int | None = None,
) -> str:
    parent_data = _gh_issue_json(repo, parent, "title,labels")
    title = parent_data.get("title") or f"Issue #{parent}"
    labels = [item["name"] for item in parent_data.get("labels") or []]
    lifecycle = _lifecycle_label(labels) or "—"
    board_url = os.environ.get("SQUAD_PROJECT_BOARD_URL", DEFAULT_PROJECT_URL)

    checkpoints = build_checkpoints(
        repo, parent, agent=agent, pr_url=pr_url, target_repo=target_repo
    )
    lines = [
        f"**{DIRECTOR_STATUS_MARKER}** — Job **#{parent}**",
        "",
        f"**Phase:** `{lifecycle}` · **Job:** {title}",
        "",
        "| Step | Status | Detail |",
        "| ---- | ------ | ------ |",
    ]
    for cp in checkpoints:
        link = f" · [open]({cp.link})" if cp.link else ""
        lines.append(
            f"| {cp.name} | {_checkpoint_icon(cp.status)} {cp.status} | {cp.detail}{link} |"
        )

    lines.extend(
        [
            "",
            f"**Pipeline board:** {board_url}",
            f"**Parent issue:** https://github.com/{repo}/issues/{parent}",
        ]
    )
    if trigger_issue and trigger_issue != parent:
        lines.append(f"**Updated from sub-issue:** #{trigger_issue}")
    if pr_url:
        lines.append(f"**Target PR:** {pr_url}")

    body = "\n".join(lines)
    return format_squad_comment(body, avatar="director", repo=repo)


def post_director_status(
    repo: str,
    issue: int,
    *,
    agent: str = "",
    pr_url: str = "",
    target_repo: str = "",
) -> int:
    """Post status on parent job issue; returns parent issue number."""
    parent = resolve_parent_issue(repo, issue)
    comment = format_director_status_comment(
        repo,
        parent,
        agent=agent,
        pr_url=pr_url,
        target_repo=target_repo,
        trigger_issue=issue if issue != parent else None,
    )
    post_issue_comment(repo, parent, comment)
    return parent


def sync_project_family(repo: str, parent: int) -> None:
    """Sync parent and all architect sub-issues to GitHub Project #6."""
    root = Path(os.environ.get("SQUAD_REPO_ROOT", _repo_root()))
    script = root / "scripts" / "squad_project_sync.py"
    numbers = [parent]
    for role in ARCHITECT_SUBISSUE_ROLES:
        num = _subissue_number(repo, parent, role)
        if num:
            numbers.append(num)
    for num in numbers:
        subprocess.run(
            ["python3", str(script), "--repo", repo, "sync-issue", str(num)],
            cwd=root,
            check=False,
        )
