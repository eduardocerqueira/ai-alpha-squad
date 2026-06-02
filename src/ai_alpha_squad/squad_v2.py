"""Minimal squad pipeline (v2): Business Owner + Developer, single issue, sequential."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime
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
AGENTS_V2 = ("business-owner", "developer", "qa")

DELIVERABLE_MARKERS: dict[str, str] = {
    "business-owner": "# Business Analysis",
    "developer": "# Developer Deliverable",
    "qa": "# QA Report",
}

# QA verdict markers embedded in the # QA Report comment, parsed deterministically
# so the orchestrator never interprets prose.
QA_PASS_MARKER = "squad-v2-qa:pass"
QA_FAIL_MARKER = "squad-v2-qa:fail"
# Max Developer⇄QA rework rounds before escalating to the Director.
MAX_QA_ROUNDS = 3

RUN_IN_PROGRESS_MARKER = "squad-v2-run:in_progress:"
RUN_FAILED_MARKER = "squad-v2-run:failed:"
RUN_RESET_MARKER = "squad-v2-run:reset:"
# Non-retryable setup/permission failure. Deliberately NOT a substring of
# RUN_FAILED_MARKER so it does not count toward the retry cap — these need a
# human (grant access, create the branch), not another agent attempt.
RUN_SETUP_FAILED_MARKER = "squad-v2-run:setup-failed:"
MAX_RUN_ATTEMPTS = 3
# A run with an in_progress marker older than this with no terminal marker is
# treated as dead (orchestrator timeout is 90m, so this must stay above it).
STALE_RUN_MINUTES = 120

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
    text = body or ""
    # Prefer a URL on a line that explicitly names the target, so incidental
    # github.com links elsewhere in the body cannot be mistaken for the target.
    for line in text.splitlines():
        if "target" not in line.lower():
            continue
        for match in _TARGET_REPO_RE.finditer(line):
            if "ai-alpha-squad" not in match.group(1).lower():
                return match.group(1)
    # Fallback: first non-self github URL anywhere in the body.
    for match in _TARGET_REPO_RE.finditer(text):
        if "ai-alpha-squad" not in match.group(1).lower():
            return match.group(1)
    return None


def has_deliverable(comments: tuple[dict, ...], agent: str) -> bool:
    marker = DELIVERABLE_MARKERS.get(agent, "")
    if not marker:
        return False
    return issue_has_deliverable(list(comments), marker)


def _latest_deliverable_index(comments: tuple[dict, ...], agent: str) -> int | None:
    """Index of the agent's most recent deliverable comment (by heading)."""
    from ai_alpha_squad.nudge import has_heading_marker, is_orchestrator_noise

    marker = DELIVERABLE_MARKERS.get(agent, "")
    if not marker:
        return None
    idx: int | None = None
    for i, comment in enumerate(comments):
        body = comment.get("body") or ""
        if is_orchestrator_noise(body):
            continue
        if has_heading_marker(body, marker):
            idx = i
    return idx


def latest_qa_verdict(comments: tuple[dict, ...]) -> tuple[int | None, str | None]:
    """Index and verdict ('pass'|'fail') of the most recent QA verdict marker."""
    idx: int | None = None
    verdict: str | None = None
    for i, comment in enumerate(comments):
        body = (comment.get("body") or "").lower()
        if QA_FAIL_MARKER in body:
            idx, verdict = i, "fail"
        elif QA_PASS_MARKER in body:
            idx, verdict = i, "pass"
    return idx, verdict


def qa_fail_rounds(comments: tuple[dict, ...]) -> int:
    return sum(1 for c in comments if QA_FAIL_MARKER in (c.get("body") or "").lower())


# --- Developer model-escalation ladder ---
# After MAX_QA_ROUNDS rejections on a model, escalate the developer to the next
# model in the ladder (a marker records it) and give it a fresh set of rounds;
# block only when the ladder is exhausted.
RUN_MODEL_MARKER = "squad-v2-model:"
_MODEL_RE = re.compile(r"squad-v2-model:(\S+)")


def dev_model_ladder(raw: str | None) -> list[str]:
    """Parse a comma/whitespace/newline-separated model ladder; de-duped, ordered."""
    parts = re.split(r"[,\s]+", (raw or "").strip())
    seen: set[str] = set()
    out: list[str] = []
    for p in parts:
        p = p.strip()
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    return out


def _latest_model_marker(comments: tuple[dict, ...]) -> tuple[int | None, str | None]:
    idx: int | None = None
    model: str | None = None
    for i, c in enumerate(comments):
        m = _MODEL_RE.search(c.get("body") or "")
        if m:
            idx, model = i, m.group(1)
    return idx, model


def qa_fails_since_escalation(comments: tuple[dict, ...]) -> int:
    """QA failures since the latest model-escalation marker (the current tier)."""
    mk_idx, _ = _latest_model_marker(comments)
    start = mk_idx if mk_idx is not None else -1
    return sum(
        1
        for i, c in enumerate(comments)
        if i > start and QA_FAIL_MARKER in (c.get("body") or "").lower()
    )


def current_dev_model(comments: tuple[dict, ...], ladder: list[str]) -> str | None:
    """The developer model currently in effect (latest marker, else ladder base)."""
    _, model = _latest_model_marker(comments)
    if model:
        return model
    return ladder[0] if ladder else None


def next_dev_model(comments: tuple[dict, ...], ladder: list[str]) -> str | None:
    """The next model up the ladder from the current one (None if at/after the top)."""
    if not ladder:
        return None
    cur = current_dev_model(comments, ladder)
    if cur in ladder:
        i = ladder.index(cur)
        return ladder[i + 1] if i + 1 < len(ladder) else None
    # Current model isn't in the ladder (custom/Director-chosen) → no auto-next.
    return None


def model_marker_comment(model: str) -> str:
    return (
        f"{RUN_MODEL_MARKER}{model} — developer model escalated after "
        f"{MAX_QA_ROUNDS} QA rejections; fresh attempts on this model."
    )


def qa_passed(comments: tuple[dict, ...]) -> bool:
    """True when the latest developer deliverable has since been QA-approved."""
    dev_idx = _latest_deliverable_index(comments, "developer")
    qa_idx, verdict = latest_qa_verdict(comments)
    return (
        dev_idx is not None
        and qa_idx is not None
        and qa_idx > dev_idx
        and verdict == "pass"
    )


def squad_work_branch(agent: str, issue: int) -> str:
    """One stable branch (and PR) per queue issue + agent."""
    slug = agent.strip().lower().replace(" ", "-")
    return f"squad/{slug}-issue-{issue}"


def _latest_marker_index(comments: tuple[dict, ...], needle: str) -> int | None:
    idx: int | None = None
    for i, comment in enumerate(comments):
        if needle in (comment.get("body") or "").lower():
            idx = i
    return idx


def _failure_after_in_progress(comments: tuple[dict, ...], agent: str) -> bool:
    """True if a failed marker appears after the latest in_progress marker for this agent."""
    needle_prog = f"{RUN_IN_PROGRESS_MARKER}{agent}"
    needle_fail = f"{RUN_FAILED_MARKER}{agent}"
    in_progress_idx = _latest_marker_index(comments, needle_prog)
    failure_idx = _latest_marker_index(comments, needle_fail)
    if in_progress_idx is None or failure_idx is None:
        return False
    return failure_idx > in_progress_idx


def _agent_run_completed_after_in_progress(comments: tuple[dict, ...], agent: str) -> bool:
    """True if an Actions/HF result comment was posted after the latest in_progress marker."""
    needle_prog = f"{RUN_IN_PROGRESS_MARKER}{agent}"
    in_progress_idx = _latest_marker_index(comments, needle_prog)
    if in_progress_idx is None:
        return False
    slug = agent.replace("-", " ")
    for comment in comments[in_progress_idx + 1 :]:
        body = (comment.get("body") or "").lower()
        if "squad actions agent result" in body and slug in body:
            return True
        if "squad hf agent result" in body and slug in body:
            return True
    return False


def run_in_progress(comments: tuple[dict, ...]) -> str | None:
    for comment in reversed(comments):
        body = (comment.get("body") or "").lower()
        for agent in AGENTS_V2:
            if f"{RUN_IN_PROGRESS_MARKER}{agent}" not in body:
                continue
            if has_deliverable(comments, agent):
                continue
            if _failure_after_in_progress(comments, agent):
                continue
            if _agent_run_completed_after_in_progress(comments, agent):
                continue
            return agent
    return None


def run_failures(comments: tuple[dict, ...], agent: str) -> int:
    """Count failures for this agent since the most recent reset marker.

    A ``reset`` marker (for this agent or ``all``) clears the counter so a
    deliberate retry — e.g. after an infra fix — gets a fresh set of attempts
    instead of staying permanently blocked by stale historical failures.
    """
    fail = f"{RUN_FAILED_MARKER}{agent}"
    reset_agent = f"{RUN_RESET_MARKER}{agent}"
    reset_all = f"{RUN_RESET_MARKER}all"
    reset_idx = -1
    for i, comment in enumerate(comments):
        body = (comment.get("body") or "").lower()
        if reset_agent in body or reset_all in body:
            reset_idx = i
    return sum(
        1
        for i, comment in enumerate(comments)
        if i > reset_idx and fail in (comment.get("body") or "").lower()
    )


def _comment_timestamp(comment: dict) -> datetime | None:
    raw = comment.get("createdAt") or comment.get("created_at")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None


def find_stale_in_progress(
    comments: tuple[dict, ...],
    now_iso: str,
    max_age_minutes: int = STALE_RUN_MINUTES,
) -> str | None:
    """Return an agent whose run looks dead: an in_progress marker with no
    terminal marker after it, older than ``max_age_minutes``.

    Recovers issues orphaned by a cancelled or timed-out run (which never gets
    to post a failure marker), otherwise stuck idle forever.
    """
    agent = run_in_progress(comments)
    if not agent:
        return None
    needle = f"{RUN_IN_PROGRESS_MARKER}{agent}"
    latest: datetime | None = None
    for comment in comments:
        if needle in (comment.get("body") or "").lower():
            ts = _comment_timestamp(comment)
            if ts and (latest is None or ts > latest):
                latest = ts
    now = None
    try:
        now = datetime.fromisoformat(str(now_iso).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        now = None
    if latest is None or now is None:
        return None
    age_minutes = (now - latest).total_seconds() / 60.0
    return agent if age_minutes >= max_age_minutes else None


def next_action(view: IssueView, model_ladder: list[str] | None = None) -> NextAction:
    if model_ladder is None:
        model_ladder = dev_model_ladder(os.environ.get("SQUAD_DEV_MODEL_LADDER"))
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
        if not extract_target_repo(view.body):
            return NextAction("failed", reason="Missing target repo URL in issue body")

        dev_idx = _latest_deliverable_index(view.comments, "developer")
        if dev_idx is None:
            if run_failures(view.comments, "developer") >= MAX_RUN_ATTEMPTS:
                return NextAction(
                    "failed", agent="developer", reason="Developer exceeded retry limit"
                )
            return NextAction(
                "dispatch",
                agent="developer",
                reason="Implement on target repo; post # Developer Deliverable",
            )

        # Developer deliverable exists → QA gates it before release-candidate.
        qa_idx, verdict = latest_qa_verdict(view.comments)
        if qa_idx is None or qa_idx < dev_idx:
            # Latest developer deliverable has not been QA-reviewed yet.
            if run_failures(view.comments, "qa") >= MAX_RUN_ATTEMPTS:
                return NextAction("failed", agent="qa", reason="QA agent failed to run")
            return NextAction(
                "dispatch", agent="qa", reason="QA review of the developer deliverable"
            )
        if verdict == "pass":
            return NextAction(
                "idle", reason="QA passed — sync should add release-candidate"
            )
        # QA rejected the latest deliverable → Developer reworks (capped per model).
        if qa_fails_since_escalation(view.comments) >= MAX_QA_ROUNDS:
            nxt = next_dev_model(view.comments, model_ladder)
            if nxt:
                # Escalate the developer to a stronger model and reset the rounds.
                # The dispatch posts the squad-v2-model marker and applies the model.
                return NextAction(
                    "dispatch",
                    agent="developer",
                    reason=f"QA rejected {MAX_QA_ROUNDS}× — escalating developer model to {nxt}",
                )
            return NextAction(
                "failed",
                agent="qa",
                reason=(
                    f"QA rejected the deliverable {MAX_QA_ROUNDS} times"
                    + (" and the model ladder is exhausted" if model_ladder else "")
                ),
            )
        if run_failures(view.comments, "developer") >= MAX_RUN_ATTEMPTS:
            return NextAction(
                "failed", agent="developer", reason="Developer exceeded retry limit"
            )
        return NextAction(
            "dispatch",
            agent="developer",
            reason="QA requested changes — rework the deliverable",
        )

    if lc == "release-candidate":
        return NextAction("gate", reason="Director release approval")

    return NextAction("idle", reason=f"Unhandled phase {lc}")


def is_squad_internal_comment(body: str) -> bool:
    """Comments that must not re-trigger phase watch (avoids feedback loops on #94)."""
    text = (body or "").lower()
    if (
        RUN_IN_PROGRESS_MARKER in text
        or RUN_FAILED_MARKER in text
        or RUN_RESET_MARKER in text
        or RUN_SETUP_FAILED_MARKER in text
        or RUN_MODEL_MARKER in text
    ):
        return True
    if QA_PASS_MARKER in text or QA_FAIL_MARKER in text:
        return True
    if "squad hf agent" in text or "squad actions agent" in text:
        return True
    if "squad orchestrator" in text and "<table>" in text:
        return True
    from ai_alpha_squad.nudge import is_orchestrator_noise

    return is_orchestrator_noise(body)


def in_progress_comment(agent: str) -> str:
    return f"{RUN_IN_PROGRESS_MARKER}{agent} — do not start another agent on this issue."


def failed_comment(agent: str, error: str) -> str:
    text = (error or "unknown error").strip()[:500]
    return f"{RUN_FAILED_MARKER}{agent} — {text}"


def setup_failed_comment(agent: str, reason: str) -> str:
    """Non-retryable escalation: a setup/permission problem a human must fix."""
    text = (reason or "setup error").strip()[:500]
    return (
        f"{RUN_SETUP_FAILED_MARKER}{agent} — {text}. "
        "This will not be retried automatically; fix the cause and re-run the orchestrator."
    )


def reset_comment(agent: str) -> str:
    return (
        f"{RUN_RESET_MARKER}{agent} — failure count cleared; "
        "agent gets a fresh set of retry attempts."
    )
