"""Pipeline health: per-agent status and stuck detection for Director dashboard."""

from __future__ import annotations

import json
import os
import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ai_alpha_squad.hf_dispatch import parse_parent_issue_number
from ai_alpha_squad.nudge import ARCHITECT_SUBISSUE_ROLES, PHASE_MARKERS, issue_has_deliverable
from ai_alpha_squad.project_sync import LIFECYCLE_LABELS, current_lifecycle
from ai_alpha_squad.agent_models import (
    ACTIONS_DISPATCH_MARKER,
    ACTIONS_RESULT_MARKER,
    HF_DISPATCH_MARKER,
    HF_RESULT_MARKER,
)
from ai_alpha_squad.validation_dispatch import (
    VALIDATION_ROLES,
    parent_has_validation_dispatch,
    role_dispatch_marker,
)

PR_URL_RE = re.compile(
    r"https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/pull/(\d+)",
)

PLANNING_ROLES = ("business-owner", "architect")
CODING_ROLES = ("developer",)
ALL_TRACKED_ROLES = ("business-owner", "architect", *ARCHITECT_SUBISSUE_ROLES, "release-manager")
SUBISSUE_ROLES = ("developer", *VALIDATION_ROLES)


@dataclass
class SquadIssueIndex:
    """In-memory index from a few ``gh issue list`` calls (avoids per-role/per-issue API spam)."""

    by_number: dict[int, dict[str, Any]]
    subs_by_parent: dict[int, dict[str, int]]
    pr_merged_cache: dict[str, bool] = field(default_factory=dict)

    @classmethod
    def from_repo(cls, repo: str, *, include_closed: int = 15) -> SquadIssueIndex:
        rows: list[dict[str, Any]] = list(
            _gh_json(
                [
                    "issue",
                    "list",
                    "--repo",
                    repo,
                    "--state",
                    "open",
                    "--json",
                    "number,title,body,state,labels,updatedAt,comments",
                    "--limit",
                    "100",
                ]
            )
        )
        if include_closed > 0:
            rows.extend(
                _gh_json(
                    [
                        "issue",
                        "list",
                        "--repo",
                        repo,
                        "--state",
                        "closed",
                        "--json",
                        "number,title,body,state,labels,updatedAt,comments",
                        "--limit",
                        str(include_closed),
                    ]
                )
            )
        by_number: dict[int, dict[str, Any]] = {}
        subs: dict[int, dict[str, int]] = defaultdict(dict)
        for row in rows:
            num = int(row["number"])
            by_number[num] = row
            body = str(row.get("body") or "")
            parent = parse_parent_issue_number(body)
            if not parent:
                continue
            label_names = {item["name"] for item in row.get("labels") or []}
            for role in SUBISSUE_ROLES:
                if role in label_names:
                    subs[parent][role] = num
        return cls(by_number=by_number, subs_by_parent=dict(subs))

    def subissue_number(self, parent: int, role: str) -> int | None:
        return self.subs_by_parent.get(parent, {}).get(role)

    def issue_comments(self, issue_number: int | None) -> list[dict]:
        if issue_number is None:
            return []
        row = self.by_number.get(issue_number) or {}
        return list(row.get("comments") or [])

    def issue_body(self, issue_number: int | None) -> str:
        if issue_number is None:
            return ""
        row = self.by_number.get(issue_number) or {}
        return str(row.get("body") or "")

    def issue_state(self, issue_number: int | None) -> str:
        if issue_number is None:
            return ""
        row = self.by_number.get(issue_number) or {}
        return str(row.get("state") or "")


@dataclass(frozen=True)
class AgentStatus:
    role: str
    status: str  # done | active | waiting | idle | stuck
    issue_number: int | None
    issue_url: str | None
    detail: str


@dataclass(frozen=True)
class PipelineHealth:
    effective_lifecycle: str | None
    target_pr_url: str | None
    target_pr_merged: bool
    stuck_reasons: tuple[str, ...]
    agents: tuple[AgentStatus, ...]
    suggested_action: str


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _gh_json(args: list[str]) -> dict | list:
    proc = subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout)


def _subissue_number(
    repo: str,
    parent: int,
    role: str,
    *,
    index: SquadIssueIndex | None = None,
) -> int | None:
    if index is not None:
        return index.subissue_number(parent, role)
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


def effective_lifecycle_from_labels(labels: set[str]) -> str | None:
    """Strongest lifecycle label when multiple are present (e.g. designed + implemented)."""
    for label in LIFECYCLE_LABELS:
        if label in labels:
            return label
    return None


def _pr_merged(pr_url: str | None, *, index: SquadIssueIndex | None = None) -> bool:
    if not pr_url:
        return False
    if index is not None and pr_url in index.pr_merged_cache:
        return index.pr_merged_cache[pr_url]
    match = PR_URL_RE.match(pr_url.strip())
    if not match:
        return False
    repo, num = match.group(1), match.group(2)
    try:
        data = _gh_json(
            ["pr", "view", num, "--repo", repo, "--json", "state,mergedAt"]
        )
        merged = bool(data.get("mergedAt")) or str(data.get("state", "")).upper() == "MERGED"
    except subprocess.CalledProcessError:
        merged = False
    if index is not None:
        index.pr_merged_cache[pr_url] = merged
    return merged


def _find_dev_pr(
    repo: str,
    parent: int,
    comments: list[dict],
    body: str,
    *,
    index: SquadIssueIndex | None = None,
) -> str | None:
    dev = _subissue_number(repo, parent, "developer", index=index)
    texts = [body or ""]
    if dev:
        if index is not None:
            texts.append(index.issue_body(dev))
            for c in index.issue_comments(dev):
                texts.append(c.get("body") or "")
        else:
            try:
                sub = _gh_json(
                    [
                        "issue",
                        "view",
                        str(dev),
                        "--repo",
                        repo,
                        "--json",
                        "body,comments",
                    ]
                )
                texts.append(sub.get("body") or "")
                for c in sub.get("comments") or []:
                    texts.append(c.get("body") or "")
            except subprocess.CalledProcessError:
                pass
    for c in comments:
        texts.append(c.get("body") or "")
    for text in reversed(texts):
        for match in PR_URL_RE.finditer(str(text)):
            pr_repo = match.group(1)
            if "ai-alpha-squad" not in pr_repo.lower():
                return match.group(0)
    return None


def _comment_bodies(comments: list[dict]) -> str:
    return "\n".join(str(c.get("body") or "") for c in comments)


def _sub_issue_dispatch_stale(sub_comments: list[dict], role: str) -> bool:
    """True when dispatch was recorded on sub-issue but no agent result/deliverable yet."""
    blob = _comment_bodies(sub_comments).lower()
    if role_dispatch_marker(role).lower() not in blob:
        if ACTIONS_DISPATCH_MARKER.lower() not in blob and HF_DISPATCH_MARKER.lower() not in blob:
            return False
    if ACTIONS_RESULT_MARKER.lower() in blob or HF_RESULT_MARKER.lower() in blob:
        return False
    return True


def _validation_marker(role: str) -> str:
    markers = {
        "qa": "# qa report",
        "security": "# security report",
        "devops": "# deployment checklist",
        "tech-writer": "# release notes",
    }
    return markers.get(role, "")


def build_agent_roster(
    repo: str,
    parent: int,
    *,
    labels: set[str],
    comments: list[dict],
    lifecycle: str | None,
    pr_url: str | None,
    pr_merged: bool,
    index: SquadIssueIndex | None = None,
) -> tuple[AgentStatus, ...]:
    roster: list[AgentStatus] = []
    lc = lifecycle or ""

    has_ba = issue_has_deliverable(comments, PHASE_MARKERS["business-owner"])
    has_spec = issue_has_deliverable(comments, PHASE_MARKERS["architect"])

    # Business Owner
    if has_ba or lc not in ("", "new"):
        bo_status = "done" if has_ba else "stuck"
        roster.append(
            AgentStatus(
                "business-owner",
                bo_status,
                parent,
                f"https://github.com/{repo}/issues/{parent}",
                "BA on parent issue" if has_ba else "Missing # Business Analysis",
            )
        )
    else:
        roster.append(
            AgentStatus(
                "business-owner",
                "active" if lc == "new" else "waiting",
                parent,
                f"https://github.com/{repo}/issues/{parent}",
                "Writing Business Analysis",
            )
        )

    # Architect
    has_dev_sub = _subissue_number(repo, parent, "developer", index=index) is not None
    if has_spec and has_dev_sub:
        roster.append(
            AgentStatus(
                "architect",
                "done",
                parent,
                f"https://github.com/{repo}/issues/{parent}",
                "Tech spec + sub-issues created",
            )
        )
    elif lc in ("director-approved", "new") and not has_spec:
        roster.append(
            AgentStatus(
                "architect",
                "active" if lc == "director-approved" else "waiting",
                parent,
                f"https://github.com/{repo}/issues/{parent}",
                "Tech spec in progress" if lc == "director-approved" else "Waiting for director-approved",
            )
        )
    elif has_spec:
        roster.append(
            AgentStatus(
                "architect",
                "stuck",
                parent,
                f"https://github.com/{repo}/issues/{parent}",
                "Tech spec done but sub-issues missing",
            )
        )
    else:
        roster.append(
            AgentStatus(
                "architect",
                "done" if lc not in ("", "new", "awaiting-approval", "director-approved") else "waiting",
                parent,
                f"https://github.com/{repo}/issues/{parent}",
                "Complete" if lc not in ("", "new", "awaiting-approval", "director-approved") else "Not started",
            )
        )

    # Developer
    dev_num = _subissue_number(repo, parent, "developer", index=index)
    dev_url = f"https://github.com/{repo}/issues/{dev_num}" if dev_num else None
    if pr_merged:
        roster.append(
            AgentStatus(
                "developer",
                "done",
                dev_num,
                dev_url,
                f"PR merged{f' — {pr_url}' if pr_url else ''}",
            )
        )
    elif pr_url and not pr_merged:
        roster.append(
            AgentStatus(
                "developer",
                "active",
                dev_num,
                dev_url,
                f"PR open — merge when ready: {pr_url}",
            )
        )
    elif lc in ("designed", "implemented", "validation"):
        roster.append(
            AgentStatus(
                "developer",
                "stuck" if lc != "designed" else "active",
                dev_num,
                dev_url,
                "No target PR found on developer sub-issue"
                if not pr_url
                else "Implementation phase",
            )
        )
    else:
        roster.append(
            AgentStatus(
                "developer",
                "waiting",
                dev_num,
                dev_url,
                "Starts at designed phase",
            )
        )

    # Validation roles
    validation_started = parent_has_validation_dispatch(comments)
    for role in VALIDATION_ROLES:
        num = _subissue_number(repo, parent, role, index=index)
        url = f"https://github.com/{repo}/issues/{num}" if num else None
        role_marker_on_parent = parent_has_validation_dispatch(comments, role=role)
        if num:
            try:
                if index is not None:
                    sub_comments = index.issue_comments(num)
                    sub_state = index.issue_state(num)
                else:
                    sub = _gh_json(
                        [
                            "issue",
                            "view",
                            str(num),
                            "--repo",
                            repo,
                            "--json",
                            "state,comments",
                        ]
                    )
                    sub_comments = sub.get("comments") or []
                    sub_state = str(sub.get("state") or "")
                has_report = issue_has_deliverable(
                    sub_comments, _validation_marker(role)
                )
                if has_report or str(sub_state).upper() == "CLOSED":
                    roster.append(
                        AgentStatus(role, "done", num, url, "Deliverable posted")
                    )
                    continue
                if _sub_issue_dispatch_stale(sub_comments, role):
                    roster.append(
                        AgentStatus(
                            role,
                            "stuck",
                            num,
                            url,
                            "Dispatch logged but no report — re-run validation dispatch",
                        )
                    )
                    continue
            except subprocess.CalledProcessError:
                pass

        if lc in ("release-candidate", "released"):
            # Validation has cleared (the job reached the release gate). v2 may
            # not create per-role sub-issues, so reflect completion rather than
            # leaving validation agents stuck on "waiting".
            roster.append(AgentStatus(role, "done", num, url, "Validated"))
        elif lc not in ("implemented", "validation") and not validation_started:
            roster.append(
                AgentStatus(role, "waiting", num, url, "After developer PR merges")
            )
        elif not role_marker_on_parent and not num:
            roster.append(
                AgentStatus(
                    role,
                    "stuck",
                    num,
                    url,
                    "Sub-issue missing",
                )
            )
        elif not role_marker_on_parent:
            roster.append(
                AgentStatus(
                    role,
                    "stuck",
                    num,
                    url,
                    "Not dispatched — run phase tick",
                )
            )
        else:
            roster.append(
                AgentStatus(role, "active", num, url, "Dispatched — awaiting report")
            )

    # Release manager
    if lc in ("validation", "release-candidate", "released"):
        rm_status = "active" if lc == "validation" else ("waiting" if lc == "release-candidate" else "done")
        roster.append(
            AgentStatus(
                "release-manager",
                rm_status,
                parent,
                f"https://github.com/{repo}/issues/{parent}",
                f"Phase `{lc}`",
            )
        )
    else:
        roster.append(
            AgentStatus(
                "release-manager",
                "waiting",
                None,
                None,
                "After validation completes",
            )
        )

    return tuple(roster)


def detect_stuck_reasons(
    *,
    labels: set[str],
    lifecycle: str | None,
    comments: list[dict],
    pr_url: str | None,
    pr_merged: bool,
    agents: tuple[AgentStatus, ...],
) -> tuple[str, ...]:
    reasons: list[str] = []
    lc = lifecycle or ""

    if "designed" in labels and "implemented" in labels:
        reasons.append("Conflicting labels: both `designed` and `implemented` on parent")

    if pr_merged and lc == "designed":
        reasons.append("Target PR is merged but parent is still `designed` (should be `implemented`)")

    if pr_merged and lc == "implemented":
        stuck_validation = [a.role for a in agents if a.role in VALIDATION_ROLES and a.status == "stuck"]
        if stuck_validation:
            reasons.append(
                f"PR merged and `implemented`, but validation not started: {', '.join(stuck_validation)}"
            )

    stale_validation = [
        a.role
        for a in agents
        if a.role in VALIDATION_ROLES and "Dispatch logged but no report" in a.detail
    ]
    if stale_validation:
        reasons.append(
            f"Validation agents stalled after dispatch: {', '.join(stale_validation)} "
            "(re-run with SQUAD_FORCE_NUDGE=1)"
        )
    elif lc == "implemented" and not parent_has_validation_dispatch(comments):
        reasons.append(
            "Parent has `implemented` but validation agents were never dispatched"
        )

    if lc == "designed" and pr_merged:
        reasons.append(
            "Developer PR merged — run `./scripts/squad-phase-tick.sh <repo> <parent>` to advance"
        )

    stuck_agents = [a for a in agents if a.status == "stuck"]
    for a in stuck_agents:
        if a.role in VALIDATION_ROLES and f"validation not started" not in " ".join(reasons):
            reasons.append(f"{a.role}: {a.detail}")

    return tuple(dict.fromkeys(reasons))


def analyze_job(
    repo: str,
    parent: int,
    *,
    labels: set[str],
    comments: list[dict],
    body: str,
    index: SquadIssueIndex | None = None,
) -> PipelineHealth:
    lifecycle = effective_lifecycle_from_labels(labels)
    pr_url = _find_dev_pr(repo, parent, comments, body, index=index)
    pr_merged = _pr_merged(pr_url, index=index)
    agents = build_agent_roster(
        repo,
        parent,
        labels=labels,
        comments=comments,
        lifecycle=lifecycle,
        pr_url=pr_url,
        pr_merged=pr_merged,
        index=index,
    )
    stuck_reasons = detect_stuck_reasons(
        labels=labels,
        lifecycle=lifecycle,
        comments=comments,
        pr_url=pr_url,
        pr_merged=pr_merged,
        agents=agents,
    )
    if stuck_reasons:
        action = f"Unblock: `./scripts/squad-phase-tick.sh {repo} {parent}`"
    elif pr_merged and lifecycle == "implemented":
        action = "Validation should be running — refresh dashboard in 1–2 min after tick"
    else:
        action = ""

    return PipelineHealth(
        effective_lifecycle=lifecycle,
        target_pr_url=pr_url,
        target_pr_merged=pr_merged,
        stuck_reasons=stuck_reasons,
        agents=agents,
        suggested_action=action,
    )
