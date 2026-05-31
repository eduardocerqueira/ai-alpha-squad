"""Short Director WhatsApp messages for squad lifecycle steps."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LifecycleStep:
    headline: str
    status: str
    next_step: str


# Keys match GitHub lifecycle labels or notify script step names.
LIFECYCLE_STEPS: dict[str, LifecycleStep] = {
    "new": LifecycleStep(
        headline="Job started",
        status="Business Owner is analyzing the request.",
        next_step="BA will post on GitHub; watch for approval message.",
    ),
    "awaiting-approval": LifecycleStep(
        headline="Approval needed",
        status="Business Analysis is ready on GitHub.",
        next_step="Reply APPROVE, REJECT: reason, or CHANGES: details.",
    ),
    "director-approved": LifecycleStep(
        headline="Approved",
        status="Scope approved. Architect is starting.",
        next_step="Tech spec + sub-issues on GitHub, then Developer.",
    ),
    "designed": LifecycleStep(
        headline="Design complete",
        status="Technical specification and sub-issues are ready.",
        next_step="Developer implements on the target repo.",
    ),
    "implemented": LifecycleStep(
        headline="Build complete",
        status="Implementation PR is in progress or merged.",
        next_step="QA, Security, DevOps, and Docs validate.",
    ),
    "validation": LifecycleStep(
        headline="Validation",
        status="QA, Security, DevOps, and Docs are checking quality.",
        next_step="Release Manager prepares release candidate.",
    ),
    "release-candidate": LifecycleStep(
        headline="Release candidate",
        status="Release is ready for your decision.",
        next_step="Reply APPROVE to ship or REJECT: reason.",
    ),
    "released": LifecycleStep(
        headline="Released",
        status="Release is published.",
        next_step="None — issue will close.",
    ),
    "blocked": LifecycleStep(
        headline="Blocked",
        status="Work stopped until the blocker is resolved.",
        next_step="Check GitHub issue for details and owner.",
    ),
    "dispatched-business-owner": LifecycleStep(
        headline="Agent: Business Owner",
        status="Copilot is writing the Business Analysis.",
        next_step="You approve when label awaiting-approval is set.",
    ),
    "dispatched-architect": LifecycleStep(
        headline="Agent: Architect",
        status="Copilot is writing the tech spec and sub-issues.",
        next_step="Track progress on GitHub issue comments.",
    ),
    "inbound-approve": LifecycleStep(
        headline="APPROVE received",
        status="Your WhatsApp reply was recorded on GitHub.",
        next_step="Architect is starting (director-approved).",
    ),
    "inbound-reject": LifecycleStep(
        headline="REJECT received",
        status="Your WhatsApp reply was recorded on GitHub.",
        next_step="Business Owner will revise the analysis.",
    ),
    "inbound-changes": LifecycleStep(
        headline="CHANGES received",
        status="Your WhatsApp reply was recorded on GitHub.",
        next_step="Business Owner will clarify on the issue.",
    ),
    "unauthorized-approval": LifecycleStep(
        headline="Approval blocked",
        status="Someone tried to approve without Director authority.",
        next_step="No action needed — only you can approve.",
    ),
}


def issue_url(issue_number: int, repo: str = "eduardocerqueira/ai-alpha-squad") -> str:
    owner, name = repo.split("/", 1) if "/" in repo else ("eduardocerqueira", repo)
    return f"https://github.com/{owner}/{name}/issues/{issue_number}"


def format_lifecycle_message(
    step: str,
    issue_number: int,
    title: str,
    *,
    repo: str = "eduardocerqueira/ai-alpha-squad",
    extra: str | None = None,
) -> str:
    """Short objective WhatsApp body for a lifecycle step."""
    cfg = LIFECYCLE_STEPS.get(step)
    if cfg is None:
        raise ValueError(f"Unknown lifecycle step: {step}")

    short_title = title if len(title) <= 72 else f"{title[:69]}..."
    lines = [
        f"[AI Alpha Squad] {cfg.headline}",
        "",
        f"#{issue_number} — {short_title}",
        f"Now: {cfg.status}",
        f"Next: {cfg.next_step}",
    ]
    if extra:
        lines.append(extra)
    lines.extend(["", issue_url(issue_number, repo)])
    return "\n".join(lines)


def format_business_analysis_ready(
    issue_number: int,
    title: str,
    *,
    summary: str,
    repo: str = "eduardocerqueira/ai-alpha-squad",
) -> str:
    """Backward-compatible wrapper for awaiting-approval."""
    body = format_lifecycle_message(
        "awaiting-approval",
        issue_number,
        title,
        repo=repo,
    )
    return body.replace(
        "Now: Business Analysis is ready on GitHub.",
        f"Now: Business Analysis is ready.\nSummary: {summary}",
    )
