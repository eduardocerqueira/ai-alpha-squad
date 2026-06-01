"""Dispatch squad work via Hugging Face Inference Providers (OpenAI-compatible chat API)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

from ai_alpha_squad.agent_models import model_summary, resolve_dispatch_mode, resolve_model
from ai_alpha_squad.comments import (
    format_hf_dispatch_comment,
    format_hf_result_comment,
    format_orchestrator_notice,
)

HF_ROUTER_URL = os.environ.get(
    "SQUAD_HF_ROUTER_URL",
    "https://router.huggingface.co/v1/chat/completions",
)
MAX_ISSUE_CHARS = int(os.environ.get("SQUAD_HF_MAX_ISSUE_CHARS", "12000"))
MAX_OUTPUT_TOKENS = int(os.environ.get("SQUAD_HF_MAX_OUTPUT_TOKENS", "4096"))


def hf_run_enabled() -> bool:
    """When false, only post dispatch comment (manual or external runner)."""
    return os.environ.get("SQUAD_HF_RUN_IN_CI", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def _gh_json(args: list[str]) -> dict:
    proc = subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout)


def parse_parent_issue_number(issue_body: str) -> int | None:
    """Extract parent issue number from sub-issue body (e.g. Parent Issue | #64)."""
    import re

    for pattern in (
        r"Parent\s+Issue\s*\|\s*#(\d+)",
        r"Parent\s+issue:\s*#(\d+)",
        r"issues/(\d+)",
    ):
        match = re.search(pattern, issue_body or "", re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def fetch_issue_context(repo: str, issue: int) -> str:
    data = _gh_json(
        [
            "issue",
            "view",
            str(issue),
            "--repo",
            repo,
            "--json",
            "title,body,comments",
        ]
    )
    parts = [f"# {data.get('title', '')}", (data.get("body") or "").strip()]
    for comment in data.get("comments") or []:
        author = (comment.get("author") or {}).get("login", "unknown")
        body = (comment.get("body") or "").strip()
        if body:
            parts.append(f"\n---\n**Comment by @{author}:**\n{body}")
    text = "\n\n".join(p for p in parts if p)
    if len(text) > MAX_ISSUE_CHARS:
        text = text[:MAX_ISSUE_CHARS] + "\n\n…(truncated for HF context limit)"
    return text


def fetch_issue_context_with_parent(repo: str, issue: int) -> str:
    """Issue thread plus parent issue body/comments when this is a sub-issue."""
    data = _gh_json(
        [
            "issue",
            "view",
            str(issue),
            "--repo",
            repo,
            "--json",
            "title,body,comments",
        ]
    )
    parent = parse_parent_issue_number(data.get("body") or "")
    parts = [fetch_issue_context(repo, issue)]
    if parent and parent != issue:
        parts.append(
            f"\n\n---\n\n# Parent issue #{parent} (Technical Specification + BA)\n\n"
            f"{fetch_issue_context(repo, parent)}"
        )
    return "\n".join(parts)


def chat_completion(
    model: str,
    *,
    system: str,
    user: str,
    token: str,
) -> str:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": MAX_OUTPUT_TOKENS,
    }
    req = urllib.request.Request(
        HF_ROUTER_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HF inference HTTP {exc.code}: {detail[:2000]}") from exc

    choices = body.get("choices") or []
    if not choices:
        raise RuntimeError(f"HF inference returned no choices: {json.dumps(body)[:500]}")
    message = choices[0].get("message") or {}
    content = (message.get("content") or "").strip()
    if not content:
        raise RuntimeError("HF inference returned empty content")
    return content


def post_issue_comment(repo: str, issue: int, body: str) -> None:
    proc = subprocess.run(
        ["gh", "issue", "comment", str(issue), "--repo", repo, "--body", body],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or "gh issue comment failed")


def dispatch(
    repo: str,
    issue: int,
    agent: str,
    instructions: str,
    *,
    label: str = "",
) -> bool:
    """
    Post HF dispatch marker and optionally run inference in CI.

    Returns True when dispatched (comment posted or inference completed).
    """
    if resolve_dispatch_mode(agent) != "hf":
        raise RuntimeError(f"hf_dispatch called but dispatch mode for {agent!r} is not hf")

    model = resolve_model(agent, "huggingface")
    summary = model_summary(agent, "huggingface")
    dispatch_body = format_hf_dispatch_comment(
        agent,
        label or agent,
        model_summary=summary,
        run_in_ci=hf_run_enabled(),
    )
    post_issue_comment(repo, issue, dispatch_body)

    if not hf_run_enabled():
        return True

    token = os.environ.get("HF_TOKEN", "").strip()
    if not token:
        raise RuntimeError("HF_TOKEN is required when SQUAD_HF_RUN_IN_CI=1")

    issue_context = fetch_issue_context(repo, issue)
    user_prompt = (
        f"## GitHub issue context\n\n{issue_context}\n\n"
        "## Your task\n\n"
        f"{instructions.strip()}\n\n"
        "Respond with the full deliverable in markdown. "
        "Use the required headings from the task (e.g. `# Business Analysis`, `# QA Report`)."
    )
    content = chat_completion(
        model,
        system=(
            f"You are the AI Alpha Squad `{agent}` agent. "
            "Follow instructions exactly. Output only the deliverable markdown."
        ),
        user=user_prompt,
        token=token,
    )
    result_body = format_hf_result_comment(agent, content, model=model)
    post_issue_comment(repo, issue, result_body)

    if agent == "architect" and os.environ.get("SQUAD_HF_ARCHITECT_SUBISSUES", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    ):
        from ai_alpha_squad.architect_subissues import ensure_architect_subissues

        created = ensure_architect_subissues(repo, issue)
        if created:
            roles = ", ".join(f"`{role}` #{num}" for role, num in sorted(created.items()))
            post_issue_comment(
                repo,
                issue,
                format_orchestrator_notice(
                    f"**Squad orchestrator:** Architect sub-issues created — {roles}."
                ),
            )

    return True


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) < 4:
        print(
            "Usage: python -m ai_alpha_squad.hf_dispatch <repo> <issue> <agent> <instructions_file>",
            file=sys.stderr,
        )
        return 2

    repo, issue_s, agent = argv[0], argv[1], argv[2]
    instructions_path = Path(argv[3])
    label = os.environ.get("DISPATCH_LABEL", agent)

    instructions = instructions_path.read_text(encoding="utf-8")
    try:
        dispatch(repo, int(issue_s), agent, instructions, label=label)
    except Exception as exc:
        print(f"HF dispatch failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
