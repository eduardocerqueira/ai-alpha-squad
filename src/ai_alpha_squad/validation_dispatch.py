"""Phase 4 validation dispatch helpers (parallel QA / Security / DevOps / Tech Writer)."""
from __future__ import annotations

VALIDATION_ROLES: tuple[str, ...] = ("qa", "security", "devops", "tech-writer")

VALIDATION_DISPATCH_MARKER = "Squad orchestrator: Validation phase started"

ROLE_DISPATCH_MARKER_PREFIX = "validation-dispatch:"


def role_dispatch_marker(role: str) -> str:
    return f"{ROLE_DISPATCH_MARKER_PREFIX}{role}"


def parent_has_validation_dispatch(comments: list[dict], *, role: str | None = None) -> bool:
    """True if orchestrator already recorded dispatch for all roles or a specific role."""
    if role:
        needle = role_dispatch_marker(role).lower()
        for comment in comments:
            body = (comment.get("body") or "").lower()
            if needle in body:
                return True
        return False
    marker = VALIDATION_DISPATCH_MARKER.lower()
    for comment in comments:
        body = (comment.get("body") or "").lower()
        if marker in body:
            return True
    return False
