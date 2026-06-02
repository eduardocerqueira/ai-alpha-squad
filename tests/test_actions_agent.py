"""Tests for Squad Actions agent tools."""

from __future__ import annotations

import pytest

import ai_alpha_squad.actions_agent as actions_agent
from ai_alpha_squad.actions_agent import execute_tool, parse_tool_call, run_agent_loop


def test_parse_tool_call_finish():
    parsed = parse_tool_call('{"tool":"finish","args":{"summary":"done"}}')
    assert parsed == ("finish", {"summary": "done"})


def test_parse_tool_call_markdown_fence():
    raw = 'Here is the call:\n```json\n{"tool": "list_dir", "args": {"path": "."}}\n```'
    assert parse_tool_call(raw) == ("list_dir", {"path": "."})


def test_parse_tool_call_nested_args():
    raw = '{"tool": "write_file", "args": {"path": "pkg.json", "content": "{\\"name\\": \\"x\\"}"}}'
    name, args = parse_tool_call(raw)  # type: ignore[misc]
    assert name == "write_file"
    assert args["path"] == "pkg.json"


def test_write_and_read_file(tmp_path):
    result = execute_tool(tmp_path, "write_file", {"path": "a.txt", "content": "hello"})
    assert "ok:" in result
    read = execute_tool(tmp_path, "read_file", {"path": "a.txt"})
    assert read == "hello"


def test_path_escape_blocked(tmp_path):
    result = execute_tool(tmp_path, "read_file", {"path": "../../../etc/passwd"})
    assert result.startswith("error:")


def test_run_command_blocked(tmp_path):
    result = execute_tool(tmp_path, "run_command", {"command": "rm -rf /"})
    assert result.startswith("error:")


def test_run_agent_loop_sees_prior_actions(tmp_path, monkeypatch):
    """The loop must feed prior tool results back so the model can track progress
    and call finish — otherwise it churns until max turns (the #107 failure)."""
    seen_prompts = []

    # Scripted model: decide what to do next based ONLY on the execution-result
    # markers ("ok: wrote …"), which appear solely in the accumulated history —
    # not in the task text. If history weren't fed back, it would loop forever.
    def fake_chat(model, *, system, user, token):
        seen_prompts.append(user)
        if "ok: wrote first.out" not in user:
            return '{"tool":"write_file","args":{"path":"first.out","content":"A"}}'
        if "ok: wrote second.out" not in user:
            return '{"tool":"write_file","args":{"path":"second.out","content":"B"}}'
        return '{"tool":"finish","args":{"summary":"wrote both outputs"}}'

    monkeypatch.setattr(actions_agent, "chat_completion", fake_chat)
    monkeypatch.setattr(actions_agent, "resolve_model", lambda *a, **k: "test-model")
    monkeypatch.setattr(actions_agent, "MAX_TURNS", 10)

    summary, finished = run_agent_loop(
        tmp_path, agent="developer", instructions="produce the outputs", issue_context="ctx", token="t"
    )
    assert finished is True
    assert (tmp_path / "first.out").read_text() == "A"
    assert (tmp_path / "second.out").read_text() == "B"
    # The final prompt must contain BOTH prior write results — proof history persists.
    assert "ok: wrote first.out" in seen_prompts[-1]
    assert "ok: wrote second.out" in seen_prompts[-1]


def test_run_agent_loop_reports_max_turns(tmp_path, monkeypatch):
    monkeypatch.setattr(actions_agent, "chat_completion",
                        lambda *a, **k: '{"tool":"list_dir","args":{"path":"."}}')
    monkeypatch.setattr(actions_agent, "resolve_model", lambda *a, **k: "m")
    monkeypatch.setattr(actions_agent, "MAX_TURNS", 3)
    summary, finished = run_agent_loop(
        tmp_path, agent="developer", instructions="x", issue_context="c", token="t"
    )
    assert finished is False
    assert "max turns" in summary.lower()


def test_run_agent_loop_aborts_on_consecutive_unparsed(tmp_path, monkeypatch):
    """A model that never emits valid JSON should fail fast, not grind to MAX_TURNS."""
    monkeypatch.setattr(actions_agent, "chat_completion",
                        lambda *a, **k: "I think we should consider the architecture…")
    monkeypatch.setattr(actions_agent, "resolve_model", lambda *a, **k: "m")
    monkeypatch.setattr(actions_agent, "MAX_TURNS", 500)
    monkeypatch.setattr(actions_agent, "MAX_CONSECUTIVE_UNPARSED", 4)
    summary, finished = run_agent_loop(
        tmp_path, agent="developer", instructions="x", issue_context="c", token="t"
    )
    assert finished is False
    assert "consecutive" in summary.lower()
    assert "tool protocol" in summary.lower()


def test_run_agent_loop_unparsed_counter_resets_on_valid_call(tmp_path, monkeypatch):
    """Sporadic unparsed turns interspersed with real tool calls must NOT abort."""
    calls = {"n": 0}

    def fake_chat(model, *, system, user, token):
        calls["n"] += 1
        # alternate: unparsed, list_dir, unparsed, list_dir … then finish
        if calls["n"] >= 9:
            return '{"tool":"finish","args":{"summary":"done"}}'
        if calls["n"] % 2 == 1:
            return "musing, not json"
        return '{"tool":"list_dir","args":{"path":"."}}'

    monkeypatch.setattr(actions_agent, "chat_completion", fake_chat)
    monkeypatch.setattr(actions_agent, "resolve_model", lambda *a, **k: "m")
    monkeypatch.setattr(actions_agent, "MAX_TURNS", 50)
    monkeypatch.setattr(actions_agent, "MAX_CONSECUTIVE_UNPARSED", 3)
    summary, finished = run_agent_loop(
        tmp_path, agent="developer", instructions="x", issue_context="c", token="t"
    )
    assert finished is True


def test_run_agent_loop_aborts_on_no_progress(tmp_path, monkeypatch):
    """A model that only navigates (read/list) without ever editing should abort."""
    monkeypatch.setattr(actions_agent, "chat_completion",
                        lambda *a, **k: '{"tool":"list_dir","args":{"path":"."}}')
    monkeypatch.setattr(actions_agent, "resolve_model", lambda *a, **k: "m")
    monkeypatch.setattr(actions_agent, "MAX_TURNS", 500)
    monkeypatch.setattr(actions_agent, "MAX_TURNS_NO_PROGRESS", 5)
    summary, finished = run_agent_loop(
        tmp_path, agent="developer", instructions="x", issue_context="c", token="t"
    )
    assert finished is False
    assert "without writing or editing" in summary.lower()


def test_run_agent_loop_no_progress_resets_on_edit(tmp_path, monkeypatch):
    """Writing a file resets the stall counter so steady editing is never aborted."""
    calls = {"n": 0}

    def fake_chat(model, *, system, user, token):
        calls["n"] += 1
        # navigate a few turns, write a file (resets stall), navigate again, finish
        if calls["n"] >= 9:
            return '{"tool":"finish","args":{"summary":"done"}}'
        if calls["n"] == 4:
            return '{"tool":"write_file","args":{"path":"out.txt","content":"hi"}}'
        return '{"tool":"list_dir","args":{"path":"."}}'

    monkeypatch.setattr(actions_agent, "chat_completion", fake_chat)
    monkeypatch.setattr(actions_agent, "resolve_model", lambda *a, **k: "m")
    monkeypatch.setattr(actions_agent, "MAX_TURNS", 50)
    monkeypatch.setattr(actions_agent, "MAX_TURNS_NO_PROGRESS", 6)
    summary, finished = run_agent_loop(
        tmp_path, agent="developer", instructions="x", issue_context="c", token="t"
    )
    assert finished is True
    assert (tmp_path / "out.txt").read_text() == "hi"


def test_run_agent_loop_blocks_cleanly_on_credits_depleted(tmp_path, monkeypatch):
    """A 402 must fail the run cleanly with an actionable message, not crash it."""
    from ai_alpha_squad.hf_dispatch import HFCreditsDepletedError

    def boom(*a, **k):
        raise HFCreditsDepletedError("You have depleted your monthly included credits.")

    monkeypatch.setattr(actions_agent, "chat_completion", boom)
    monkeypatch.setattr(actions_agent, "resolve_model", lambda *a, **k: "m")
    monkeypatch.setattr(actions_agent, "MAX_TURNS", 50)
    summary, finished = run_agent_loop(
        tmp_path, agent="developer", instructions="x", issue_context="c", token="t"
    )
    assert finished is False
    assert "credits" in summary.lower()
    assert "402" in summary


def test_finish_summary_uses_args_summary():
    from ai_alpha_squad.actions_agent import _finish_summary
    assert _finish_summary({"summary": "did the thing"}, '{"tool":"finish","args":{"summary":"did the thing"}}') == "did the thing"


def test_finish_summary_recovers_top_level_summary():
    # Model put summary at top level, so parsed args is empty and content is raw JSON.
    from ai_alpha_squad.actions_agent import _finish_summary
    raw = '{"tool": "finish", "summary": "Created Hello World in 10 languages."}'
    assert _finish_summary({}, raw) == "Created Hello World in 10 languages."


def test_finish_summary_recovers_from_fenced_json():
    from ai_alpha_squad.actions_agent import _finish_summary
    raw = '```json\n{"tool":"finish","summary":"done all files"}\n```'
    assert _finish_summary({}, raw) == "done all files"


def test_finish_summary_never_echoes_raw_toolcall():
    from ai_alpha_squad.actions_agent import _finish_summary
    raw = '{"tool":"finish","args":{}}'
    out = _finish_summary({}, raw)
    assert '"tool"' not in out and out


# --- destructive-change safety guard ---

_DESTRUCTIVE_DIFF = """diff --git a/seeker/util.py b/seeker/util.py
index d78fa504..b23e20e5 100755
--- a/seeker/util.py
+++ b/seeker/util.py
@@ -13,120 +13,13 @@
-def get_config(section, parameter):
-    config = ConfigParser()
-    return json.loads(config.get(section, parameter))
-
-
-def build_regex():
-    return "x"
-
-
 def purge():
-    day = get_config("purge", "day")
-    files = listdir(SNIPPET_DIR)
-    for file in files:
-        with open(SNIPPET_DIR / file, "r") as fp:
-            data = fp.read()
+    pass
"""

_TARGETED_DIFF = """diff --git a/seeker/util.py b/seeker/util.py
--- a/seeker/util.py
+++ b/seeker/util.py
@@ -50,7 +50,7 @@
 def purge():
     files = listdir(SNIPPET_DIR)
     for file in files:
-        with open(SNIPPET_DIR / file, "r") as fp:
+        with open(SNIPPET_DIR / file, "r", encoding="utf-8", errors="ignore") as fp:
             data = fp.read()
"""


def test_assess_change_safety_flags_removed_defs():
    from ai_alpha_squad.actions_agent import assess_change_safety
    violations = assess_change_safety(_DESTRUCTIVE_DIFF)
    assert violations  # not empty
    joined = " ".join(violations)
    assert "get_config" in joined and "build_regex" in joined


def test_assess_change_safety_allows_targeted_fix():
    from ai_alpha_squad.actions_agent import assess_change_safety
    assert assess_change_safety(_TARGETED_DIFF) == []


def test_assess_change_safety_ignores_purely_additive_diff():
    # New-file / greenfield work only adds lines — must never be flagged.
    from ai_alpha_squad.actions_agent import assess_change_safety
    additive = "diff --git a/hello.py b/hello.py\n--- a/hello.py\n+++ b/hello.py\n" + "".join(
        f"+line {i}\n" for i in range(60)
    )
    assert assess_change_safety(additive) == []


def test_diff_file_stats_counts():
    from ai_alpha_squad.actions_agent import diff_file_stats
    stats = diff_file_stats(_DESTRUCTIVE_DIFF)
    assert "seeker/util.py" in stats
    s = stats["seeker/util.py"]
    assert s["removed"] > s["added"]
    assert {"get_config", "build_regex"} <= s["removed_defs"]


# --- edit_file (targeted find/replace for existing files) ---

def test_edit_file_replaces_unique_snippet(tmp_path):
    (tmp_path / "u.py").write_text('open(f, "r")\nother = 1\n')
    res = execute_tool(tmp_path, "edit_file", {
        "path": "u.py", "old_string": 'open(f, "r")', "new_string": 'open(f, "r", errors="ignore")'})
    assert res.startswith("ok:")
    assert (tmp_path / "u.py").read_text() == 'open(f, "r", errors="ignore")\nother = 1\n'


def test_edit_file_errors_when_not_found(tmp_path):
    (tmp_path / "u.py").write_text("a = 1\n")
    res = execute_tool(tmp_path, "edit_file", {"path": "u.py", "old_string": "nope", "new_string": "x"})
    assert res.startswith("error:") and "not found" in res


def test_edit_file_errors_on_ambiguous_match(tmp_path):
    (tmp_path / "u.py").write_text("x\nx\n")
    res = execute_tool(tmp_path, "edit_file", {"path": "u.py", "old_string": "x", "new_string": "y"})
    assert res.startswith("error:") and "matches 2" in res


def test_edit_file_errors_on_missing_file(tmp_path):
    res = execute_tool(tmp_path, "edit_file", {"path": "nope.py", "old_string": "a", "new_string": "b"})
    assert res.startswith("error:") and "not a file" in res


def test_edit_file_rejects_path_escape(tmp_path):
    res = execute_tool(tmp_path, "edit_file", {"path": "../../etc/passwd", "old_string": "a", "new_string": "b"})
    assert res.startswith("error:")


# --- completeness guardrail (block premature finish on enumerated multi-file tasks) ---

_TASK_30 = "\n".join(
    [f"{i}. Lang{i} — `hello.x{i}`" for i in range(1, 31)]
) + "\nAdd these files and update the README."


def test_expected_artifact_count_counts_enumerated_files():
    from ai_alpha_squad.actions_agent import expected_artifact_count
    assert expected_artifact_count(_TASK_30) == 30


def test_expected_artifact_count_none_for_non_list_task():
    from ai_alpha_squad.actions_agent import expected_artifact_count
    assert expected_artifact_count("Fix the UnicodeDecodeError in purge().") is None
    # A short numbered step list (no filenames) must not trigger.
    assert expected_artifact_count("1. clone\n2. edit\n3. push") is None


def test_loop_blocks_finish_until_all_files_created(tmp_path, monkeypatch):
    """Agent that tries to finish after 2 of 3 files must be forced to continue."""
    monkeypatch.setattr(actions_agent, "resolve_model", lambda *a, **k: "m")
    monkeypatch.setattr(actions_agent, "MAX_TURNS", 30)
    task = "1. A — `a.py`\n2. B — `b.py`\n3. C — `c.py`"
    calls = {"n": 0}

    def fake_chat(model, *, system, user, token):
        calls["n"] += 1
        # Try to finish immediately; only actually finishes once 3 files exist.
        for name, fn in (("a.py", "a"), ("b.py", "b"), ("c.py", "c")):
            if f"ok: wrote {name}" not in user:
                # Premature finish attempt before all files exist on first chance:
                if calls["n"] == 1:
                    return '{"tool":"finish","args":{"summary":"done early"}}'
                return '{"tool":"write_file","args":{"path":"%s","content":"x"}}' % name
        return '{"tool":"finish","args":{"summary":"all three created"}}'

    monkeypatch.setattr(actions_agent, "chat_completion", fake_chat)
    summary, finished = run_agent_loop(
        tmp_path, agent="developer", instructions=task, issue_context="c", token="t"
    )
    assert finished is True
    # The early finish was rejected, so all three files got created.
    assert (tmp_path / "a.py").exists() and (tmp_path / "b.py").exists() and (tmp_path / "c.py").exists()
    assert "all three" in summary


def test_loop_allows_finish_when_no_required_count(tmp_path, monkeypatch):
    monkeypatch.setattr(actions_agent, "resolve_model", lambda *a, **k: "m")
    monkeypatch.setattr(actions_agent, "MAX_TURNS", 5)
    monkeypatch.setattr(actions_agent, "chat_completion",
                        lambda *a, **k: '{"tool":"finish","args":{"summary":"fixed the bug"}}')
    summary, finished = run_agent_loop(
        tmp_path, agent="developer", instructions="Fix the bug in util.py", issue_context="c", token="t"
    )
    assert finished is True and "fixed" in summary


# --- filename-based completeness (robust across idempotent continues) ---

def test_expected_artifact_files_lists_filenames():
    from ai_alpha_squad.actions_agent import expected_artifact_files
    task = "1. A — `a.py`\n2. B — `b.py`\n3. C — `c.py`"
    assert expected_artifact_files(task) == ["a.py", "b.py", "c.py"]


def test_expected_artifact_files_takes_first_filename_per_line():
    # Item 23 of #120: "23. Prolog — `hello.pro`  (note: `hello.pl` is taken)"
    from ai_alpha_squad.actions_agent import expected_artifact_files
    task = "1. X — `x.a`\n2. Y — `y.b`\n3. Prolog — `hello.pro` (note: `hello.pl` taken)"
    assert expected_artifact_files(task) == ["x.a", "y.b", "hello.pro"]


def test_loop_counts_preexisting_files_for_completion(tmp_path, monkeypatch):
    """Idempotent continue: a required file already on disk counts, so the agent
    only needs to create the rest before finish is allowed."""
    (tmp_path / "a.py").write_text("exists from a prior run\n")
    monkeypatch.setattr(actions_agent, "resolve_model", lambda *a, **k: "m")
    monkeypatch.setattr(actions_agent, "MAX_TURNS", 20)
    task = "1. A — `a.py`\n2. B — `b.py`\n3. C — `c.py`"
    calls = {"n": 0}

    def fake_chat(model, *, system, user, token):
        calls["n"] += 1
        if not (tmp_path / "b.py").exists():
            return '{"tool":"write_file","args":{"path":"b.py","content":"x"}}'
        if not (tmp_path / "c.py").exists():
            return '{"tool":"write_file","args":{"path":"c.py","content":"x"}}'
        return '{"tool":"finish","args":{"summary":"done"}}'

    monkeypatch.setattr(actions_agent, "chat_completion", fake_chat)
    summary, finished = run_agent_loop(
        tmp_path, agent="developer", instructions=task, issue_context="c", token="t"
    )
    assert finished is True
    # a.py was never rewritten (it pre-existed); only b/c created.
    assert (tmp_path / "a.py").read_text() == "exists from a prior run\n"
    assert (tmp_path / "b.py").exists() and (tmp_path / "c.py").exists()


def test_loop_guard_reads_list_from_issue_context(tmp_path, monkeypatch):
    """The enumerated file list lives in the issue body (issue_context), not the
    short dispatch instructions — the guard must still engage."""
    monkeypatch.setattr(actions_agent, "resolve_model", lambda *a, **k: "m")
    monkeypatch.setattr(actions_agent, "MAX_TURNS", 20)
    short_instructions = "Implement on the target repo and post # Developer Deliverable."
    issue_body = "1. A — `a.py`\n2. B — `b.py`\n3. C — `c.py`"

    def fake_chat(model, *, system, user, token):
        for name in ("a.py", "b.py", "c.py"):
            if not (tmp_path / name).exists():
                return '{"tool":"write_file","args":{"path":"%s","content":"x"}}' % name
        return '{"tool":"finish","args":{"summary":"all done"}}'

    monkeypatch.setattr(actions_agent, "chat_completion", fake_chat)
    summary, finished = run_agent_loop(
        tmp_path, agent="developer", instructions=short_instructions,
        issue_context=issue_body, token="t",
    )
    assert finished is True
    assert all((tmp_path / f).exists() for f in ("a.py", "b.py", "c.py"))


def test_loop_guard_ignores_preexisting_enumerated_files_modify_task(tmp_path, monkeypatch):
    """Modify task: the enumerated files (and BA-plan file refs) already exist, so
    none are 'to create' — finish must NOT be blocked (the #140 regression)."""
    # All enumerated files already present (a modify task / BA plan referencing them).
    for n in ("BuildMonitorView.java", "index.jelly", "configure-entries.jelly"):
        (tmp_path / n).write_text("existing\n")
    monkeypatch.setattr(actions_agent, "resolve_model", lambda *a, **k: "m")
    monkeypatch.setattr(actions_agent, "MAX_TURNS", 5)
    task = ("Plan:\n1. Edit `BuildMonitorView.java`\n2. Edit `index.jelly`\n"
            "3. Edit `configure-entries.jelly`")
    monkeypatch.setattr(actions_agent, "chat_completion",
                        lambda *a, **k: '{"tool":"finish","args":{"summary":"edited the existing files"}}')
    summary, finished = run_agent_loop(
        tmp_path, agent="developer", instructions="modernize", issue_context=task, token="t"
    )
    assert finished is True  # not blocked, because nothing was "to create"
    assert "edited" in summary


# --- search tool + repo map (agent navigation) ---

def test_search_tool_finds_matches(tmp_path):
    (tmp_path / "a.py").write_text("import os\nLOGO_URL = 'x'\n")
    (tmp_path / "b.txt").write_text("nothing here\n")
    res = execute_tool(tmp_path, "search", {"query": "LOGO_URL"})
    assert "a.py" in res and "LOGO_URL" in res
    assert "b.txt" not in res


def test_search_tool_no_match(tmp_path):
    (tmp_path / "a.py").write_text("hello\n")
    assert execute_tool(tmp_path, "search", {"query": "zzzznope"}) == "(no matches)"


def test_search_tool_requires_query(tmp_path):
    assert execute_tool(tmp_path, "search", {"query": ""}).startswith("error:")


def test_search_tool_respects_sandbox(tmp_path):
    res = execute_tool(tmp_path, "search", {"query": "x", "path": "../../.."})
    assert res.startswith("error:")


def test_repo_map_lists_files(tmp_path):
    from ai_alpha_squad.actions_agent import _repo_map
    (tmp_path / "x.py").write_text("1\n")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "y.txt").write_text("2\n")
    m = _repo_map(tmp_path)
    assert "x.py" in m and "sub/y.txt" in m


def test_guard_matches_deep_files_by_basename_modify_task(tmp_path, monkeypatch):
    """#140 regression: enumerated files referenced by bare/wrong paths but present
    at a deep path must count as existing — not 'to create' — so finish isn't blocked."""
    # Real files live deep in the tree.
    deep = tmp_path / "src/main/java/com/x/buildmonitor"
    deep.mkdir(parents=True)
    (deep / "BuildMonitorView.java").write_text("class X {}\n")
    resdir = tmp_path / "src/main/resources/com/x/buildmonitor/BuildMonitorView"
    resdir.mkdir(parents=True)
    (resdir / "index.jelly").write_text("<x/>\n")
    (resdir / "configure-entries.jelly").write_text("<x/>\n")

    # Issue/BA enumerate them by bare names + a WRONG path (java instead of resources).
    task = (
        "Pointers:\n"
        "1. `src/main/java/com/x/buildmonitor/BuildMonitorView/index.jelly`\n"
        "2. `BuildMonitorView.java`\n"
        "3. `configure-entries.jelly`\n"
    )
    monkeypatch.setattr(actions_agent, "resolve_model", lambda *a, **k: "m")
    monkeypatch.setattr(actions_agent, "MAX_TURNS", 4)
    monkeypatch.setattr(actions_agent, "chat_completion",
                        lambda *a, **k: '{"tool":"finish","args":{"summary":"added logoUrl"}}')
    summary, finished = run_agent_loop(
        tmp_path, agent="developer", instructions="add configurable logo",
        issue_context=task, token="t",
    )
    assert finished is True   # not blocked — all referenced files already exist
    assert "logoUrl" in summary


def test_file_artifact_present_basename(tmp_path):
    from ai_alpha_squad.actions_agent import file_artifact_present
    d = tmp_path / "deep/pkg"
    d.mkdir(parents=True)
    (d / "Foo.java").write_text("x\n")
    assert file_artifact_present("Foo.java", tmp_path)            # bare name
    assert file_artifact_present("wrong/path/Foo.java", tmp_path)  # wrong path, right basename
    assert not file_artifact_present("Bar.java", tmp_path)
