"""Derive GitHub Project field values from squad issue labels."""
from __future__ import annotations

from dataclasses import dataclass

LIFECYCLE_LABELS = (
    "released",
    "blocked",
    "release-candidate",
    "validation",
    "implemented",
    "designed",
    "director-approved",
    "awaiting-approval",
    "new",
)

AGENT_LABELS = frozenset(
    {
        "business-owner",
        "architect",
        "developer",
        "qa",
        "security",
        "devops",
        "tech-writer",
        "release-manager",
    }
)

# Shown on the project board when lifecycle label advanced but deliverable is still missing.
AGENT_PENDING_ON_ISSUE = "blocked — post on issue"

PHASE_TO_AGENT: dict[str, str] = {
    "new": "business-owner",
    "awaiting-approval": "Director",
    "director-approved": "architect",
    "designed": "developer",
    "implemented": "developer",
    "validation": "release-manager",
    "release-candidate": "Director",
    "released": "Done",
    "blocked": "Blocked",
}

VALIDATION_AGENT_LABELS = frozenset({"qa", "security", "devops", "tech-writer"})

# GitHub Project single-select options (see scripts/squad_project_sync.py ensure-fields)
COPILOT_SESSION_SUFFIX = " (Copilot x{count})"
PARALLEL_VALIDATION_AGENT = "validation (parallel)"


@dataclass(frozen=True)
class PlanningDeliverables:
    """Whether required issue comments exist (not merely Copilot PR stubs)."""

    has_business_analysis: bool = False
    has_technical_spec: bool = False


@dataclass(frozen=True)
class Derived:
    lifecycle: str | None
    active_agent: str
    needs_director: str


def current_lifecycle(labels: set[str]) -> str | None:
    for label in LIFECYCLE_LABELS:
        if label in labels:
            return label
    return None


def format_active_agent(base_agent: str, *, copilot_sessions: int = 1) -> str:
    """Append Copilot session count for project board visibility."""
    if base_agent == AGENT_PENDING_ON_ISSUE:
        return base_agent
    if copilot_sessions <= 1:
        return base_agent
    return f"{base_agent}{COPILOT_SESSION_SUFFIX.format(count=copilot_sessions)}"


def base_active_agent(
    labels: set[str],
    lifecycle: str | None,
    *,
    planning: PlanningDeliverables | None = None,
) -> str:
    agents_on_issue = sorted(labels & AGENT_LABELS)
    deliverables = planning or PlanningDeliverables()

    if lifecycle == "new" and not deliverables.has_business_analysis:
        return AGENT_PENDING_ON_ISSUE
    if lifecycle == "director-approved" and not deliverables.has_technical_spec:
        return AGENT_PENDING_ON_ISSUE

    if lifecycle is None:
        return agents_on_issue[0] if agents_on_issue else "Unassigned"
    if lifecycle == "implemented":
        validation_on_parent = sorted(labels & VALIDATION_AGENT_LABELS)
        if len(validation_on_parent) >= 2:
            return PARALLEL_VALIDATION_AGENT
        if len(validation_on_parent) == 1:
            return validation_on_parent[0]
        if len(agents_on_issue) == 1:
            return agents_on_issue[0]
    if lifecycle in PHASE_TO_AGENT:
        return PHASE_TO_AGENT[lifecycle]
    return agents_on_issue[0] if agents_on_issue else "Unassigned"


def derive_state(
    labels: set[str],
    *,
    copilot_sessions: int = 1,
    planning: PlanningDeliverables | None = None,
) -> Derived:
    lifecycle = current_lifecycle(labels)
    base = base_active_agent(labels, lifecycle, planning=planning)
    if base == PARALLEL_VALIDATION_AGENT:
        active_agent = base
    else:
        active_agent = format_active_agent(base, copilot_sessions=copilot_sessions)
    needs_director = "Yes" if lifecycle in {"awaiting-approval", "release-candidate"} else "No"
    return Derived(lifecycle=lifecycle, active_agent=active_agent, needs_director=needs_director)
