"""Build Director dashboard job list (needs you / in progress / stuck / completed)."""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from ai_alpha_squad.hf_dispatch import parse_parent_issue_number
from ai_alpha_squad.job_pipeline import analyze_job
from ai_alpha_squad.nudge import PHASE_MARKERS, issue_has_deliverable
from ai_alpha_squad.project_sync import (
    AGENT_PENDING_ON_ISSUE,
    PlanningDeliverables,
    derive_state,
)

DEFAULT_REPO = "eduardocerqueira/ai-alpha-squad"
SUBISSUE_TITLE_PREFIXES = (
    "[Developer]",
    "[QA]",
    "[Security]",
    "[DevOps]",
    "[Tech Writer]",
    "Architect:",
)


@dataclass(frozen=True)
class JobCard:
    number: int
    title: str
    url: str
    lifecycle: str | None
    active_agent: str
    bucket: str
    updated_at: str
    target_repo: str | None
    target_pr_url: str | None
    target_pr_merged: bool
    summary: str
    labels: tuple[str, ...]
    stuck_reasons: tuple[str, ...]
    suggested_action: str
    agents: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class DirectorDashboard:
    generated_at: str
    repo: str
    needs_you: tuple[JobCard, ...]
    in_progress: tuple[JobCard, ...]
    stuck: tuple[JobCard, ...]
    completed: tuple[JobCard, ...]

    def to_json(self) -> dict[str, Any]:
        def rows(cards: tuple[JobCard, ...]) -> list[dict[str, Any]]:
            return [asdict(c) for c in cards]

        return {
            "generated_at": self.generated_at,
            "repo": self.repo,
            "counts": {
                "needs_you": len(self.needs_you),
                "in_progress": len(self.in_progress),
                "stuck": len(self.stuck),
                "completed": len(self.completed),
            },
            "needs_you": rows(self.needs_you),
            "in_progress": rows(self.in_progress),
            "stuck": rows(self.stuck),
            "completed": rows(self.completed),
        }


def _gh_json(args: list[str]) -> Any:
    proc = subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout)


def _is_parent_job(title: str, body: str) -> bool:
    if parse_parent_issue_number(body or ""):
        return False
    title = (title or "").strip()
    return not any(title.startswith(prefix) for prefix in SUBISSUE_TITLE_PREFIXES)


def _planning_from_comments(comments: list[dict]) -> PlanningDeliverables:
    return PlanningDeliverables(
        has_business_analysis=issue_has_deliverable(comments, PHASE_MARKERS["business-owner"]),
        has_technical_spec=issue_has_deliverable(comments, PHASE_MARKERS["architect"]),
    )


def _classify_bucket(
    *,
    state: str,
    lifecycle: str | None,
    active_agent: str,
    needs_director: str,
    planning: PlanningDeliverables,
    stuck_reasons: tuple[str, ...],
) -> str:
    if stuck_reasons:
        return "stuck"
    if state.upper() == "CLOSED" or lifecycle == "released":
        return "completed"
    if lifecycle == "blocked" or active_agent in (AGENT_PENDING_ON_ISSUE, "Blocked"):
        return "stuck"
    if needs_director == "Yes" or lifecycle in ("awaiting-approval", "release-candidate"):
        return "needs_you"
    if lifecycle == "new" and not planning.has_business_analysis:
        return "stuck"
    if lifecycle == "director-approved" and not planning.has_technical_spec:
        return "stuck"
    return "in_progress"


def _summary_for_card(
    bucket: str,
    lifecycle: str | None,
    stuck_reasons: tuple[str, ...],
    pr_merged: bool,
    suggested_action: str,
) -> str:
    if stuck_reasons:
        return stuck_reasons[0]
    if bucket == "needs_you":
        return "Director approval required"
    if pr_merged and lifecycle == "implemented":
        return "PR merged — validation agents should be running"
    if bucket == "completed":
        return "Job finished"
    return f"Phase `{lifecycle or '—'}`"


def _load_job_card(repo: str, row: dict) -> JobCard | None:
    title = str(row.get("title") or "")
    body = str(row.get("body") or "")
    if not _is_parent_job(title, body):
        return None

    number = int(row["number"])
    labels = tuple(item["name"] for item in row.get("labels") or [])
    label_set = set(labels)
    state = str(row.get("state") or "OPEN")
    updated_at = str(row.get("updatedAt") or "")

    comments: list[dict] = []
    try:
        detail = _gh_json(
            [
                "issue",
                "view",
                str(number),
                "--repo",
                repo,
                "--json",
                "comments",
            ]
        )
        comments = detail.get("comments") or []
    except subprocess.CalledProcessError:
        pass

    health = analyze_job(repo, number, labels=label_set, comments=comments, body=body)
    lifecycle = health.effective_lifecycle
    planning = _planning_from_comments(comments)
    derived = derive_state(label_set, planning=planning)
    if lifecycle:
        derived_lifecycle = lifecycle
    else:
        derived_lifecycle = derived.lifecycle

    bucket = _classify_bucket(
        state=state,
        lifecycle=derived_lifecycle,
        active_agent=derived.active_agent,
        needs_director=derived.needs_director,
        planning=planning,
        stuck_reasons=health.stuck_reasons,
    )

    agent_rows = tuple(
        {
            "role": a.role,
            "status": a.status,
            "issue_number": a.issue_number,
            "issue_url": a.issue_url,
            "detail": a.detail,
        }
        for a in health.agents
    )

    return JobCard(
        number=number,
        title=title,
        url=f"https://github.com/{repo}/issues/{number}",
        lifecycle=derived_lifecycle,
        active_agent=derived.active_agent,
        bucket=bucket,
        updated_at=updated_at,
        target_repo=_extract_target_repo(body),
        target_pr_url=health.target_pr_url,
        target_pr_merged=health.target_pr_merged,
        summary=_summary_for_card(
            bucket,
            derived_lifecycle,
            health.stuck_reasons,
            health.target_pr_merged,
            health.suggested_action,
        ),
        labels=labels,
        stuck_reasons=health.stuck_reasons,
        suggested_action=health.suggested_action,
        agents=agent_rows,
    )


def _extract_target_repo(body: str) -> str | None:
    import re

    for match in re.finditer(r"`([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)`", body or ""):
        repo = match.group(1)
        if "ai-alpha-squad" not in repo.lower():
            return repo
    return None


def build_dashboard(repo: str = DEFAULT_REPO, *, include_closed: int = 15) -> DirectorDashboard:
    """List parent jobs and classify into Director buckets."""
    open_rows = _gh_json(
        [
            "issue",
            "list",
            "--repo",
            repo,
            "--state",
            "open",
            "--json",
            "number,title,body,state,labels,updatedAt",
            "--limit",
            "100",
        ]
    )
    closed_rows: list[dict] = []
    if include_closed > 0:
        closed_rows = _gh_json(
            [
                "issue",
                "list",
                "--repo",
                repo,
                "--state",
                "closed",
                "--json",
                "number,title,body,state,labels,updatedAt",
                "--limit",
                str(include_closed),
            ]
        )

    buckets: dict[str, list[JobCard]] = {
        "needs_you": [],
        "in_progress": [],
        "stuck": [],
        "completed": [],
    }
    for row in list(open_rows) + list(closed_rows):
        card = _load_job_card(repo, row)
        if card is None:
            continue
        buckets[card.bucket].append(card)

    for key in buckets:
        buckets[key].sort(key=lambda c: c.updated_at, reverse=True)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return DirectorDashboard(
        generated_at=now,
        repo=repo,
        needs_you=tuple(buckets["needs_you"]),
        in_progress=tuple(buckets["in_progress"]),
        stuck=tuple(buckets["stuck"]),
        completed=tuple(buckets["completed"]),
    )
