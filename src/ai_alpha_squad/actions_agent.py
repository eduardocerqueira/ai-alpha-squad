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
    HFCreditsDepletedError,
    chat_completion,
    fetch_issue_context_with_parent,
    post_issue_comment,
)
from ai_alpha_squad.target_build_verify import should_verify_build, verify_workdir

MAX_TURNS = int(os.environ.get("SQUAD_ACTIONS_MAX_TURNS", "50"))
COMMAND_TIMEOUT = int(os.environ.get("SQUAD_ACTIONS_CMD_TIMEOUT", "300"))
# Early-abort thresholds: a model that ignores the tool protocol or never edits
# anything should fail fast (and let the orchestrator escalate / the Director pick
# another model) instead of grinding all the way to MAX_TURNS.
MAX_CONSECUTIVE_UNPARSED = int(os.environ.get("SQUAD_ACTIONS_MAX_UNPARSED", "8"))
MAX_TURNS_NO_PROGRESS = int(os.environ.get("SQUAD_ACTIONS_MAX_STALL", "60"))
# Abort when the model reads/searches without ever editing (e.g. 20+ read_file turns).
MAX_READ_ONLY_CHURN = int(os.environ.get("SQUAD_ACTIONS_MAX_READ_CHURN", "14"))

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
    "mvn ",
    "mvnw ",
    "gradle ",
    "gradlew ",
    "pytest ",
    "pip ",
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
        if name == "edit_file":
            # Targeted find/replace for EXISTING files — avoids the destructive
            # full-file rewrite that weaker models do with write_file.
            path = _safe_path(workdir, str(args.get("path", "")))
            if not path.is_file():
                return f"error: not a file: {path} (use write_file to create new files)"
            old = str(args.get("old_string", ""))
            new = str(args.get("new_string", ""))
            replace_all = bool(args.get("replace_all"))
            if not old:
                return "error: edit_file requires a non-empty old_string"
            text = path.read_text(encoding="utf-8", errors="replace")
            count = text.count(old)
            if count == 0:
                return "error: old_string not found — read_file first and copy the exact text"
            if count > 1 and not replace_all:
                # The duplicate-line case (e.g. a field declared 3×) trips here:
                # spell out the ways to resolve it so a weaker model doesn't stall.
                return (
                    f"error: old_string matches {count} places. To target ONE, add "
                    "surrounding context so it is unique. To REMOVE duplicates, set "
                    "old_string to the whole block containing all the copies and "
                    "new_string to the single intended version. To change EVERY "
                    'occurrence, pass "replace_all": true.'
                )
            if replace_all:
                path.write_text(text.replace(old, new), encoding="utf-8")
                return f"ok: edited {path.relative_to(workdir)} ({count} replacements)"
            path.write_text(text.replace(old, new, 1), encoding="utf-8")
            return f"ok: edited {path.relative_to(workdir)} (1 replacement)"
        if name == "list_dir":
            path = _safe_path(workdir, str(args.get("path", ".")))
            if not path.is_dir():
                return f"error: not a directory: {path}"
            entries = sorted(path.iterdir(), key=lambda p: p.name)[:200]
            lines = [
                f"{'[dir]' if e.is_dir() else '[file]'} {e.name}" for e in entries
            ]
            return "\n".join(lines) or "(empty)"
        if name == "search":
            query = str(args.get("query", "")).strip()
            if not query:
                return "error: search requires a non-empty 'query'"
            rel = str(args.get("path", ".") or ".")
            base = _safe_path(workdir, rel)
            proc = subprocess.run(
                ["grep", "-rIn", "--exclude-dir=.git", "-F", "-e", query, str(base)],
                capture_output=True, text=True, timeout=COMMAND_TIMEOUT,
            )
            wd = str(_normalize_workdir(workdir))
            lines = []
            for line in proc.stdout.splitlines()[:60]:
                lines.append(line[len(wd) + 1:] if line.startswith(wd + "/") else line)
            out = "\n".join(lines)
            if len(out) > 4000:
                out = out[:4000] + "\n…(truncated; refine the query)"
            return out or "(no matches)"
        if name == "run_command":
            return _run_command(workdir, str(args.get("command", "")))
        if name == "finish":
            return json.dumps({"status": "finish", "summary": args.get("summary", "")})
    except Exception as exc:
        return f"error: {exc}"
    return f"error: unknown tool {name!r}"


_DEF_RE = re.compile(r"^[+-](?:async\s+)?(?:def|class)\s+([A-Za-z_]\w*)")


def diff_file_stats(diff_text: str) -> dict[str, dict]:
    """Per-file line/def deltas from a unified git diff (``git diff HEAD``).

    Returns ``{path: {added, removed, added_defs, removed_defs}}``. ``*_defs`` are
    top-level Python ``def``/``class`` names (column 0 after the +/- marker).
    """
    stats: dict[str, dict] = {}
    cur: str | None = None
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            match = re.search(r" b/(.+)$", line)
            cur = match.group(1) if match else None
            if cur:
                stats[cur] = {"added": 0, "removed": 0, "added_defs": set(), "removed_defs": set()}
            continue
        if cur is None or line[:3] in ("+++", "---") or line.startswith("@@"):
            continue
        if line.startswith("+"):
            stats[cur]["added"] += 1
            dm = _DEF_RE.match(line)
            if dm:
                stats[cur]["added_defs"].add(dm.group(1))
        elif line.startswith("-"):
            stats[cur]["removed"] += 1
            dm = _DEF_RE.match(line)
            if dm:
                stats[cur]["removed_defs"].add(dm.group(1))
    return stats


def assess_change_safety(diff_text: str) -> list[str]:
    """Flag suspiciously destructive edits (the kind where the model rewrites a
    file and drops existing code). Returns human-readable violation strings.

    New (untracked) files don't appear in ``git diff HEAD``, so greenfield work
    that only adds files is never flagged.
    """
    violations: list[str] = []
    for path, s in diff_file_stats(diff_text).items():
        lost_defs = s["removed_defs"] - s["added_defs"]
        if lost_defs:
            violations.append(
                f"{path}: removes top-level definitions without re-adding them: "
                + ", ".join(sorted(lost_defs))
            )
        if s["removed"] >= 30 and s["removed"] >= 3 * max(s["added"], 1):
            violations.append(
                f"{path}: deletes {s['removed']} lines but adds only {s['added']} — "
                "looks like a file rewrite/truncation, not a targeted change"
            )
    return violations


_ENUM_FILE_RE = re.compile(r"^\s*\d+\.\s")
_BACKTICK_FILE_RE = re.compile(r"`[^`]+\.[A-Za-z0-9]{1,8}`")


def expected_artifact_files(text: str) -> list[str]:
    """Filenames the task explicitly enumerates (e.g. "1. C# — `hello.cs`" …).

    Returns the first backticked filename on each enumerated line. Empty unless
    there's a clear multi-file list (>= 3 such items), so single-file or
    non-creation tasks aren't constrained. Checking these specific files exist is
    robust across runs — an idempotent continue on a branch that already has some
    of them is measured correctly (unlike counting this run's writes).
    """
    names: list[str] = []
    for line in (text or "").splitlines():
        if not _ENUM_FILE_RE.match(line):
            continue
        m = _BACKTICK_FILE_RE.search(line)
        if m:
            names.append(m.group(0).strip("`"))
    seen: set[str] = set()
    ordered = [n for n in names if not (n in seen or seen.add(n))]
    return ordered if len(ordered) >= 3 else []


def expected_artifact_count(text: str) -> int | None:
    """Count of enumerated files (None when not a clear multi-file task)."""
    files = expected_artifact_files(text)
    return len(files) if files else None


def _repo_basenames(workdir: Path) -> set[str]:
    """Basenames of files currently in the working tree (tracked + untracked).

    Used so the completeness guard recognises a file referenced by a bare name or a
    wrong/guessed path (e.g. the issue 'pointers' or BA plan say `BuildMonitorView.java`
    or `src/main/java/.../index.jelly` while the real file lives elsewhere). Matching
    by basename keeps the guard from demanding the 'creation' of files that already
    exist under a different path (#140), while still enforcing genuinely new files.
    """
    import os

    names: set[str] = set()
    try:
        for args in (["git", "ls-files"], ["git", "ls-files", "--others", "--exclude-standard"]):
            proc = subprocess.run(args, cwd=str(workdir), capture_output=True, text=True)
            if proc.returncode == 0:
                names.update(os.path.basename(f) for f in proc.stdout.splitlines() if f)
    except Exception:
        pass
    if not names:
        try:
            names = {p.name for p in Path(workdir).rglob("*") if p.is_file()}
        except Exception:
            names = set()
    return names


def file_artifact_present(name: str, workdir: Path, basenames: set[str] | None = None) -> bool:
    """True if the enumerated artifact exists in the repo (exact path or basename)."""
    import os

    if (workdir / name).exists():
        return True
    bset = basenames if basenames is not None else _repo_basenames(workdir)
    return os.path.basename(name) in bset


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


def _finish_summary(tool_args: dict, raw: str) -> str:
    """Extract a clean finish summary.

    Models sometimes emit ``{"tool":"finish","summary":"..."}`` with the summary
    at the top level instead of inside ``args`` — leaving ``args`` empty. Recover
    it from the raw content rather than echoing the whole tool-call JSON into the
    Developer Deliverable comment.
    """
    summary = tool_args.get("summary")
    if isinstance(summary, str) and summary.strip():
        return summary.strip()

    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text, re.IGNORECASE)
    candidate = fenced.group(1) if fenced else text
    blob = _extract_json_object(candidate, candidate.find("{")) if "{" in candidate else None
    if blob:
        try:
            data = json.loads(blob)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict):
            for value in (data.get("summary"), (data.get("args") or {}).get("summary")):
                if isinstance(value, str) and value.strip():
                    return value.strip()

    # Last resort: never echo a raw tool-call object as the summary.
    if text.startswith("{") and '"tool"' in text:
        return "Agent finished (no summary provided)."
    return text


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


def _repo_map(workdir: Path, max_files: int = 200) -> str:
    """A compact listing of the repo's tracked files, so the agent knows the
    layout up front instead of crawling it with repeated list_dir."""
    files: list[str] = []
    try:
        proc = subprocess.run(
            ["git", "ls-files"], cwd=str(workdir), capture_output=True, text=True
        )
        if proc.returncode == 0:
            files = [f for f in proc.stdout.splitlines() if f]
    except Exception:
        files = []
    if not files:
        try:
            files = sorted(
                str(p.relative_to(workdir))
                for p in Path(workdir).rglob("*")
                if p.is_file() and ".git" not in p.parts
            )
        except Exception:
            files = []
    total = len(files)
    listing = "\n".join(files[:max_files])
    if total > max_files:
        listing += f"\n…(+{total - max_files} more files; use search)"
    return listing or "(empty repository)"


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
- write_file: {{"path": "relative/path", "content": "..."}}  (NEW files only)
- edit_file: {{"path": "relative/path", "old_string": "exact text to replace", "new_string": "replacement"}}  (add "replace_all": true to change every occurrence — e.g. rename a symbol)
- search: {{"query": "literal text", "path": "."}}  (grep the repo — find where something is)
- list_dir: {{"path": "."}}
- run_command: {{"command": "npm install"}}  (allowlisted: npm, pnpm, yarn, npx, node, python, make, cargo, go, git status/diff/add/commit)
- finish: {{"summary": "what you did"}}

The repository layout is listed below — use it and `search` to jump straight to the
relevant file. Do NOT crawl the tree with repeated list_dir.
To CHANGE an existing file, use edit_file with a unique snippet copied verbatim from a
prior read_file — do NOT rewrite the whole file with write_file (you will drop code and
the change will be rejected). Use write_file only to create NEW files.
For new files, prefer write_file for each artifact; if the task lists multiple languages,
create every language, then call finish immediately.
VERIFY YOUR WORK before finishing: if the repo has a build/compile/test command
(e.g. mvn -q compile, ./gradlew compileJava, npm run build, make, pytest) and it runs
quickly, use run_command to confirm your changes build — then FIX any error it reports.
A change that does not compile will be rejected. If no build tool is available, skip this.
The "Progress so far" list below shows the tools you have ALREADY run this session —
do not repeat completed work, and once every required artifact exists call finish.
Output only the JSON object."""

    repo_map = _repo_map(workdir)
    user = (
        f"## GitHub issue context\n\n{issue_context}\n\n"
        f"## Task\n\n{instructions.strip()}\n\n"
        f"## Repository layout\n\n{repo_map}\n\n"
        "Repository root is the current working directory for tools."
    )

    # Running transcript of completed actions. The model is otherwise stateless
    # per call, so without this it cannot track which artifacts it already wrote
    # and never confidently calls finish (it churns until max turns).
    history: list[str] = []
    # Completeness guard: if the task enumerates specific files to CREATE, don't
    # accept finish until they all exist — models otherwise finish early (e.g. 8 of
    # 30) and ship a partial deliverable. Only files that are ABSENT at the start of
    # the run count: on a modify task the enumerated files (and the file paths the
    # Business Analysis cites in its plan) already exist, so they must not be treated
    # as "to create" — that previously blocked finish forever on modify jobs (#140).
    _start_basenames = _repo_basenames(workdir)
    required_files = [
        f
        for f in expected_artifact_files(f"{instructions}\n\n{issue_context}")
        if not file_artifact_present(f, workdir, _start_basenames)
    ]

    def build_conversation(extra: str = "") -> str:
        parts = [user]
        if history:
            parts.append("## Progress so far (tools you already ran this session)\n" + "\n".join(history))
        parts.append("Next: reply with ONE JSON tool object." + extra)
        return "\n\n---\n".join(parts)

    consecutive_unparsed = 0
    turns_since_change = 0
    read_only_streak = 0
    made_a_change = False
    for _turn in range(MAX_TURNS):
        remaining = MAX_TURNS - _turn
        urgency = ""
        if remaining <= 15:
            urgency = (
                "\n\nURGENT: " + str(remaining) + " turn(s) left. Call "
                '{"tool": "finish", "args": {"summary": "..."}} now with what you completed.'
            )
        try:
            content = chat_completion(
                model,
                system=system,
                user=build_conversation(urgency),
                token=token,
            )
        except HFCreditsDepletedError as exc:
            # Billing, not capability: fail cleanly with an actionable message
            # instead of crashing the workflow with a raw HF error page.
            print(
                f"[actions] ABORT: HF Inference credits depleted for {model}: {exc}",
                file=sys.stderr,
            )
            return (
                f"Blocked: Hugging Face Inference credits are depleted for model "
                f"'{model}' (HTTP 402: {exc}). Add pre-paid credits at "
                f"huggingface.co billing, or switch this issue to a free-tier model.",
                False,
            )
        parsed = parse_tool_call(content)
        if not parsed:
            consecutive_unparsed += 1
            turns_since_change += 1
            print(
                f"[actions] turn {_turn + 1}/{MAX_TURNS}: unparsed ({len(content)} chars), "
                f"consecutive={consecutive_unparsed}",
                file=sys.stderr,
            )
            if consecutive_unparsed >= MAX_CONSECUTIVE_UNPARSED:
                print(
                    f"[actions] ABORT: {consecutive_unparsed} consecutive unparsed responses "
                    f"(>= {MAX_CONSECUTIVE_UNPARSED}); model is not following the tool protocol",
                    file=sys.stderr,
                )
                return (
                    f"Aborted after {_turn + 1} turns: the model produced "
                    f"{consecutive_unparsed} consecutive responses that were not valid tool "
                    f"calls and is not following the JSON tool protocol. This usually means the "
                    f"model is a poor fit for the task — escalate to a stronger model.",
                    False,
                )
            history.append(f"[turn {_turn + 1}] (model output was not valid JSON; reminded to emit a tool object)")
            continue
        consecutive_unparsed = 0
        tool_name, tool_args = parsed
        print(f"[actions] turn {_turn + 1}/{MAX_TURNS}: {tool_name}", file=sys.stderr)
        if tool_name == "finish":
            if required_files:
                _now = _repo_basenames(workdir)
                missing = [f for f in required_files if not file_artifact_present(f, workdir, _now)]
                if missing:
                    print(
                        f"[actions] finish blocked: {len(required_files) - len(missing)}"
                        f"/{len(required_files)} required files exist",
                        file=sys.stderr,
                    )
                    history.append(
                        f"[turn {_turn + 1}] finish REJECTED — "
                        f"{len(required_files) - len(missing)}/{len(required_files)} required "
                        f"files exist. Do NOT finish yet; create the missing file(s): "
                        + ", ".join(missing[:12]) + ("…" if len(missing) > 12 else "")
                    )
                    continue
            if should_verify_build(workdir, issue_context):
                ok, log = verify_workdir(workdir, issue_body=issue_context)
                if not ok:
                    print("[actions] finish blocked: build verification failed", file=sys.stderr)
                    excerpt = log if len(log) <= 2500 else log[-2500:]
                    history.append(
                        f"[turn {_turn + 1}] finish REJECTED — build/compile failed. "
                        f"Fix the errors (run the same build command), then finish again:\n"
                        f"{excerpt}"
                    )
                    continue
            return _finish_summary(tool_args, content), True
        result = execute_tool(workdir, tool_name, tool_args)
        arg_hint = str(tool_args.get("path") or tool_args.get("command") or "").strip()
        result_brief = result if len(result) <= 400 else result[:400] + "…(truncated)"
        history.append(
            f"[turn {_turn + 1}] {tool_name} {arg_hint}".rstrip() + f" -> {result_brief}"
        )
        # Track progress: a write/edit that succeeded counts as forward motion.
        if tool_name in ("write_file", "edit_file") and not result.lower().startswith("error"):
            made_a_change = True
            turns_since_change = 0
            read_only_streak = 0
        else:
            turns_since_change += 1
            if (
                not made_a_change
                and tool_name in ("read_file", "list_dir", "search")
                and not result.lower().startswith("error")
            ):
                read_only_streak += 1
                if read_only_streak >= MAX_READ_ONLY_CHURN:
                    print(
                        f"[actions] ABORT: {read_only_streak} read-only turns "
                        f"without any edit (>= {MAX_READ_ONLY_CHURN})",
                        file=sys.stderr,
                    )
                    return (
                        f"Aborted after {_turn + 1} turns: the agent made "
                        f"{read_only_streak} read/list/search turns without editing any file. "
                        "Use edit_file on the file named in the task or QA fix list.",
                        False,
                    )
        if turns_since_change >= MAX_TURNS_NO_PROGRESS:
            print(
                f"[actions] ABORT: {turns_since_change} turns with no file change "
                f"(>= {MAX_TURNS_NO_PROGRESS}); agent is stalling",
                file=sys.stderr,
            )
            return (
                f"Aborted after {_turn + 1} turns: the agent went "
                f"{turns_since_change} turns without writing or editing any file"
                + (" after earlier edits" if made_a_change else "")
                + ". It is stuck navigating without making progress — escalate to a "
                "stronger model.",
                False,
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
        elif argv[0] == "check-changes":
            # Safety gate: reject destructive rewrites before they become a PR.
            workdir = Path(argv[1])
            # Force standard a/ b/ prefixes regardless of the runner's git config
            # (mnemonicPrefix/noprefix would otherwise break diff parsing).
            diff = subprocess.run(
                ["git", "-c", "diff.mnemonicPrefix=false", "-c", "diff.noprefix=false",
                 "diff", "HEAD"],
                cwd=workdir, capture_output=True, text=True,
            ).stdout
            violations = assess_change_safety(diff)
            for v in violations:
                print(v)
            return 3 if violations else 0
        elif argv[0] == "check-complete":
            # Backstop: a partial result (e.g. agent hit max turns) must not pass as
            # a finished deliverable. The enumerated file list lives in the issue
            # body, so fetch the same context the agent saw.
            workdir = Path(argv[1])
            queue_repo, issue_s = argv[2], argv[3]
            base = os.environ.get("SQUAD_TARGET_BASE_BRANCH", "main")
            task_text = fetch_issue_context_with_parent(queue_repo, int(issue_s))
            enumerated = expected_artifact_files(task_text)
            # Only files the task names that DON'T already exist in the base branch
            # are "to be created" — match by basename so a modify task (whose
            # enumerated files / BA-plan references already exist in base, possibly
            # under bare or guessed paths) isn't wrongly judged incomplete (#140).
            base_basenames: set[str] = set()
            proc = subprocess.run(
                ["git", "ls-tree", "-r", "--name-only", base],
                cwd=workdir, capture_output=True, text=True,
            )
            if proc.returncode == 0:
                base_basenames = {os.path.basename(f) for f in proc.stdout.splitlines() if f}
            to_create = [
                f for f in enumerated
                if os.path.basename(f) not in base_basenames and not (workdir / f).exists()
            ]
            if not to_create:
                return 0
            now = _repo_basenames(workdir)
            missing = [f for f in to_create if not file_artifact_present(f, workdir, now)]
            if missing:
                print(
                    f"incomplete: {len(to_create) - len(missing)}/{len(to_create)} files to create "
                    "present; missing: " + ", ".join(missing[:12]) + ("…" if len(missing) > 12 else "")
                )
                return 4
            return 0
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
