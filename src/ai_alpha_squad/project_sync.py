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


def derive_state(labels: set[str]) -> Derived:
    lifecycle = current_lifecycle(labels)
    agents_on_issue = sorted(labels & AGENT_LABELS)

    if lifecycle is None:
        active_agent = agents_on_issue[0] if agents_on_issue else "Unassigned"
    elif lifecycle == "implemented" and len(agents_on_issue) == 1:
        active_agent = agents_on_issue[0]
    elif lifecycle in PHASE_TO_AGENT:
        active_agent = PHASE_TO_AGENT[lifecycle]
    else:
        active_agent = agents_on_issue[0] if agents_on_issue else "Unassigned"

    needs_director = "Yes" if lifecycle in {"awaiting-approval", "release-candidate"} else "No"
    return Derived(lifecycle=lifecycle, active_agent=active_agent, needs_director=needs_director)
