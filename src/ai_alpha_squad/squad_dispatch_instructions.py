"""Unified developer/QA dispatch instructions for Squad v2 (Actions + orchestrator)."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from typing import Any

from ai_alpha_squad.compile_diagnostics import format_compile_fix_list
from ai_alpha_squad.squad_qa import format_qa_prechecks_section
from ai_alpha_squad.squad_v2 import (
    QA_FAIL_MARKER,
    QA_PASS_MARKER,
    developer_instruction_appendix,
    latest_qa_fail_excerpt,
    latest_qa_verdict,
)


_BLOCKER_FILE_RE = re.compile(
    r"\[(?:BLOCKER|REQUIRED|NICE)\]\s+([\w./-]+\.(?:java|kt|tsx?|jsx?|py|go|rs|gradle|xml))\b",
    re.IGNORECASE,
)


def _fetch_issue_comments(repo: str, issue: int) -> tuple[tuple[dict[str, Any], ...], str]:
    data = json.loads(
        subprocess.check_output(
            ["gh", "issue", "view", str(issue), "--repo", repo, "--json", "comments,body"],
            text=True,
        )
    )
    return tuple(data.get("comments") or []), data.get("body") or ""


def _first_blocker_path(qa_fail_body: str | None) -> str | None:
    if not qa_fail_body:
        return None
    m = _BLOCKER_FILE_RE.search(qa_fail_body)
    return m.group(1) if m else None


def _file_snippet_from_repo(target_repo: str, path: str, *, max_lines: int = 24) -> str:
    """Fetch a short file excerpt via GitHub API for first-edit bootstrap."""
    token = __import__("os").environ.get("GH_TOKEN") or __import__("os").environ.get("GITHUB_TOKEN") or ""
    if not token:
        return ""
    import base64
    import urllib.error
    import urllib.request

    url = f"https://api.github.com/repos/{target_repo}/contents/{path.lstrip('/')}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "ai-alpha-squad",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode())
    except (urllib.error.HTTPError, OSError, json.JSONDecodeError):
        return ""
    content = payload.get("content") if isinstance(payload, dict) else None
    if not content:
        return ""
    try:
        raw = base64.b64decode(content).decode("utf-8", errors="replace")
    except (ValueError, UnicodeDecodeError):
        return ""
    lines = raw.splitlines()
    if len(lines) <= max_lines:
        return raw
    return "\n".join(lines[:max_lines]) + f"\n… ({len(lines) - max_lines} more lines)"


def developer_dispatch_instructions(
    queue_repo: str,
    issue: int,
    target_repo: str,
    *,
    comments: tuple[dict[str, Any], ...] | None = None,
    issue_body: str = "",
) -> str:
    if comments is None:
        comments, issue_body = _fetch_issue_comments(queue_repo, issue)
    _, qa_verdict = latest_qa_verdict(comments)
    is_rework = qa_verdict == "fail"
    qa_excerpt = latest_qa_fail_excerpt(comments) if is_rework else None

    lines = [
        f"You are the Developer for AI Alpha Squad (v2 — single issue, no sub-issues).",
        "",
        f"Read .agents/agent-developer.md. Target repo: {target_repo}",
        "",
        f"Issue: https://github.com/{queue_repo}/issues/{issue}",
        "",
        "1. Use the repository layout in context; go to the file the task or QA fix list names — "
        "do NOT crawl with repeated list_dir/read_file before your first edit_file.",
    ]
    if is_rework:
        lines.extend(
            [
                "2. REWORK: QA already listed BLOCKER items — fix them one at a time with targeted edit_file.",
                "3. Run the build/compile command via run_command; finish is rejected if compile fails.",
            ]
        )
    else:
        lines.extend(
            [
                "2. Implement the success criteria on the target repo (branch + PR).",
                "3. Run build/compile via run_command before finish.",
            ]
        )
    lines.extend(
        [
            "4. Push to the stable branch; one PR per job (updates reuse the same PR).",
            "5. Use finish only when the tree compiles and required artifacts exist.",
            "6. Do not create sub-issues.",
            "",
            f"Agent profile: .agents/agent-developer.md",
        ]
    )

    appendix = developer_instruction_appendix(comments)
    if appendix.strip():
        lines.extend(["", appendix.strip()])

    bootstrap_path = _first_blocker_path(qa_excerpt)
    if bootstrap_path:
        snippet = _file_snippet_from_repo(target_repo, bootstrap_path)
        if snippet:
            lines.extend(
                [
                    "",
                    f"## First edit target (from QA BLOCKER): `{bootstrap_path}`",
                    "",
                    "```",
                    snippet,
                    "```",
                    "",
                    "Start with edit_file on this file — do not list_dir first.",
                ]
            )

    return "\n".join(lines)


def qa_dispatch_instructions(
    queue_repo: str,
    issue: int,
    target_repo: str,
    *,
    pr_diff: str = "",
    changed_files: tuple[str, ...] = (),
    base_tree: str = "",
    build_ok: bool = True,
    build_log: str = "",
    issue_body: str = "",
) -> str:
    from ai_alpha_squad.squad_qa import artifact_paths_in_changed

    artifacts = artifact_paths_in_changed(changed_files)
    prechecks = format_qa_prechecks_section(
        build_ok=build_ok,
        build_log_excerpt=build_log if not build_ok else "",
        changed_files=changed_files,
        artifact_paths_in_pr=artifacts,
    )

    changed_list = "\n".join(changed_files) if changed_files else "(no open PR / no files changed — treat as not delivered)"
    diff_block = pr_diff if pr_diff.strip() else "(no open PR diff found — treat as not delivered)"

    return f"""You are the QA engineer for AI Alpha Squad (v2). Read .agents/agent-qa.md.

Issue: https://github.com/{queue_repo}/issues/{issue}
Target repo: {target_repo}

Evaluate whether the Developer's deliverable satisfies EVERY success criterion in
the issue above (the criteria are in the issue body).

{prechecks}

## Files changed in this PR ({len(changed_files)})
{changed_list}

## Files in the repository base branch (for completeness checks)
{base_tree or "(unavailable)"}

Use the lists above to judge **completeness**. Then review the actual changes:

```diff
{diff_block}
```

Be a strict but OBJECTIVE reviewer. The Developer is a code model that acts best on a
short, concrete fix-list — not prose. Keep the report tight.

Post ONE comment on THIS issue (#{issue}) with heading: # QA Report
- "## Criteria" — one line per success criterion: `✅` or `❌ <≤12-word reason>`.
  For any count/coverage criterion, give numbers (e.g. "47/54 files changed").
  Do NOT write paragraphs, code blocks, or restate the criteria text.
- "## Fixes required" — ONLY if failing. A prioritized, numbered list the Developer
  can act on directly. Each item EXACTLY: `[BLOCKER|REQUIRED|NICE] <file path> — <the
  concrete change to make>`. Order BLOCKER first, then REQUIRED, then NICE.
- End with EXACTLY one verdict line, nothing after it:
  - `{QA_PASS_MARKER}` — if every criterion is met.
  - `{QA_FAIL_MARKER}` — otherwise.
Do not open PRs or sub-issues; review only.
"""


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) < 4:
        print(
            "usage: squad_dispatch_instructions developer|qa <queue_repo> <issue> <target_repo>",
            file=sys.stderr,
        )
        return 2
    agent, repo, issue_s, target = argv[0], argv[1], int(argv[2]), argv[3]
    if agent == "developer":
        print(developer_dispatch_instructions(repo, issue_s, target))
        return 0
    if agent == "qa":
        # Optional JSON context on stdin: pr_diff, changed_files, base_tree, build_ok, build_log, issue_body
        ctx: dict[str, Any] = {}
        if not sys.stdin.isatty():
            try:
                ctx = json.loads(sys.stdin.read() or "{}")
            except json.JSONDecodeError:
                ctx = {}
        print(
            qa_dispatch_instructions(
                repo,
                issue_s,
                target,
                pr_diff=str(ctx.get("pr_diff") or ""),
                changed_files=tuple(ctx.get("changed_files") or ()),
                base_tree=str(ctx.get("base_tree") or ""),
                build_ok=bool(ctx.get("build_ok", True)),
                build_log=str(ctx.get("build_log") or ""),
                issue_body=str(ctx.get("issue_body") or ""),
            )
        )
        return 0
    print(f"unknown agent: {agent}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
