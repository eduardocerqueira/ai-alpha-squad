"""Squad coding agent: HF model + tool loop on a checked-out target repo (GitHub Actions)."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

from ai_alpha_squad.agent_models import (
    ACTIONS_DISPATCH_MARKER,
    ACTIONS_RESULT_MARKER,
    model_summary,
    resolve_model,
)
from ai_alpha_squad.comments import format_squad_comment
from ai_alpha_squad.hf_dispatch import chat_completion, fetch_issue_context, post_issue_comment

MAX_TURNS = int(os.environ.get("SQUAD_ACTIONS_MAX_TURNS", "30"))
COMMAND_TIMEOUT = int(os.environ.get("SQUAD_ACTIONS_CMD_TIMEOUT", "300"))

_TOOL_JSON_RE = re.compile(
    r"\{[^{}]*\"tool\"\s*:\s*\"[^\"]+\"[^{}]*\}",
    re.DOTALL,
)

_ALLOWED_CMD_PREFIXES = (
    "npm ",
    "pnpm ",
    "yarn ",
    "npx ",
    "node ",
    "python ",
    "python3 ",
    "uv ",
    "make ",
    "cargo ",
    "go ",
    "git status",
    "git diff",
    "git add",
    "git commit",
    "./",
)


def _normalize_workdir(workdir: Path) -> Path:
    return workdir.resolve()


def _safe_path(workdir: Path, rel: str) -> Path:
    workdir = _normalize_workdir(workdir)
    target = (workdir / rel.lstrip("/")).resolve()
    if not str(target).startswith(str(workdir)):
        raise ValueError(f"Path escapes workdir: {rel!r}")
    return target


def _run_command(workdir: Path, command: str) -> str:
    cmd = command.strip()
    if not cmd:
        return "error: empty command"
    lowered = cmd.lower()
    if any(x in lowered for x in ("|", "&&", ";", "`", "$(", "rm -rf", "> /", "sudo ")):
        return "error: command not allowed"
    if not any(lowered.startswith(p) for p in _ALLOWED_CMD_PREFIXES):
        return f"error: command prefix not allowed (allowed: {', '.join(_ALLOWED_CMD_PREFIXES[:8])}…)"

    proc = subprocess.run(
        cmd,
        shell=True,
        cwd=workdir,
        capture_output=True,
        text=True,
        timeout=COMMAND_TIMEOUT,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    if len(out) > 12000:
        out = out[:12000] + "\n…(truncated)"
    return f"exit={proc.returncode}\n{out}"


def execute_tool(workdir: Path, name: str, args: dict) -> str:
    try:
        if name == "read_file":
            path = _safe_path(workdir, str(args.get("path", "")))
            if not path.is_file():
                return f"error: not a file: {path}"
            text = path.read_text(encoding="utf-8", errors="replace")
            if len(text) > 16000:
                text = text[:16000] + "\n…(truncated)"
            return text
        if name == "write_file":
            path = _safe_path(workdir, str(args.get("path", "")))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(str(args.get("content", "")), encoding="utf-8")
            return f"ok: wrote {path.relative_to(workdir)} ({path.stat().st_size} bytes)"
        if name == "list_dir":
            path = _safe_path(workdir, str(args.get("path", ".")))
            if not path.is_dir():
                return f"error: not a directory: {path}"
            entries = sorted(path.iterdir(), key=lambda p: p.name)[:200]
            lines = [
                f"{'[dir]' if e.is_dir() else '[file]'} {e.name}" for e in entries
            ]
            return "\n".join(lines) or "(empty)"
        if name == "run_command":
            return _run_command(workdir, str(args.get("command", "")))
        if name == "finish":
            return json.dumps({"status": "finish", "summary": args.get("summary", "")})
    except Exception as exc:
        return f"error: {exc}"
    return f"error: unknown tool {name!r}"


def parse_tool_call(content: str) -> tuple[str, dict] | None:
    content = content.strip()
    for candidate in (content,):
        match = _TOOL_JSON_RE.search(candidate)
        if match:
            try:
                data = json.loads(match.group(0))
                if isinstance(data, dict) and "tool" in data:
                    return str(data["tool"]), dict(data.get("args") or {})
            except json.JSONDecodeError:
                pass
    try:
        data = json.loads(content)
        if isinstance(data, dict) and "tool" in data:
            return str(data["tool"]), dict(data.get("args") or {})
    except json.JSONDecodeError:
        return None
    return None


def format_actions_dispatch_comment(agent: str, label: str, *, repo: str, target_repo: str) -> str:
    from ai_alpha_squad.comments import agent_icon_img, normalize_agent_slug

    agent_slug = normalize_agent_slug(agent)
    icon = agent_icon_img(agent_slug, repo=repo)
    summary = model_summary(agent_slug)
    message = (
        f"**Squad orchestrator** — {ACTIONS_DISPATCH_MARKER}\n\n"
        f"Runtime: **GitHub Actions** · Agent {icon} `{agent_slug}` · label `{label}`\n\n"
        f"Target repo: `{target_repo}` · Model: {summary}\n\n"
        "Running coding agent loop in this workflow."
    )
    return format_squad_comment(message, avatar="orchestrator", repo=repo)


def format_actions_result_comment(
    agent: str,
    summary: str,
    *,
    repo: str,
    pr_url: str = "",
    model: str = "",
) -> str:
    from ai_alpha_squad.comments import agent_icon_img, normalize_agent_slug

    agent_slug = normalize_agent_slug(agent)
    icon = agent_icon_img(agent_slug, repo=repo)
    model_line = f" · model `{model}`" if model else ""
    pr_line = f"\n\n**Pull request:** {pr_url}" if pr_url else ""
    body = f"**{ACTIONS_RESULT_MARKER}** — {icon} `{agent_slug}`{model_line}\n\n{summary.strip()}{pr_line}"
    return format_squad_comment(body, avatar=agent_slug, repo=repo)


def run_agent_loop(
    workdir: Path,
    *,
    agent: str,
    instructions: str,
    issue_context: str,
    token: str,
) -> tuple[str, bool]:
    """Returns (summary, finished_via_finish_tool)."""
    model = resolve_model(agent, "huggingface")
    system = f"""You are the AI Alpha Squad `{agent}` agent running in GitHub Actions on a cloned repository.
Work only inside the repository root. Implement the task using tools.

Respond with a single JSON object per message (no markdown fences):
{{"tool": "<name>", "args": {{...}}}}

Tools:
- read_file: {{"path": "relative/path"}}
- write_file: {{"path": "relative/path", "content": "..."}}
- list_dir: {{"path": "."}}
- run_command: {{"command": "npm test"}}  (allowlisted prefixes only)
- finish: {{"summary": "what you did", "commit_message": "optional"}}

When implementation is complete and tests pass (or you documented blockers), call finish.
Output only the JSON object."""

    user = (
        f"## GitHub issue context\n\n{issue_context}\n\n"
        f"## Task\n\n{instructions.strip()}\n\n"
        "Repository root is the current working directory for tools."
    )

    conversation = user
    for _turn in range(MAX_TURNS):
        content = chat_completion(
            model,
            system=system,
            user=conversation,
            token=token,
        )
        parsed = parse_tool_call(content)
        if not parsed:
            conversation = (
                f"{user}\n\n---\nModel response (unparsed):\n{content[:2000]}\n\n"
                "Reply with a single JSON tool object."
            )
            continue
        tool_name, tool_args = parsed
        if tool_name == "finish":
            return str(tool_args.get("summary", content)), True
        result = execute_tool(workdir, tool_name, tool_args)
        conversation = (
            f"{user}\n\n---\nLast tool: {tool_name}\nResult:\n{result}\n\n"
            "Next: one JSON tool object."
        )

    return "Agent loop reached max turns without finish.", False


def post_dispatch(
    queue_repo: str,
    issue: int,
    agent: str,
    *,
    target_repo: str,
    label: str = "",
) -> None:
    label = label or agent
    dispatch_body = format_actions_dispatch_comment(
        agent, label, repo=queue_repo, target_repo=target_repo
    )
    post_issue_comment(queue_repo, issue, dispatch_body)


def run_coding_loop(
    queue_repo: str,
    issue: int,
    agent: str,
    instructions: str,
    *,
    workdir: Path,
) -> str:
    token = os.environ.get("HF_TOKEN", "").strip()
    if not token:
        raise RuntimeError("HF_TOKEN is required for Squad Actions agent")
    issue_context = fetch_issue_context(queue_repo, issue)
    summary, _finished = run_agent_loop(
        workdir,
        agent=agent,
        instructions=instructions,
        issue_context=issue_context,
        token=token,
    )
    return summary


def post_result(
    queue_repo: str,
    issue: int,
    agent: str,
    summary: str,
    *,
    pr_url: str = "",
) -> None:
    model = resolve_model(agent, "huggingface")
    result_body = format_actions_result_comment(
        agent, summary, repo=queue_repo, pr_url=pr_url, model=model
    )
    post_issue_comment(queue_repo, issue, result_body)


def dispatch(
    queue_repo: str,
    issue: int,
    agent: str,
    instructions: str,
    *,
    target_repo: str,
    workdir: Path,
    label: str = "",
    pr_url: str = "",
) -> bool:
    post_dispatch(queue_repo, issue, agent, target_repo=target_repo, label=label)
    summary = run_coding_loop(queue_repo, issue, agent, instructions, workdir=workdir)
    post_result(queue_repo, issue, agent, summary, pr_url=pr_url)
    return True


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) < 2:
        print(
            "Usage:\n"
            "  python -m ai_alpha_squad.actions_agent run "
            "<queue_repo> <issue> <agent> <target_repo> <workdir> <instructions_file>\n"
            "  python -m ai_alpha_squad.actions_agent finalize "
            "<queue_repo> <issue> <agent> <summary_file> [pr_url]",
            file=sys.stderr,
        )
        return 2

    try:
        if argv[0] == "run":
            queue_repo, issue_s, agent, target_repo, workdir_s, instructions_path_s = argv[1:7]
            label = os.environ.get("DISPATCH_LABEL", agent)
            instructions = Path(instructions_path_s).read_text(encoding="utf-8")
            post_dispatch(
                queue_repo,
                int(issue_s),
                agent,
                target_repo=target_repo,
                label=label,
            )
            summary = run_coding_loop(
                queue_repo,
                int(issue_s),
                agent,
                instructions,
                workdir=Path(workdir_s),
            )
            summary_file = os.environ.get(
                "SQUAD_ACTIONS_SUMMARY_FILE", "/tmp/squad-actions-summary.txt"
            )
            Path(summary_file).write_text(summary, encoding="utf-8")
        elif argv[0] == "finalize":
            queue_repo, issue_s, agent = argv[1], argv[2], argv[3]
            summary_path = Path(argv[4])
            pr_url = argv[5] if len(argv) > 5 else os.environ.get("SQUAD_ACTIONS_PR_URL", "")
            summary = summary_path.read_text(encoding="utf-8")
            post_result(queue_repo, int(issue_s), agent, summary, pr_url=pr_url)
        elif len(argv) >= 6:
            queue_repo, issue_s, agent, target_repo, workdir_s, instructions_path_s = argv[:6]
            instructions = Path(instructions_path_s).read_text(encoding="utf-8")
            label = os.environ.get("DISPATCH_LABEL", agent)
            pr_url = os.environ.get("SQUAD_ACTIONS_PR_URL", "")
            dispatch(
                queue_repo,
                int(issue_s),
                agent,
                instructions,
                target_repo=target_repo,
                workdir=Path(workdir_s),
                label=label,
                pr_url=pr_url,
            )
        else:
            raise ValueError("unknown command or insufficient arguments")
    except Exception as exc:
        print(f"Actions agent failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
