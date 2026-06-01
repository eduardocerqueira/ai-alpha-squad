"""Build Director dashboard job list (needs you / in progress / stuck / completed)."""

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from ai_alpha_squad.hf_dispatch import parse_parent_issue_number
from ai_alpha_squad.job_pipeline import SquadIssueIndex, analyze_job
from ai_alpha_squad.nudge import PHASE_MARKERS, issue_has_deliverable
from ai_alpha_squad.project_sync import (
    AGENT_PENDING_ON_ISSUE,
    PlanningDeliverables,
    derive_state,
)

DEFAULT_REPO = "eduardocerqueira/ai-alpha-squad"


class GhCliError(RuntimeError):
    """``gh`` CLI failed (auth, rate limit, network)."""

    def __init__(self, args: list[str], returncode: int, message: str) -> None:
        self.args_list = args
        self.returncode = returncode
        self.message = message.strip()
        super().__init__(self.message or f"gh exited {returncode}")


def _short_gh_error(err: GhCliError) -> str:
    msg = err.message
    if "rate limit" in msg.lower():
        return "GitHub API rate limit — wait a few minutes or use cached data below"
    if "auth" in msg.lower() or "401" in msg or "403" in msg:
        return "GitHub auth failed — run: gh auth login"
    return msg.splitlines()[0][:200] if msg else f"gh failed (exit {err.returncode})"
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
    headline: str
    director_action: str
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
        def simple(c: JobCard) -> dict[str, Any]:
            return {
                "number": c.number,
                "title": c.title,
                "url": c.url,
                "headline": c.headline,
                "action": c.director_action,
            }

        attention_cards = tuple(self.stuck) + tuple(self.in_progress)

        return {
            "generated_at": self.generated_at,
            "repo": self.repo,
            "your_move": [simple(c) for c in self.needs_you],
            "attention": [simple(c) for c in attention_cards],
            "counts": {
                "your_move": len(self.needs_you),
                "attention": len(attention_cards),
            },
        }


def _gh_json(args: list[str]) -> Any:
    proc = subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise GhCliError(
            args,
            proc.returncode,
            (proc.stderr or proc.stdout or "").strip(),
        )
    return json.loads(proc.stdout)


def load_cached_dashboard(cache_path: Path) -> dict[str, Any]:
    """Load last written ``jobs.json`` snapshot."""
    data = json.loads(cache_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"invalid dashboard cache: {cache_path}")
    return data


_LIVE_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_LIVE_CACHE_LOCK = Lock()
_DEFAULT_TTL_SEC = 300


def _dashboard_ttl_sec() -> int:
    raw = os.environ.get("SQUAD_DASHBOARD_TTL_SEC", str(_DEFAULT_TTL_SEC))
    try:
        return max(30, int(raw))
    except ValueError:
        return _DEFAULT_TTL_SEC


def fetch_dashboard_json(
    repo: str = DEFAULT_REPO,
    *,
    cache_path: Path | None = None,
    include_closed: int = 15,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Build live dashboard from GitHub; fall back to cache when ``gh`` fails."""
    ttl = _dashboard_ttl_sec()
    if not force_refresh:
        with _LIVE_CACHE_LOCK:
            hit = _LIVE_CACHE.get(repo)
            if hit and (time.time() - hit[0]) < ttl:
                data = dict(hit[1])
                data["cache_ttl_sec"] = ttl
                return data

    try:
        data = build_dashboard(repo, include_closed=include_closed).to_json()
        data["cache_ttl_sec"] = ttl
        with _LIVE_CACHE_LOCK:
            _LIVE_CACHE[repo] = (time.time(), data)
        if cache_path is not None:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return data
    except GhCliError as err:
        with _LIVE_CACHE_LOCK:
            hit = _LIVE_CACHE.get(repo)
            if hit:
                data = dict(hit[1])
                data["stale"] = True
                data["fetch_error"] = _short_gh_error(err)
                return data
        if cache_path is None or not cache_path.is_file():
            raise
        data = load_cached_dashboard(cache_path)
        data["stale"] = True
        data["fetch_error"] = _short_gh_error(err)
        return data


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
    # Closed/released jobs are done — do not surface pipeline noise on the Director view.
    if state.upper() == "CLOSED" or lifecycle == "released":
        return "completed"
    if stuck_reasons:
        return "stuck"
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


def _headline_for_card(
    bucket: str,
    lifecycle: str | None,
    stuck_reasons: tuple[str, ...],
    pr_merged: bool,
) -> str:
    lc = lifecycle or ""
    if bucket == "needs_you":
        if lc == "awaiting-approval":
            return "Approve the Business Analysis."
        if lc == "release-candidate":
            return "Approve or reject the release."
        return "Your approval is required."
    if bucket == "stuck":
        if stuck_reasons:
            text = stuck_reasons[0]
            if "validation" in text.lower():
                return "Validation stalled — squad may need a nudge."
            if "PR merged" in text:
                return "PR merged but the pipeline did not advance."
            return text if len(text) <= 100 else text[:97] + "…"
        return "This job is blocked."
    if bucket == "in_progress":
        if pr_merged and lc == "implemented":
            return "PR merged; validation in progress."
        if lc == "validation":
            return "Release checks running — wait unless you are asked to approve."
        if lc == "designed":
            return "Developer is building — nothing needed from you."
        return "Squad is working — nothing needed from you."
    return "This job is done."


def _director_action_for_card(bucket: str, lifecycle: str | None) -> str:
    if bucket != "needs_you":
        return ""
    lc = lifecycle or ""
    if lc == "awaiting-approval":
        return "Open the issue and reply APPROVE (or REQUEST CHANGES)."
    if lc == "release-candidate":
        return "Open the issue and reply APPROVE or REJECT."
    return "Open the issue and follow the Director gate instructions."


def _load_job_card(
    repo: str,
    row: dict,
    *,
    index: SquadIssueIndex,
) -> JobCard | None:
    title = str(row.get("title") or "")
    body = str(row.get("body") or "")
    if not _is_parent_job(title, body):
        return None

    number = int(row["number"])
    labels = tuple(item["name"] for item in row.get("labels") or [])
    label_set = set(labels)
    state = str(row.get("state") or "OPEN")
    updated_at = str(row.get("updatedAt") or "")

    comments: list[dict] = list(row.get("comments") or index.issue_comments(number))

    health = analyze_job(
        repo,
        number,
        labels=label_set,
        comments=comments,
        body=body,
        index=index,
    )
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
        headline=_headline_for_card(
            bucket,
            derived_lifecycle,
            health.stuck_reasons,
            health.target_pr_merged,
        ),
        director_action=_director_action_for_card(bucket, derived_lifecycle),
        labels=labels,
        stuck_reasons=health.stuck_reasons,
        suggested_action=health.suggested_action,
        agents=(),
    )


def _extract_target_repo(body: str) -> str | None:
    import re

    for match in re.finditer(r"`([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)`", body or ""):
        repo = match.group(1)
        if "ai-alpha-squad" not in repo.lower():
            return repo
    return None


def build_dashboard(repo: str = DEFAULT_REPO, *, include_closed: int = 0) -> DirectorDashboard:
    """List open parent jobs; only approvals surface on the Director view."""
    index = SquadIssueIndex.from_repo(repo, include_closed=include_closed)
    rows = list(index.by_number.values())

    buckets: dict[str, list[JobCard]] = {
        "needs_you": [],
        "in_progress": [],
        "stuck": [],
        "completed": [],
    }
    for row in rows:
        if str(row.get("state") or "OPEN").upper() == "CLOSED":
            continue
        card = _load_job_card(repo, row, index=index)
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
