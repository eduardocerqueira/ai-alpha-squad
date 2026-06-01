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
