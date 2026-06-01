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
from ai_alpha_squad.comments import format_squad_comment, format_v2_developer_deliverable
from ai_alpha_squad.actions_scaffold import (
    apply_vscode_squad_director_scaffold,
    is_greenfield_repo,
)
from ai_alpha_squad.hf_dispatch import (
    chat_completion,
    fetch_issue_context_with_parent,
    post_issue_comment,
)

MAX_TURNS = int(os.environ.get("SQUAD_ACTIONS_MAX_TURNS", "50"))
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


def _extract_json_object(text: str, start: int) -> str | None:
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def parse_tool_call(content: str) -> tuple[str, dict] | None:
    content = content.strip()
    fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", content, re.IGNORECASE)
    if fenced:
        content = fenced.group(1).strip()
    candidates = [content]
    if fenced:
        candidates.append(content)
    idx = 0
    while True:
        start = content.find("{", idx)
        if start < 0:
            break
        blob = _extract_json_object(content, start)
        if blob:
            candidates.append(blob)
        idx = start + 1
    for candidate in candidates:
        match = _TOOL_JSON_RE.search(candidate)
        if match:
            try:
                data = json.loads(match.group(0))
                if isinstance(data, dict) and "tool" in data:
                    return str(data["tool"]), dict(data.get("args") or {})
            except json.JSONDecodeError:
                pass
        try:
            data = json.loads(candidate)
            if isinstance(data, dict) and "tool" in data:
                return str(data["tool"]), dict(data.get("args") or {})
        except json.JSONDecodeError:
            continue
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
    v2 = os.environ.get("SQUAD_V2", "").strip() in ("1", "true", "yes")
    task_hint = (
        "Follow the Task section and parent issue context exactly (v2 — no default VS Code scaffold)."
        if v2
        else "The repo may be greenfield (only README.md). Scaffold a minimal VS Code extension per the parent issue Technical Specification: package.json, tsconfig.json, src/extension.ts, .vscodeignore, README updates."
    )
    system = f"""You are the AI Alpha Squad `{agent}` agent running in GitHub Actions on a cloned repository.
Work only inside the repository root. Implement the task using tools.

{task_hint}

Respond with ONE JSON object per message — no markdown fences, no extra text:
{{"tool": "<name>", "args": {{...}}}}

Tools:
- read_file: {{"path": "relative/path"}}
- write_file: {{"path": "relative/path", "content": "..."}}
- list_dir: {{"path": "."}}
- run_command: {{"command": "npm install"}}  (allowlisted: npm, pnpm, yarn, npx, node, python, make, cargo, go, git status/diff/add/commit)
- finish: {{"summary": "what you did"}}

Use list_dir once at the start, then prefer write_file for each artifact.
If the task lists multiple languages, create every language, then call finish immediately.
The "Progress so far" list below shows the tools you have ALREADY run this session —
do not repeat completed work, and once every required artifact exists call finish.
Do not repeat list_dir on the same path. Output only the JSON object."""

    user = (
        f"## GitHub issue context\n\n{issue_context}\n\n"
        f"## Task\n\n{instructions.strip()}\n\n"
        "Repository root is the current working directory for tools."
    )

    # Running transcript of completed actions. The model is otherwise stateless
    # per call, so without this it cannot track which artifacts it already wrote
    # and never confidently calls finish (it churns until max turns).
    history: list[str] = []

    def build_conversation(extra: str = "") -> str:
        parts = [user]
        if history:
            parts.append("## Progress so far (tools you already ran this session)\n" + "\n".join(history))
        parts.append("Next: reply with ONE JSON tool object." + extra)
        return "\n\n---\n".join(parts)

    for _turn in range(MAX_TURNS):
        remaining = MAX_TURNS - _turn
        urgency = ""
        if remaining <= 15:
            urgency = (
                "\n\nURGENT: " + str(remaining) + " turn(s) left. Call "
                '{"tool": "finish", "args": {"summary": "..."}} now with what you completed.'
            )
        content = chat_completion(
            model,
            system=system,
            user=build_conversation(urgency),
            token=token,
        )
        parsed = parse_tool_call(content)
        if not parsed:
            print(
                f"[actions] turn {_turn + 1}/{MAX_TURNS}: unparsed ({len(content)} chars)",
                file=sys.stderr,
            )
            history.append(f"[turn {_turn + 1}] (model output was not valid JSON; reminded to emit a tool object)")
            continue
        tool_name, tool_args = parsed
        print(f"[actions] turn {_turn + 1}/{MAX_TURNS}: {tool_name}", file=sys.stderr)
        if tool_name == "finish":
            return str(tool_args.get("summary", content)), True
        result = execute_tool(workdir, tool_name, tool_args)
        arg_hint = str(tool_args.get("path") or tool_args.get("command") or "").strip()
        result_brief = result if len(result) <= 400 else result[:400] + "…(truncated)"
        history.append(
            f"[turn {_turn + 1}] {tool_name} {arg_hint}".rstrip() + f" -> {result_brief}"
        )
        # Bound transcript size; a 10-artifact task stays well under this.
        while len(history) > 1 and sum(len(h) for h in history) > 12000:
            history.pop(0)

    return "Agent loop reached max turns without finish.", False


def _v2_enabled() -> bool:
    return os.environ.get("SQUAD_V2", "").strip() in ("1", "true", "yes")


def post_dispatch(
    queue_repo: str,
    issue: int,
    agent: str,
    *,
    target_repo: str,
    label: str = "",
) -> None:
    if _v2_enabled() or os.environ.get("SQUAD_ACTIONS_SKIP_DISPATCH_COMMENT", "").strip() in (
        "1",
        "true",
        "yes",
    ):
        return
    label = label or agent
    dispatch_body = format_actions_dispatch_comment(
        agent, label, repo=queue_repo, target_repo=target_repo
    )
    post_issue_comment(queue_repo, issue, dispatch_body)


def _scaffold_greenfield_enabled() -> bool:
    return os.environ.get("SQUAD_ACTIONS_SCAFFOLD_GREENFIELD", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def run_coding_loop(
    queue_repo: str,
    issue: int,
    agent: str,
    instructions: str,
    *,
    workdir: Path,
) -> str:
    strategy = os.environ.get("SQUAD_ACTIONS_STRATEGY", "scaffold").strip().lower()
    scaffold_summary = ""

    if _scaffold_greenfield_enabled() and is_greenfield_repo(workdir):
        paths = apply_vscode_squad_director_scaffold(workdir)
        scaffold_summary = (
            f"Applied deterministic greenfield scaffold ({len(paths)} paths) "
            "for Squad Director v1 (Job 1)."
        )
        print(f"[actions] {scaffold_summary}", file=sys.stderr)
        if strategy == "scaffold":
            return scaffold_summary

    token = os.environ.get("HF_TOKEN", "").strip()
    if not token:
        raise RuntimeError("HF_TOKEN is required for Squad Actions agent")
    issue_context = fetch_issue_context_with_parent(queue_repo, issue)
    summary, finished = run_agent_loop(
        workdir,
        agent=agent,
        instructions=instructions,
        issue_context=issue_context,
        token=token,
    )
    if scaffold_summary and finished:
        return f"{scaffold_summary}\n\n{summary}"
    if scaffold_summary and not finished:
        return (
            f"{scaffold_summary}\n\nLLM loop did not finish ({summary}); "
            "scaffold files are still eligible for PR."
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
    if _v2_enabled() and agent == "developer" and pr_url:
        result_body = format_v2_developer_deliverable(
            summary, pr_url=pr_url, repo=queue_repo, model=model
        )
    else:
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
