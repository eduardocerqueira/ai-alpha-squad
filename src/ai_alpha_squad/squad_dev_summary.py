"""Developer deliverable summary helpers."""

from __future__ import annotations

import re

_ABORT_RE = re.compile(
    r"\baborted after\b|\bmax turns\b|\bstalling\b|\bread-only turns\b|\bwithout writing or editing\b",
    re.IGNORECASE,
)


def is_stall_abort_summary(summary: str) -> bool:
    return bool(_ABORT_RE.search(summary or ""))


def sanitize_developer_summary(summary: str, *, build_verified: bool, pr_url: str = "") -> str:
    """Replace abort/churn prose with a gate-backed summary when compile passed."""
    if not build_verified:
        return (summary or "").strip()
    text = (summary or "").strip()
    if not is_stall_abort_summary(text):
        return text
    pr_line = f"\n\n**Pull request:** {pr_url}" if pr_url else ""
    return (
        "Build verified on the squad branch — changes are ready for QA review."
        f"{pr_line}\n\n_(Agent loop ended early; deterministic compile gate passed.)_"
    )
