"""Build Director dashboard job list (needs you / in progress / stuck / completed)."""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from ai_alpha_squad.hf_dispatch import parse_parent_issue_number
from ai_alpha_squad.job_pipeline import SquadIssueIndex, analyze_job
from ai_alpha_squad.nudge import PHASE_MARKERS, issue_has_deliverable
from ai_alpha_squad.project_sync import (
    AGENT_PENDING_ON_ISSUE,
    LIFECYCLE_LABELS,
    PHASE_TO_AGENT,
    PlanningDeliverables,
    derive_state,
)
from ai_alpha_squad import squad_v2

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
    blocked: bool
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
    events: tuple[dict[str, Any], ...]


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
            return "Accept or reject the developer + QA delivery."
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
        return (
            "Accept delivery to complete the job, or Reject to send "
            "developer and QA for another round."
        )
    return "Open the issue and follow the Director gate instructions."


# Chronological phases shown on the Director timeline (forward order):
# (lifecycle label, human title, owning role).
TIMELINE_PHASES: tuple[tuple[str, str, str], ...] = (
    ("new", "Request triaged", "business-owner"),
    ("awaiting-approval", "Business analysis ready", "Director"),
    ("director-approved", "Approved — architecture & planning", "architect"),
    ("designed", "Technical spec ready — development", "developer"),
    ("implemented", "Code complete — pull request", "developer"),
    ("validation", "Validation (QA, Security, DevOps, Docs)", "release-manager"),
    ("release-candidate", "Release candidate", "Director"),
    ("released", "Released", "Done"),
)

DIRECTOR_GATES = frozenset({"awaiting-approval", "release-candidate"})


def _progress_phase(lifecycle: str | None, labels: tuple[str, ...]) -> str | None:
    """Resolve the phase a job actually reached on the timeline.

    ``lifecycle`` may collapse to ``blocked`` (an overlay, not a phase). When it
    is not itself a timeline phase, fall back to the most-advanced lifecycle
    label present on the issue (``LIFECYCLE_LABELS`` is ordered most-advanced
    first), skipping the ``blocked`` overlay.
    """
    phases = {p[0] for p in TIMELINE_PHASES}
    if lifecycle in phases:
        return lifecycle
    label_set = set(labels)
    for label in LIFECYCLE_LABELS:
        if label == "blocked":
            continue
        if label in label_set and label in phases:
            return label
    return None


def _effective_phase(
    lifecycle: str | None,
    labels: tuple[str, ...],
    *,
    has_spec: bool,
    pr_url: str | None,
    pr_merged: bool,
) -> str | None:
    """Phase the job has *actually* reached, advancing past lagging labels using
    artifacts. A label can fall behind (or get stuck on ``blocked``) while the
    squad has already produced a spec or opened a PR — trust the artifacts."""
    order = [p[0] for p in TIMELINE_PHASES]
    phase = _progress_phase(lifecycle, labels)
    idx = order.index(phase) if phase in order else -1

    def at_least(label: str) -> None:
        nonlocal idx
        idx = max(idx, order.index(label))

    if has_spec:
        at_least("designed")
    if pr_url and not pr_merged:
        at_least("implemented")
    if pr_merged:
        at_least("validation")  # code merged → past implementation
    return order[idx] if idx >= 0 else phase


def _build_events(
    *,
    lifecycle: str | None,
    labels: tuple[str, ...],
    bucket: str,
    director_action: str,
    issue_url: str,
    target_pr_url: str | None,
    target_pr_merged: bool,
    stuck_reasons: tuple[str, ...],
) -> tuple[dict[str, Any], ...]:
    """Chronological lifecycle timeline for one job (timeline19 view).

    Step status is one of ``done | current | director | blocked | pending``.
    The current Director gate carries an ``action`` (message + link) so the UI
    can surface "request for Director" inline on the timeline.
    """
    order = [p[0] for p in TIMELINE_PHASES]
    current = _progress_phase(lifecycle, labels)
    cur_idx = order.index(current) if current else -1

    events: list[dict[str, Any]] = []
    for idx, (label, title, owner) in enumerate(TIMELINE_PHASES):
        if cur_idx < 0:
            status = "pending"
        elif idx < cur_idx:
            status = "done"
        elif idx == cur_idx:
            if bucket == "completed":
                status = "done"
            elif label in DIRECTOR_GATES and bucket == "needs_you":
                status = "director"
            elif bucket == "stuck":
                status = "blocked"
            else:
                status = "current"
        else:
            status = "pending"

        detail = ""
        action = None
        if status == "director":
            detail = director_action or "Director approval required."
            action = {
                "label": "Open issue & respond",
                "url": issue_url,
                "message": director_action or "Approve or request changes on GitHub.",
            }
        elif status == "blocked" and stuck_reasons:
            detail = stuck_reasons[0]
        elif label == "implemented" and target_pr_url:
            detail = "PR merged" if target_pr_merged else "PR open"

        event: dict[str, Any] = {
            "key": label,
            "title": title,
            "owner": owner,
            "status": status,
            "detail": detail,
        }
        if action:
            event["action"] = action
        if label == "implemented" and target_pr_url:
            event["pr_url"] = target_pr_url
        events.append(event)
    return tuple(events)


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

    # `blocked` is an overlay flag, not a phase: surface it but trust the
    # artifacts (spec, PR) for the real phase the squad has reached.
    blocked = "blocked" in label_set or derived_lifecycle == "blocked"
    effective_lifecycle = _effective_phase(
        derived_lifecycle,
        labels,
        has_spec=planning.has_technical_spec,
        pr_url=health.target_pr_url,
        pr_merged=health.target_pr_merged,
    )
    # Active agent from the real phase (so a stale `blocked` label doesn't read
    # as "Blocked" and wrongly bucket an advancing job as stuck).
    active_agent = (
        PHASE_TO_AGENT.get(effective_lifecycle, derived.active_agent)
        if effective_lifecycle
        else derived.active_agent
    )

    bucket = _classify_bucket(
        state=state,
        lifecycle=effective_lifecycle,
        active_agent=active_agent,
        needs_director=derived.needs_director,
        planning=planning,
        stuck_reasons=health.stuck_reasons,
    )

    director_action = _director_action_for_card(bucket, effective_lifecycle)
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
    events = _build_events(
        lifecycle=effective_lifecycle,
        labels=labels,
        bucket=bucket,
        director_action=director_action,
        issue_url=f"https://github.com/{repo}/issues/{number}",
        target_pr_url=health.target_pr_url,
        target_pr_merged=health.target_pr_merged,
        stuck_reasons=health.stuck_reasons,
    )

    return JobCard(
        number=number,
        title=title,
        url=f"https://github.com/{repo}/issues/{number}",
        lifecycle=effective_lifecycle,
        active_agent=active_agent,
        bucket=bucket,
        blocked=blocked,
        updated_at=updated_at,
        target_repo=_extract_target_repo(body),
        target_pr_url=health.target_pr_url,
        target_pr_merged=health.target_pr_merged,
        summary=_summary_for_card(
            bucket,
            effective_lifecycle,
            health.stuck_reasons,
            health.target_pr_merged,
            health.suggested_action,
        ),
        headline=_headline_for_card(
            bucket,
            effective_lifecycle,
            health.stuck_reasons,
            health.target_pr_merged,
        ),
        director_action=director_action,
        labels=labels,
        stuck_reasons=health.stuck_reasons,
        suggested_action=health.suggested_action,
        agents=agent_rows,
        events=events,
    )


def _extract_target_repo(body: str) -> str | None:
    import re

    for match in re.finditer(r"`([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)`", body or ""):
        repo = match.group(1)
        if "ai-alpha-squad" not in repo.lower():
            return repo
    return None


# ---------------------------------------------------------------------------
# v2 model: Business Owner → Developer → QA, deliverables as parent comments,
# no sub-issues, no designed/implemented/validation phases. See squad_v2.py.
# ---------------------------------------------------------------------------

# (lifecycle/synthetic key, human title, owning actor)
TIMELINE_PHASES_V2: tuple[tuple[str, str, str], ...] = (
    ("new", "Request triaged", "business-owner"),
    ("awaiting-approval", "Business analysis ready", "Director"),
    ("implementation", "Implementation — PR on target repo", "developer"),
    ("qa", "QA review", "qa"),
    ("release-candidate", "Delivery review", "Director"),
    ("released", "Released", "Done"),
)

_V2_DIRECTOR_GATES = frozenset({"awaiting-approval", "release-candidate"})


def _v2_dev_pr(comments: tuple[dict, ...]) -> str | None:
    """Latest non-self PR URL posted on the issue (the developer deliverable)."""
    import re

    found: str | None = None
    for c in comments:
        for m in re.finditer(r"https://github\.com/([\w.-]+/[\w.-]+)/pull/\d+", c.get("body") or ""):
            if "ai-alpha-squad" not in m.group(1).lower():
                found = m.group(0)
    return found


# Squad result comments are rendered as an HTML card; the posting agent is
# identified by its avatar (assets/agents/<role>.svg) and the model is printed
# as "Model: `org/Name`" (a "squad-v2-model:X" marker records a developer
# escalation to a stronger coder). These match the real comment bodies.
_RESULT_ROLE_RE = re.compile(r"/agents/([a-z-]+)\.svg")
_MODEL_RE = re.compile(r"\bmodel:?\**\s*`([^`]+)`", re.IGNORECASE)
_ESCALATION_RE = re.compile(r"squad-v2-model:(\S+)")


def _result_role(body: str) -> str | None:
    m = _RESULT_ROLE_RE.search(body)
    return m.group(1) if m else None


def _v2_agent_model_history(comments: tuple[dict, ...], role: str) -> tuple[dict[str, Any], ...]:
    """Chronological list of every AI model an agent used on this issue.

    Agents announce the model they ran on in their result card ("Model: `X`");
    the developer additionally posts a ``squad-v2-model:X`` marker when a re-run
    escalates to a stronger model. Returns ``[{model, at, kind}]`` ordered
    oldest→newest, with consecutive duplicates of the same model collapsed so
    the history reads as distinct hand-offs/escalations rather than one entry
    per comment.
    """
    raw: list[dict[str, Any]] = []
    for c in comments:
        body = c.get("body") or ""
        at = c.get("createdAt") or c.get("created_at") or ""
        if role == "developer":
            m = _ESCALATION_RE.search(body)
            if m:
                raw.append({"model": m.group(1), "at": at, "kind": "escalation"})
                continue
        low = body.lower()
        if ("squad hf agent result" in low or "squad actions agent result" in low) and _result_role(
            body
        ) == role:
            m = _MODEL_RE.search(body)
            if m:
                raw.append({"model": m.group(1), "at": at, "kind": "result"})

    history: list[dict[str, Any]] = []
    for entry in raw:
        if history and history[-1]["model"] == entry["model"]:
            # Same model still in use — keep the first time we saw it.
            continue
        history.append(entry)
    return tuple(history)


def _v2_agent_model(comments: tuple[dict, ...], role: str) -> str | None:
    """The latest AI model an agent used (back-compat single value)."""
    history = _v2_agent_model_history(comments, role)
    return history[-1]["model"] if history else None


def _developer_last_run_failed(comments: tuple[dict, ...]) -> bool:
    """True when the latest developer run marker is a failure (not reset since)."""
    last: str | None = None
    for comment in comments:
        body = (comment.get("body") or "").lower()
        if f"{squad_v2.RUN_RESET_MARKER}developer" in body or f"{squad_v2.RUN_RESET_MARKER}all" in body:
            last = None
            continue
        if f"{squad_v2.RUN_IN_PROGRESS_MARKER}developer" in body:
            last = "in_progress"
        if f"{squad_v2.RUN_FAILED_MARKER}developer" in body:
            last = "failed"
    return last == "failed"


def _v2_agents(
    repo: str,
    number: int,
    comments: tuple[dict, ...],
    lc: str | None,
    pr_url: str | None,
    *,
    pending_agent: str | None = None,
    active_agent: str | None = None,
) -> tuple[dict[str, Any], ...]:
    parent = f"https://github.com/{repo}/issues/{number}"
    dev_idx = squad_v2._latest_deliverable_index(comments, "developer")
    qa_idx, qa_verdict = squad_v2.latest_qa_verdict(comments)
    active = active_agent or squad_v2.run_in_progress(comments)
    done_phase = lc in ("release-candidate", "released")

    def row(role: str, status: str, detail: str) -> dict[str, Any]:
        return {
            "role": role,
            "status": status,
            "issue_number": number,
            "issue_url": parent,
            "detail": detail,
            "model": _v2_agent_model(comments, role),
            "model_history": _v2_agent_model_history(comments, role),
        }

    # Business Owner
    if squad_v2.has_deliverable(comments, "business-owner"):
        bo = ("done", "Business analysis posted")
    elif lc == "new":
        bo = ("active", "Writing business analysis")
    else:
        bo = ("done", "Complete")

    rounds = squad_v2.qa_fails_since_escalation(comments)

    # Developer
    pr_suffix = f" — {pr_url}" if pr_url else ""
    if done_phase:
        dev = ("done", f"Delivered{pr_suffix}")
    elif (
        dev_idx is not None
        and qa_verdict == "pass"
        and (qa_idx or 0) > dev_idx
        and squad_v2.director_delivery_rejected_after(comments, qa_idx or 0)
    ):
        dev = (
            ("waiting", f"Queued — rework after Director rejection{pr_suffix}")
            if pending_agent == "developer" and active != "developer"
            else ("waiting", f"Director rejected delivery — awaiting rework{pr_suffix}")
        )
    elif dev_idx is not None and qa_verdict == "fail" and (qa_idx or 0) > dev_idx:
        dev = (
            ("waiting", f"Queued — rework after QA (round {rounds}){pr_suffix}")
            if pending_agent == "developer" and active != "developer"
            else ("waiting", f"QA requested changes — awaiting developer{pr_suffix}")
        )
    elif dev_idx is not None:
        dev = ("done", f"Deliverable posted{pr_suffix}")
    elif lc == "director-approved":
        dev = (
            ("waiting", "Queued — implementing on the target repo")
            if pending_agent == "developer" and active != "developer"
            else ("waiting", "Awaiting developer implementation")
        )
    else:
        dev = ("waiting", "After Director approves the analysis")

    if active != "developer" and _developer_last_run_failed(comments) and not done_phase:
        dev = ("blocked", f"Last run failed — waiting for retry{pr_suffix}")

    # QA (acceptance gate)
    if done_phase:
        qa = ("done", "Passed")
    elif (
        dev_idx is not None
        and qa_verdict == "pass"
        and (qa_idx or 0) > dev_idx
        and squad_v2.director_delivery_rejected_after(comments, qa_idx or 0)
    ):
        qa = ("waiting", "Awaiting re-review after developer rework")
    elif dev_idx is not None and qa_verdict == "pass" and (qa_idx or 0) > dev_idx:
        qa = ("done", "Passed")
    elif dev_idx is not None and qa_verdict == "fail" and (qa_idx or 0) > dev_idx:
        state = "blocked" if rounds >= squad_v2.MAX_QA_ROUNDS else "done"
        qa = (state, f"Requested changes (round {rounds}/{squad_v2.MAX_QA_ROUNDS})")
    elif dev_idx is not None:
        qa = (
            ("waiting", "Queued — QA review of deliverable")
            if pending_agent == "qa" and active != "qa"
            else ("waiting", "Awaiting QA review")
        )
    else:
        qa = ("waiting", "After the developer delivers")

    rows = [
        row("business-owner", bo[0], bo[1]),
        row("developer", dev[0], dev[1]),
        row("qa", qa[0], qa[1]),
    ]
    # A live run marker means this agent is executing now — surface "running".
    if active:
        for r in rows:
            if r["role"] == active:
                r["status"] = "running"
                r["detail"] = f"Running now — {r['detail']}"
    return tuple(rows)


def _comment_at(comments: tuple[dict, ...], idx: int | None) -> str:
    """ISO timestamp of comments[idx] ("" if out of range/unknown)."""
    if idx is None or not (0 <= idx < len(comments)):
        return ""
    c = comments[idx]
    return c.get("createdAt") or c.get("created_at") or ""


def _first_marker_at(comments: tuple[dict, ...], needle: str) -> str:
    """ISO timestamp of the first comment containing ``needle`` ("" if none)."""
    for c in comments:
        if needle in (c.get("body") or "").lower():
            return c.get("createdAt") or c.get("created_at") or ""
    return ""


def _released_at(comments: tuple[dict, ...]) -> str:
    """ISO timestamp of the latest 'Released — …' comment ("" if none)."""
    at = ""
    for c in comments:
        if (c.get("body") or "").lstrip().lower().startswith("released"):
            at = c.get("createdAt") or c.get("created_at") or ""
    return at


def _v2_events(
    *,
    lc: str | None,
    bucket: str,
    comments: tuple[dict, ...],
    director_action: str,
    issue_url: str,
    pr_url: str | None,
) -> tuple[dict[str, Any], ...]:
    dev_idx = squad_v2._latest_deliverable_index(comments, "developer")
    qa_idx, qa_verdict = squad_v2.latest_qa_verdict(comments)
    rounds = squad_v2.qa_fails_since_escalation(comments)
    # Best-available timestamp per phase, from the comment that marks it.
    bo_idx = squad_v2._latest_deliverable_index(comments, "business-owner")
    ba_at = _comment_at(comments, bo_idx)
    phase_at = {
        "new": _first_marker_at(comments, "squad-v2-run:in_progress:business-owner") or ba_at,
        "awaiting-approval": ba_at,
        "implementation": _comment_at(comments, dev_idx),
        "qa": _comment_at(comments, qa_idx),
        "released": _released_at(comments),
    }
    order = ["new", "awaiting-approval", "director-approved", "release-candidate", "released"]
    cur = order.index(lc) if lc in order else -1

    def at_or_past(label: str) -> bool:
        return cur >= order.index(label)

    events: list[dict[str, Any]] = []
    for key, title, owner in TIMELINE_PHASES_V2:
        status = "pending"
        detail = ""
        action = None
        if key == "new":
            status = "done" if (cur > 0 or squad_v2.has_deliverable(comments, "business-owner")) else (
                "current" if lc == "new" else "pending"
            )
        elif key == "awaiting-approval":
            if at_or_past("director-approved"):
                status = "done"
            elif lc == "awaiting-approval":
                status = "director"
            else:
                status = "pending"
        elif key == "implementation":
            if at_or_past("release-candidate"):
                status = "done"
            elif dev_idx is not None:
                dir_reject = (
                    qa_verdict == "pass"
                    and (qa_idx or 0) > dev_idx
                    and squad_v2.director_delivery_rejected_after(comments, qa_idx or 0)
                )
                status = (
                    "current"
                    if dir_reject or (qa_verdict == "fail" and (qa_idx or 0) > dev_idx)
                    else "done"
                )
                if pr_url:
                    detail = (
                        "Director rejected — reworking"
                        if dir_reject
                        else ("PR open" if not at_or_past("release-candidate") else "PR merged")
                    )
            elif lc == "director-approved":
                status = "current"
                detail = "Developer implementing on the target repo"
        elif key == "qa":
            if at_or_past("release-candidate"):
                status = "done"
            elif dev_idx is None:
                status = "pending"
            elif qa_verdict == "pass" and (qa_idx or 0) > dev_idx:
                if squad_v2.director_delivery_rejected_after(comments, qa_idx or 0):
                    status = "current"
                    detail = "Director rejected — waiting for developer rework"
                else:
                    status = "done"
            elif qa_verdict == "fail" and (qa_idx or 0) > dev_idx:
                status = "blocked" if rounds >= squad_v2.MAX_QA_ROUNDS else "current"
                detail = (
                    f"QA requested changes — developer reworking ({rounds}/{squad_v2.MAX_QA_ROUNDS})"
                )
            else:
                status = "current"
                detail = "Reviewing the developer deliverable"
        elif key == "release-candidate":
            if lc == "released":
                status = "done"
            elif lc == "release-candidate":
                status = "director"
            else:
                status = "pending"
        elif key == "released":
            status = "done" if lc == "released" else "pending"

        if status == "director":
            detail = director_action or "Director decision required."
            action = {"label": "Open issue & respond", "url": issue_url, "message": detail}

        event: dict[str, Any] = {"key": key, "title": title, "owner": owner, "status": status, "detail": detail}
        if action:
            event["action"] = action
        if key == "implementation" and pr_url:
            event["pr_url"] = pr_url
        # Timestamp the step once it has actually happened (skip not-yet-reached).
        at = phase_at.get(key, "")
        if at and status != "pending":
            event["at"] = at
        events.append(event)
    return tuple(events)


def _load_job_card_v2(repo: str, row: dict) -> JobCard | None:
    title = str(row.get("title") or "")
    body = str(row.get("body") or "")
    if not _is_parent_job(title, body):
        return None

    number = int(row["number"])
    labels = tuple(item["name"] for item in row.get("labels") or [])
    state = str(row.get("state") or "OPEN")
    state_reason = str(row.get("stateReason") or "") or None
    updated_at = str(row.get("updatedAt") or "")
    comments = tuple(row.get("comments") or [])

    label_set = set(labels)
    blocked = "blocked" in label_set
    # `blocked` is an overlay, not a phase — derive the real phase from the
    # other labels so the timeline/agents still reflect progress.
    lc = squad_v2.current_lifecycle(label_set - {"blocked"} if blocked else label_set)
    view = squad_v2.IssueView(number, state, frozenset(labels), comments, body, state_reason)
    action = squad_v2.next_action(view)
    pr_url = _v2_dev_pr(comments)

    # Priority: released is done; an active agent run shows In progress even if
    # the issue is closed; `blocked` outranks closed (Blocked tab); then closed.
    active_run = squad_v2.run_in_progress(tuple(comments)) is not None
    if lc == "released":
        bucket = "completed"
    elif active_run and not blocked:
        bucket = "in_progress"
    elif blocked:
        bucket = "stuck"
    elif (
        state.upper() == "CLOSED"
        and (state_reason or "").upper() == "COMPLETED"
        and lc != "release-candidate"
        and not active_run
    ):
        bucket = "completed"
    elif squad_v2.squad_closed_job_still_active(
        state, label_set, tuple(comments), state_reason=state_reason
    ):
        bucket = "needs_you" if lc == "release-candidate" else "in_progress"
    elif squad_v2.squad_job_is_done(
        state, label_set, comments=tuple(comments), state_reason=state_reason
    ):
        bucket = "completed"
    elif lc in _V2_DIRECTOR_GATES:
        bucket = "needs_you"
    elif action.kind == "failed":
        bucket = "stuck"
    else:
        bucket = "in_progress"

    director_action = _director_action_for_card(bucket, lc)
    issue_url = f"https://github.com/{repo}/issues/{number}"
    stuck_reasons: tuple[str, ...] = (action.reason,) if action.kind == "failed" else ()
    failure_mode = squad_v2.classify_failure_mode(
        tuple(comments), frozenset(labels), action_kind=action.kind, action_reason=action.reason
    )
    if failure_mode:
        stuck_reasons = stuck_reasons + (f"failure_mode:{failure_mode}",)

    pending = action.agent if action.kind == "dispatch" else None
    active_agent = squad_v2.run_in_progress(tuple(comments)) or ""

    if bucket == "completed":
        headline = "This job is done."
    elif bucket == "needs_you":
        headline = _headline_for_card("needs_you", lc, (), False)
    elif bucket == "stuck":
        headline = action.reason or "This job needs attention."
    elif action.kind == "dispatch" and not active_run:
        headline = f"Queued — {action.reason or 'next agent dispatch'}"
    elif active_agent:
        label = active_agent.replace("-", " ").title()
        headline = f"{label} running now — check GitHub Actions for live progress."
    else:
        headline = action.reason or "Squad is working — nothing needed from you."

    agents = _v2_agents(
        repo, number, comments, lc, pr_url, pending_agent=pending, active_agent=active_agent or None
    )
    events = _v2_events(
        lc=lc,
        bucket=bucket,
        comments=comments,
        director_action=director_action,
        issue_url=issue_url,
        pr_url=pr_url,
    )

    return JobCard(
        number=number,
        title=title,
        url=issue_url,
        lifecycle=lc,
        active_agent=active_agent,
        bucket=bucket,
        blocked=blocked,
        updated_at=updated_at,
        target_repo=squad_v2.resolve_target_repo(body, tuple(comments)),
        target_pr_url=pr_url,
        target_pr_merged=lc in ("release-candidate", "released") and pr_url is not None,
        summary=headline,
        headline=headline,
        director_action=director_action,
        labels=labels,
        stuck_reasons=stuck_reasons,
        suggested_action="",
        agents=agents,
        events=events,
    )


def build_dashboard(repo: str = DEFAULT_REPO, *, include_closed: int = 15) -> DirectorDashboard:
    """List parent jobs by bucket. Open jobs surface needs-you / in-progress /
    stuck; recently closed or released jobs land in ``completed`` (the Done tab)."""
    index = SquadIssueIndex.from_repo(repo, include_closed=include_closed)
    rows = list(index.by_number.values())
    v2 = squad_v2.v2_enabled()

    buckets: dict[str, list[JobCard]] = {
        "needs_you": [],
        "in_progress": [],
        "stuck": [],
        "completed": [],
    }
    for row in rows:
        card = _load_job_card_v2(repo, row) if v2 else _load_job_card(repo, row, index=index)
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
