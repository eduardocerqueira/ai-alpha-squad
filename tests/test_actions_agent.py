"""Tests for Squad Actions agent tools."""

from __future__ import annotations

import pytest

from ai_alpha_squad.actions_agent import execute_tool, parse_tool_call


def test_parse_tool_call_finish():
    parsed = parse_tool_call('{"tool":"finish","args":{"summary":"done"}}')
    assert parsed == ("finish", {"summary": "done"})


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
