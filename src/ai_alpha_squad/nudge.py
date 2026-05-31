"""Orchestrator nudge: detect missing deliverables and cooldown between re-dispatches."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

NUDGE_MARKER = "Squad orchestrator nudge"
GUARD_MARKER = "Squad PR guard"

PHASE_MARKERS: dict[str, str] = {
    "business-owner": "# Business Analysis",
    "architect": "# Technical Specification",
}

ARCHITECT_SUBISSUE_ROLES = ("developer", "qa", "security", "devops", "tech-writer")


def parse_github_timestamp(value: str) -> datetime:
    """Parse GitHub ISO-8601 timestamps (Z or offset)."""
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized).astimezone(timezone.utc)


def comment_body(comment: dict[str, Any]) -> str:
    return comment.get("body") or ""


def is_orchestrator_noise(body: str) -> bool:
    lowered = body.lower()
    return NUDGE_MARKER.lower() in lowered or GUARD_MARKER.lower() in lowered


def has_heading_marker(body: str, marker: str) -> bool:
    pattern = re.compile(rf"(?m)^{re.escape(marker)}\s")
    return bool(pattern.search(body))


def issue_has_deliverable(comments: list[dict[str, Any]], marker: str) -> bool:
    for comment in comments:
        body = comment_body(comment)
        if is_orchestrator_noise(body):
            continue
        if has_heading_marker(body, marker):
            return True
    return False


def minutes_since(timestamp: str | None, *, now: datetime | None = None) -> float | None:
    if not timestamp:
        return None
    current = now or datetime.now(timezone.utc)
    delta = current - parse_github_timestamp(timestamp)
    return delta.total_seconds() / 60.0


def last_nudge_minutes_ago(comments: list[dict[str, Any]], *, now: datetime | None = None) -> float | None:
    for comment in reversed(comments):
        body = comment_body(comment)
        if NUDGE_MARKER not in body:
            continue
        return minutes_since(comment.get("createdAt"), now=now)
    return None


def should_nudge_phase(
    *,
    has_deliverable: bool,
    minutes_since_created: float | None,
    minutes_since_last_nudge: float | None,
    force: bool,
    min_age_minutes: float = 15.0,
    cooldown_minutes: float = 30.0,
) -> bool:
    if has_deliverable:
        return False
    if force:
        return True
    if minutes_since_created is not None and minutes_since_created < min_age_minutes:
        return False
    if minutes_since_last_nudge is not None and minutes_since_last_nudge < cooldown_minutes:
        return False
    return True


def architect_subissues_complete(subissue_numbers: dict[str, int | None]) -> bool:
    return all(subissue_numbers.get(role) for role in ARCHITECT_SUBISSUE_ROLES)


def labels_include(labels: list[str], name: str) -> bool:
    return name in labels
