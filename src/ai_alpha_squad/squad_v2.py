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
# Closed issues with these lifecycle labels are not finished — reopen before dispatch.
ACTIVE_SQUAD_LIFECYCLES = frozenset({"new", "awaiting-approval", "director-approved", "release-candidate"})
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
# Director delivery gate (after dev + QA): reject re-opens dev⇄QA; accept completes the job.
DIRECTOR_DELIVERY_REJECT_MARKER = "squad-v2-director:delivery-reject"
DIRECTOR_DELIVERY_ACCEPT_MARKER = "squad-v2-director:delivery-accept"
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

# Applied (alongside `blocked`) when the squad has exhausted every model in the
# ladder and all retries without passing QA — i.e. the AI gave up and a human
# must take over. Distinct from `blocked` (which is any pause) so the Director
# dashboard can surface a clear "needs human assistance" state.
NEEDS_HUMAN_LABEL = "needs-human"

_TARGET_REPO_RE = re.compile(
    r"https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)",
)
_DELIVERABLE_PR_RE = re.compile(
    r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/pull/\d+",
    re.IGNORECASE,
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
    # True when `failed` because the AI exhausted every model + retry and still
    # couldn't pass QA → apply the needs-human label + a human-assistance message.
    needs_human: bool = False


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


def resolve_target_repo(body: str, comments: tuple[dict, ...] = ()) -> str | None:
    """Target repo from issue body, else newest Director comment with a product-repo URL."""
    found = extract_target_repo(body)
    if found:
        return found
    for comment in reversed(comments):
        body_text = comment.get("body") or ""
        if not body_text.strip():
            continue
        found = extract_target_repo(body_text)
        if found:
            return found
    return None


def has_deliverable(comments: tuple[dict, ...], agent: str) -> bool:
    marker = DELIVERABLE_MARKERS.get(agent, "")
    if not marker:
        return False
    return issue_has_deliverable(list(comments), marker)


def _developer_run_failed_after(comments: tuple[dict, ...], after_index: int) -> bool:
    needle = f"{RUN_FAILED_MARKER}developer"
    for i, comment in enumerate(comments):
        if i > after_index and needle in (comment.get("body") or "").lower():
            return True
    return False


def _deliverable_has_pr_link(body: str) -> bool:
    lower = body.lower()
    return "pull request" in lower or bool(_DELIVERABLE_PR_RE.search(body))


def _build_gate_failed_after(comments: tuple[dict, ...], after_index: int) -> bool:
    for i in range(after_index + 1, len(comments)):
        body = (comments[i].get("body") or "").lower()
        if "build verification failed" in body and "developer" in body:
            return True
        if QA_FAIL_MARKER in body and "# qa report" in body and "deterministic" in body:
            return True
    return False


def latest_trusted_developer_deliverable_index(comments: tuple[dict, ...]) -> int | None:
    """Developer deliverable that survived Actions (PR link, no later run/build failure)."""
    idx = _latest_deliverable_index(comments, "developer")
    if idx is None:
        return None
    body = comments[idx].get("body") or ""
    if not _deliverable_has_pr_link(body):
        return None
    if _developer_run_failed_after(comments, idx):
        return None
    if _build_gate_failed_after(comments, idx):
        return None
    return idx


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
    """Index and verdict ('pass'|'fail') of the most recent *valid* QA report."""
    from ai_alpha_squad.squad_qa import validate_qa_report

    for i in range(len(comments) - 1, -1, -1):
        body = comments[i].get("body") or ""
        lower = body.lower()
        if QA_FAIL_MARKER not in lower and QA_PASS_MARKER not in lower:
            continue
        verdict = validate_qa_report(body)
        if verdict:
            return i, verdict
    return None, None


def latest_invalid_qa_report_index(comments: tuple[dict, ...]) -> int | None:
    """Most recent comment that looks like QA but fails validation."""
    from ai_alpha_squad.squad_qa import validate_qa_report

    for i in range(len(comments) - 1, -1, -1):
        body = comments[i].get("body") or ""
        lower = body.lower()
        if "# qa report" not in lower:
            continue
        if QA_FAIL_MARKER in lower or QA_PASS_MARKER in lower:
            if validate_qa_report(body) is None:
                return i
    return None


_CODE_FENCE_RE = re.compile(r"```(?:\w+)?\n(.*?)```", re.DOTALL)


def _extract_last_code_fence(body: str) -> str | None:
    matches = _CODE_FENCE_RE.findall(body or "")
    if not matches:
        return None
    return matches[-1].strip()


def latest_qa_fail_excerpt(comments: tuple[dict, ...]) -> str | None:
    """Fixes-required section from the latest QA fail, for developer rework instructions."""
    idx, verdict = latest_qa_verdict(comments)
    if idx is None or verdict != "fail":
        return None
    body = comments[idx].get("body") or ""
    lower = body.lower()
    if "## fixes required" in lower:
        start = lower.index("## fixes required")
        return body[start:][:5000].strip()
    return body[:5000].strip() or None


def latest_build_failure_excerpt(
    comments: tuple[dict, ...], agent: str = "developer"
) -> str | None:
    """Compiler log from the latest deterministic build gate on the issue."""
    slug = agent.replace("-", " ")
    for comment in reversed(comments):
        body = comment.get("body") or ""
        lower = body.lower()
        if "build verification failed" in lower and slug in lower:
            return _extract_last_code_fence(body) or body[:5000].strip() or None
    return None


def developer_instruction_appendix(comments: tuple[dict, ...]) -> str:
    """Deterministic rework context appended to Actions developer instructions."""
    parts: list[str] = []
    qa = latest_qa_fail_excerpt(comments)
    if qa:
        parts.append(
            "## Prior QA rejection (address BLOCKER items first)\n\n"
            + qa
            + "\n\nGo straight to the named files — do not explore with list_dir first."
        )
    build = latest_build_failure_excerpt(comments)
    if build:
        from ai_alpha_squad.compile_diagnostics import format_compile_fix_list

        parsed = format_compile_fix_list(build)
        parts.append(
            "## Last build verification failure (must pass before finish)\n\n"
            f"```\n{build}\n```"
        )
        if parsed.strip():
            parts.append(parsed)
    return "\n\n".join(parts)


def auto_qa_pass_body(issue_body: str, *, build_ok: bool) -> str | None:
    """When compile-only and build passed, return deterministic QA pass comment body."""
    from ai_alpha_squad.squad_qa import format_auto_qa_pass_comment, is_compile_only_job

    if not build_ok or not is_compile_only_job(issue_body):
        return None
    return format_auto_qa_pass_comment(build_ok=True, compile_only=True)


def stall_model_escalation_body(
    comments: tuple[dict, ...], ladder: list[str]
) -> str | None:
    """After a stall abort, return model marker comment text if a stronger model exists."""
    nxt = next_dev_model(comments, ladder)
    cur = current_dev_model(comments, ladder)
    if nxt and nxt != cur:
        return model_marker_comment(nxt)
    return None


FAILURE_MODES = (
    "retry_cap",
    "qa_exhausted",
    "build_gate",
    "stall_abort",
    "invalid_qa",
    "needs_human",
)


def classify_failure_mode(
    comments: tuple[dict, ...],
    labels: frozenset[str],
    *,
    action_kind: str = "",
    action_reason: str = "",
) -> str | None:
    """Short failure taxonomy for dashboard / debugging."""
    if NEEDS_HUMAN_LABEL in labels:
        return "needs_human"
    reason = (action_reason or "").lower()
    if action_kind == "failed":
        if "retry limit" in reason or "exceeded retry" in reason:
            if "developer" in reason:
                return "retry_cap"
            if "qa" in reason:
                return "invalid_qa" if latest_invalid_qa_report_index(comments) is not None else "qa_exhausted"
        if "model ladder is exhausted" in reason or "qa rejected" in reason:
            return "qa_exhausted"
    if latest_build_failure_excerpt(comments):
        return "build_gate"
    for c in reversed(comments):
        body = (c.get("body") or "").lower()
        if "squad actions agent result" in body and "developer" in body:
            from ai_alpha_squad.squad_dev_summary import is_stall_abort_summary

            if is_stall_abort_summary(c.get("body") or ""):
                return "stall_abort"
            break
    if latest_invalid_qa_report_index(comments) is not None and latest_qa_verdict(comments)[0] is None:
        return "invalid_qa"
    return None


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


def models_tried(comments: tuple[dict, ...], ladder: list[str] | None = None) -> list[str]:
    """Distinct developer models used so far, in order: the ladder base (used
    before any escalation marker) followed by each escalated/forced model."""
    out: list[str] = []
    if ladder:
        out.append(ladder[0])
    for c in comments:
        m = _MODEL_RE.search(c.get("body") or "")
        if m:
            out.append(m.group(1))
    seen: set[str] = set()
    deduped: list[str] = []
    for m in out:
        if m and m not in seen:
            seen.add(m)
            deduped.append(m)
    return deduped


def _latest_qa_blocker(comments: tuple[dict, ...]) -> str | None:
    """The most actionable line from the latest QA report — the first BLOCKER /
    fix item — so the human knows where the squad got stuck."""
    qa_idx, _ = latest_qa_verdict(comments)
    if qa_idx is None:
        return None
    body = comments[qa_idx].get("body") or ""
    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
    for ln in lines:
        if "[BLOCKER]" in ln:
            return ln.lstrip("-* ").strip()
    # Fall back to the first numbered fix under "## Fixes required".
    in_fixes = False
    for ln in lines:
        if ln.lower().startswith("## fixes"):
            in_fixes = True
            continue
        if in_fixes and (ln[:2].rstrip(".").isdigit() or ln.startswith(("-", "*"))):
            return ln.lstrip("-*0123456789. ").strip()
    return None


def human_assistance_summary(
    comments: tuple[dict, ...], ladder: list[str] | None = None
) -> str:
    """Human-readable message posted when the squad gives up: how many times it
    tried, on which models, and the last blocker — so a person can take over."""
    attempts = sum(
        1 for c in comments if DELIVERABLE_MARKERS["developer"] in (c.get("body") or "")
    )
    qa_rounds = sum(1 for c in comments if QA_FAIL_MARKER in (c.get("body") or "").lower())
    models = models_tried(comments, ladder)
    blocker = _latest_qa_blocker(comments)

    model_phrase = (
        f"{len(models)} model(s) ({', '.join(models)})" if models else "the available model(s)"
    )
    lines = [
        "🚫 **This task needs human assistance.**",
        "",
        f"The AI Alpha Squad attempted this **{max(attempts, 1)} time(s)** across "
        f"**{model_phrase}** over **{qa_rounds} QA review round(s)**, but could not "
        "satisfy every acceptance criterion.",
    ]
    if blocker:
        lines += ["", "**Last blocker from QA:**", f"> {blocker}"]
    lines += [
        "",
        "👉 A human should review the open pull request and take over. After "
        "addressing the blocker, re-run this issue from the Director dashboard "
        "(or re-dispatch the orchestrator) to hand it back to the squad.",
    ]
    return "\n".join(lines)


def director_delivery_rejected_after(comments: tuple[dict, ...], after_index: int) -> bool:
    needle = DIRECTOR_DELIVERY_REJECT_MARKER.lower()
    for i, comment in enumerate(comments):
        if i > after_index and needle in (comment.get("body") or "").lower():
            return True
    return False


def format_director_delivery_reject_comment(reason: str = "") -> str:
    lines = ["**Director:** Job rejected by director."]
    if reason.strip():
        lines.extend(["", reason.strip()])
    lines.extend(["", DIRECTOR_DELIVERY_REJECT_MARKER])
    return "\n".join(lines)


def format_director_delivery_accept_comment() -> str:
    return (
        "Released — job accepted by Director.\n\n"
        "**Director:** Delivery accepted. Job complete.\n\n"
        f"{DIRECTOR_DELIVERY_ACCEPT_MARKER}"
    )


def _qa_pass_still_valid(
    comments: tuple[dict, ...],
    *,
    issue_body: str,
    queue_repo: str,
    issue_number: int,
    target_repo: str | None,
) -> bool:
    """Re-check PR quality + build gate so stale auto-QA passes cannot idle the job."""
    qa_idx, verdict = latest_qa_verdict(comments)
    if verdict != "pass" or qa_idx is None:
        return False
    qa_body = comments[qa_idx].get("body") or ""
    from ai_alpha_squad.squad_qa import validate_pr_changed_files
    from ai_alpha_squad.target_build_verify import (
        gate_pr_before_qa,
        issue_requires_package,
        list_pr_changed_files,
    )

    if "compile-only job" in qa_body.lower() and issue_requires_package(issue_body):
        return False
    if not target_repo:
        return True
    changed = list_pr_changed_files(target_repo, issue_number)
    if not changed:
        # No open squad PR or gh unavailable — do not invalidate on ambiguity.
        return True
    ok, _ = validate_pr_changed_files(changed)
    if not ok:
        return False
    return gate_pr_before_qa(
        queue_repo, issue_number, target_repo, issue_body=issue_body, post_comment=False
    )


def qa_passed(
    comments: tuple[dict, ...],
    *,
    issue_body: str = "",
    queue_repo: str = "",
    issue_number: int = 0,
    target_repo: str | None = None,
) -> bool:
    """True when the latest trusted developer deliverable has since been QA-approved."""
    dev_idx = latest_trusted_developer_deliverable_index(comments)
    qa_idx, verdict = latest_qa_verdict(comments)
    if not (
        dev_idx is not None
        and qa_idx is not None
        and qa_idx > dev_idx
        and verdict == "pass"
    ):
        return False
    if director_delivery_rejected_after(comments, qa_idx):
        return False
    if target_repo and queue_repo and issue_number:
        if not _qa_pass_still_valid(
            comments,
            issue_body=issue_body,
            queue_repo=queue_repo,
            issue_number=issue_number,
            target_repo=target_repo,
        ):
            return False
    return True


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
    in_progress_idx = _latest_marker_index(comments, needle_prog)
    if in_progress_idx is None:
        return False
    return _run_terminal_after_index(comments, agent, in_progress_idx)


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


def _run_terminal_after_index(
    comments: tuple[dict, ...], agent: str, after_index: int
) -> bool:
    """True when the run that started at ``after_index`` has ended (success or failure)."""
    needle_fail = f"{RUN_FAILED_MARKER}{agent}"
    for i in range(after_index + 1, len(comments)):
        body = (comments[i].get("body") or "").lower()
        if needle_fail in body:
            return True
        if RUN_RESET_MARKER in body and (agent in body or f"{RUN_RESET_MARKER}all" in body):
            return True
        slug = agent.replace("-", " ")
        if "squad actions agent result" in body and slug in body:
            return True
        if "squad hf agent result" in body and slug in body:
            return True
        if agent in ("developer", "devops") and "build verification failed" in body:
            return True
    if agent == "developer":
        td = latest_trusted_developer_deliverable_index(comments)
        if td is not None and td > after_index:
            return True
    else:
        d_idx = _latest_deliverable_index(comments, agent)
        if d_idx is not None and d_idx > after_index:
            return True
    return False


def run_in_progress(comments: tuple[dict, ...]) -> str | None:
    """Return the agent whose latest in_progress marker has no terminal marker after it."""
    for i in range(len(comments) - 1, -1, -1):
        body = (comments[i].get("body") or "").lower()
        for agent in AGENTS_V2:
            if f"{RUN_IN_PROGRESS_MARKER}{agent}" not in body:
                continue
            if _run_terminal_after_index(comments, agent, i):
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


def squad_job_is_done(state: str, labels: frozenset[str] | set[str]) -> bool:
    """True when the issue belongs in the Done bucket / orchestrator should not run."""
    lc = current_lifecycle(labels)
    if lc == "released":
        return True
    if state.upper() == "CLOSED":
        return lc not in ACTIVE_SQUAD_LIFECYCLES
    return False


def squad_issue_needs_reopen(state: str, labels: frozenset[str] | set[str]) -> bool:
    return state.upper() == "CLOSED" and current_lifecycle(labels) in ACTIVE_SQUAD_LIFECYCLES


def next_action(
    view: IssueView,
    model_ladder: list[str] | None = None,
    forced_model: str | None = None,
) -> NextAction:
    if model_ladder is None:
        model_ladder = dev_model_ladder(os.environ.get("SQUAD_DEV_MODEL_LADDER"))
    if forced_model is None:
        forced_model = (os.environ.get("SQUAD_DEV_MODEL_INPUT") or "").strip() or None
    if squad_job_is_done(view.state, view.labels):
        return NextAction("done", reason="Issue closed" if view.state.upper() == "CLOSED" else "Released")
    if squad_issue_needs_reopen(view.state, view.labels):
        return NextAction("idle", reason="Issue closed while squad still active — reopen to continue")

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
        if not resolve_target_repo(view.body, view.comments):
            return NextAction(
                "failed",
                reason="Missing target repo URL in issue body or Director comment",
            )

        dev_idx = latest_trusted_developer_deliverable_index(view.comments)
        stale_deliverable = (
            dev_idx is None and _latest_deliverable_index(view.comments, "developer") is not None
        )
        if dev_idx is None:
            if run_failures(view.comments, "developer") >= MAX_RUN_ATTEMPTS:
                return NextAction(
                    "failed", agent="developer",
                    reason="Developer exceeded retry limit", needs_human=True,
                )
            reason = (
                "Prior developer deliverable invalid (missing PR or Actions run failed) — rework"
                if stale_deliverable
                else "Implement on target repo; post # Developer Deliverable"
            )
            return NextAction("dispatch", agent="developer", reason=reason)

        # Developer deliverable exists → QA gates it before release-candidate.
        qa_idx, verdict = latest_qa_verdict(view.comments)
        if (
            qa_idx is not None
            and qa_idx > dev_idx
            and verdict == "pass"
            and director_delivery_rejected_after(view.comments, qa_idx)
        ):
            return NextAction(
                "dispatch",
                agent="developer",
                reason="Director rejected delivery — developer and QA must rework",
            )
        if qa_idx is None or qa_idx < dev_idx:
            # Latest developer deliverable has not been QA-reviewed yet.
            if run_failures(view.comments, "qa") >= MAX_RUN_ATTEMPTS:
                return NextAction("failed", agent="qa", reason="QA agent failed to run")
            return NextAction(
                "dispatch", agent="qa", reason="QA review of the developer deliverable"
            )
        if verdict == "pass":
            target = resolve_target_repo(view.body, view.comments)
            repo = os.environ.get("GITHUB_REPOSITORY", "")
            if (
                target
                and repo
                and not _qa_pass_still_valid(
                    view.comments,
                    issue_body=view.body,
                    queue_repo=repo,
                    issue_number=view.number,
                    target_repo=target,
                )
            ):
                return NextAction(
                    "dispatch",
                    agent="developer",
                    reason="Stale QA pass — PR or build gate failed on re-check",
                )
            return NextAction(
                "idle", reason="QA passed — sync should add release-candidate"
            )
        # QA rejected the latest deliverable → Developer reworks (capped per model).
        if qa_fails_since_escalation(view.comments) >= MAX_QA_ROUNDS:
            cur = current_dev_model(view.comments, model_ladder)
            nxt = next_dev_model(view.comments, model_ladder)
            # A Director-chosen model (dashboard dropdown) is an explicit "try this
            # one" — it bypasses the cap and acts as the next rung.
            if forced_model and forced_model != cur:
                nxt = forced_model
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
                needs_human=True,
            )
        if run_failures(view.comments, "developer") >= MAX_RUN_ATTEMPTS:
            return NextAction(
                "failed", agent="developer",
                reason="Developer exceeded retry limit", needs_human=True,
            )
        return NextAction(
            "dispatch",
            agent="developer",
            reason="QA requested changes — rework the deliverable",
        )

    if lc == "release-candidate":
        return NextAction(
            "gate",
            reason="Director must accept or reject the dev+QA delivery",
        )

    return NextAction("idle", reason=f"Unhandled phase {lc}")


def is_squad_internal_comment(body: str) -> bool:
    """Comments that must not re-trigger phase watch (avoids feedback loops on #94).

    ``failed`` markers are *not* internal — phase watch must tick immediately so
    a dispatch error can retry without waiting for the 15m cron.
    """
    text = (body or "").lower()
    if (
        RUN_IN_PROGRESS_MARKER in text
        or RUN_RESET_MARKER in text
        or RUN_SETUP_FAILED_MARKER in text
        or RUN_MODEL_MARKER in text
    ):
        return True
    if QA_PASS_MARKER in text or QA_FAIL_MARKER in text:
        return True
    if DIRECTOR_DELIVERY_REJECT_MARKER in text or DIRECTOR_DELIVERY_ACCEPT_MARKER in text:
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
