"""Minimal squad pipeline (v2): Business Owner + Developer, single issue, sequential."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

from ai_alpha_squad.nudge import issue_has_deliverable

LIFECYCLE_LABELS_V2: tuple[str, ...] = (
    "released",
    "blocked",
    "release-candidate",
    "director-approved",
    "awaiting-approval",
    "new",
)

GATE_LABELS = frozenset({"awaiting-approval", "release-candidate"})
AGENTS_V2 = ("business-owner", "developer")

DELIVERABLE_MARKERS: dict[str, str] = {
    "business-owner": "# Business Analysis",
    "developer": "# Developer Deliverable",
}

RUN_IN_PROGRESS_MARKER = "squad-v2-run:in_progress:"
RUN_FAILED_MARKER = "squad-v2-run:failed:"
MAX_RUN_ATTEMPTS = 3

_TARGET_REPO_RE = re.compile(
    r"https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)",
)


@dataclass(frozen=True)
class IssueView:
    number: int
    state: str
    labels: frozenset[str]
    comments: tuple[dict[str, Any], ...]
    body: str


@dataclass(frozen=True)
class NextAction:
    kind: str  # dispatch | gate | idle | done | failed
    agent: str | None = None
    reason: str = ""


def v2_enabled() -> bool:
    return os.environ.get("SQUAD_V2", "").strip() in ("1", "true", "yes")


def current_lifecycle(labels: set[str] | frozenset[str]) -> str | None:
    for label in LIFECYCLE_LABELS_V2:
        if label in labels:
            return label
    return None


def extract_target_repo(body: str) -> str | None:
    for match in _TARGET_REPO_RE.finditer(body or ""):
        repo = match.group(1)
        if "ai-alpha-squad" not in repo.lower():
            return repo
    return None


def has_deliverable(comments: tuple[dict, ...], agent: str) -> bool:
    marker = DELIVERABLE_MARKERS.get(agent, "")
    if not marker:
        return False
    return issue_has_deliverable(list(comments), marker)


def run_in_progress(comments: tuple[dict, ...]) -> str | None:
    for comment in reversed(comments):
        body = (comment.get("body") or "").lower()
        for agent in AGENTS_V2:
            if f"{RUN_IN_PROGRESS_MARKER}{agent}" not in body:
                continue
            # Stale marker left after a successful deliverable (common when label sync races).
            if has_deliverable(comments, agent):
                continue
            # Failed run finished — allow re-dispatch (in_progress comment may remain).
            if run_failures(comments, agent) > 0:
                continue
            return agent
    return None


def run_failures(comments: tuple[dict, ...], agent: str) -> int:
    needle = f"{RUN_FAILED_MARKER}{agent}"
    return sum(1 for c in comments if needle in (c.get("body") or "").lower())


def next_action(view: IssueView) -> NextAction:
    if view.state.upper() == "CLOSED":
        return NextAction("done", reason="Issue closed")

    lc = current_lifecycle(view.labels)
    if lc is None:
        return NextAction("idle", reason="No lifecycle label")

    if lc in GATE_LABELS:
        return NextAction("gate", reason=f"Waiting for Director ({lc})")

    if lc == "released":
        return NextAction("done", reason="Released")

    if lc == "blocked":
        return NextAction("idle", reason="Manually blocked")

    active = run_in_progress(view.comments)
    if active:
        return NextAction("idle", reason=f"Agent {active} run in progress")

    if lc == "new":
        if has_deliverable(view.comments, "business-owner"):
            return NextAction("idle", reason="BA present — sync should add awaiting-approval")
        if run_failures(view.comments, "business-owner") >= MAX_RUN_ATTEMPTS:
            return NextAction(
                "failed",
                agent="business-owner",
                reason="Business Owner exceeded retry limit",
            )
        return NextAction("dispatch", agent="business-owner", reason="Post Business Analysis")

    if lc == "awaiting-approval":
        return NextAction("gate", reason="Director must approve BA")

    if lc == "director-approved":
        if has_deliverable(view.comments, "developer"):
            return NextAction(
                "idle",
                reason="Developer deliverable posted — sync should add release-candidate",
            )
        if not extract_target_repo(view.body):
            return NextAction("failed", reason="Missing target repo URL in issue body")
        if run_failures(view.comments, "developer") >= MAX_RUN_ATTEMPTS:
            return NextAction(
                "failed",
                agent="developer",
                reason="Developer exceeded retry limit",
            )
        return NextAction(
            "dispatch",
            agent="developer",
            reason="Implement on target repo; post # Developer Deliverable",
        )

    if lc == "release-candidate":
        return NextAction("gate", reason="Director release approval")

    return NextAction("idle", reason=f"Unhandled phase {lc}")


def in_progress_comment(agent: str) -> str:
    return f"{RUN_IN_PROGRESS_MARKER}{agent} — do not start another agent on this issue."


def failed_comment(agent: str, error: str) -> str:
    text = (error or "unknown error").strip()[:500]
    return f"{RUN_FAILED_MARKER}{agent} — {text}"
