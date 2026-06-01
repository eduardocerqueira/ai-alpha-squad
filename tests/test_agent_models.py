"""Tests for AI provider and per-agent model resolution."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from ai_alpha_squad import agent_models as am


def test_parse_ai_model_section_table_and_list():
    md = """
## AI Model

| Provider | Model |
| -------- | ----- |
| huggingface | `deepseek-ai/DeepSeek-V4-Flash` |
| copilot | _(default)_ |

## Role
"""
    assert am.parse_ai_model_section(md) == {
        "huggingface": "deepseek-ai/DeepSeek-V4-Flash",
    }


def test_resolve_model_from_agent_doc(tmp_path, monkeypatch):
    agents = tmp_path / ".agents"
    agents.mkdir()
    (agents / "agent-qa.md").write_text(
        "## AI Model\n\n- **huggingface:** `org/custom-model`\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(am, "agents_dir", lambda: agents)
    monkeypatch.setattr(am, "squad_config_path", lambda: None)
    monkeypatch.delenv("SQUAD_HF_DEFAULT_MODEL", raising=False)
    assert am.resolve_model("qa", "huggingface") == "org/custom-model"


def test_resolve_provider_env(monkeypatch):
    monkeypatch.setenv("SQUAD_AI_PROVIDER", "huggingface")
    assert am.resolve_provider() == "huggingface"
    monkeypatch.setenv("SQUAD_AI_PROVIDER", "copilot")
    assert am.resolve_provider() == "copilot"


def test_resolve_provider_invalid(monkeypatch):
    monkeypatch.setenv("SQUAD_AI_PROVIDER", "openai")
    with pytest.raises(ValueError, match="invalid"):
        am.resolve_provider()


def test_default_hf_model_env(monkeypatch):
    monkeypatch.delenv("SQUAD_HF_DEFAULT_MODEL", raising=False)
    monkeypatch.setattr(am, "squad_config_path", lambda: None)
    assert am.default_model_for_provider("huggingface") == am.DEFAULT_HF_MODEL
    monkeypatch.setenv("SQUAD_HF_DEFAULT_MODEL", "meta-llama/Llama-3.2-3B-Instruct")
    assert am.default_model_for_provider("huggingface") == "meta-llama/Llama-3.2-3B-Instruct"


EXPECTED_AGENT_HF_MODELS = {
    "business-owner": "deepseek-ai/DeepSeek-V4-Flash",
    "architect": "Qwen/Qwen3.6-27B",
    "developer": "Qwen/Qwen2.5-Coder-32B-Instruct",
    "qa": "deepseek-ai/DeepSeek-V4-Flash",
    "security": "deepseek-ai/DeepSeek-V4-Flash",
    "devops": "Qwen/Qwen2.5-Coder-32B-Instruct",
    "tech-writer": "deepseek-ai/DeepSeek-V4-Flash",
    "release-manager": "deepseek-ai/DeepSeek-V4-Flash",
}


@pytest.mark.parametrize("slug,model", EXPECTED_AGENT_HF_MODELS.items())
def test_all_agent_docs_define_hf_model(slug, model):
    path = am.agent_doc_path(slug)
    assert path.is_file(), f"missing {path}"
    text = path.read_text(encoding="utf-8")
    assert "## AI Model" in text
    assert am.parse_ai_model_section(text).get("huggingface") == model
    assert am.resolve_model(slug, "huggingface") == model
