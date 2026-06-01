"""Tests for per-agent dispatch routing (HF / Actions / Copilot)."""

from __future__ import annotations

import pytest

from ai_alpha_squad import agent_models as am


def test_resolve_dispatch_mode_coding_actions(monkeypatch):
    monkeypatch.setenv("SQUAD_CODE_RUNTIME", "actions")
    monkeypatch.setenv("SQUAD_AI_PROVIDER", "huggingface")
    assert am.resolve_dispatch_mode("developer") == "actions"
    assert am.resolve_dispatch_mode("devops") == "actions"
    assert am.resolve_dispatch_mode("business-owner") == "hf"


def test_resolve_dispatch_mode_coding_copilot_legacy(monkeypatch):
    monkeypatch.setenv("SQUAD_CODE_RUNTIME", "copilot")
    monkeypatch.setenv("SQUAD_AI_PROVIDER", "huggingface")
    assert am.resolve_dispatch_mode("developer") == "copilot"
    assert am.resolve_dispatch_mode("qa") == "hf"


def test_resolve_code_runtime_defaults_to_actions_with_hf(monkeypatch, tmp_path):
    monkeypatch.delenv("SQUAD_CODE_RUNTIME", raising=False)
    monkeypatch.setenv("SQUAD_AI_PROVIDER", "huggingface")
    monkeypatch.setattr(am, "squad_config_path", lambda: None)
    assert am.resolve_code_runtime() == "actions"


def test_parse_tool_call_json():
    from ai_alpha_squad.actions_agent import parse_tool_call

    content = '{"tool": "read_file", "args": {"path": "README.md"}}'
    parsed = parse_tool_call(content)
    assert parsed == ("read_file", {"path": "README.md"})
