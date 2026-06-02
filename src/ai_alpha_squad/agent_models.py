"""Resolve AI provider and per-agent model overrides from env, squad-config, and agent docs."""

from __future__ import annotations

import os
import re
from pathlib import Path

SUPPORTED_PROVIDERS = frozenset({"copilot", "huggingface"})
SUPPORTED_CODE_RUNTIMES = frozenset({"actions", "copilot"})
SUPPORTED_DISPATCH_MODES = frozenset({"hf", "actions", "copilot"})

DEFAULT_PROVIDER = "copilot"
DEFAULT_CODE_RUNTIME = "actions"
DEFAULT_HF_MODEL = "meta-llama/Meta-Llama-3.1-8B-Instruct"

CODING_AGENT_SLUGS = frozenset({"developer", "devops"})

HF_DISPATCH_MARKER = "Squad HF agent dispatched"
HF_RESULT_MARKER = "Squad HF agent result"
ACTIONS_DISPATCH_MARKER = "Squad Actions agent dispatched"
ACTIONS_RESULT_MARKER = "Squad Actions agent result"

_AGENT_SLUGS = {
    "business-owner",
    "architect",
    "developer",
    "qa",
    "security",
    "devops",
    "release-manager",
    "tech-writer",
}

_AI_MODEL_HEADING = re.compile(r"^##\s+AI\s+Model\s*$", re.MULTILINE | re.IGNORECASE)
# Table row: | huggingface | `model-id` | or | huggingface | model-id |
_TABLE_ROW = re.compile(
    r"^\|\s*([a-z][a-z0-9_-]*)\s*\|\s*`?([^`|]+?)`?\s*\|",
    re.MULTILINE | re.IGNORECASE,
)
# List: - **huggingface:** `model` (colon inside bold) or - huggingface: model
_LIST_BOLD = re.compile(
    r"^[-*]\s+\*\*([a-z][a-z0-9_-]*):?\*\*\s*`?([^`\n]+?)`?\s*$",
    re.MULTILINE | re.IGNORECASE,
)
_LIST_PLAIN = re.compile(
    r"^[-*]\s+([a-z][a-z0-9_-]*)\s*:\s*`?([^`\n]+?)`?\s*$",
    re.MULTILINE | re.IGNORECASE,
)
_CONFIG_PROVIDER = re.compile(
    r"(?ms)^ai:\s*\n(?:[ \t].*\n)*?[ \t]+provider:\s*([a-z][a-z0-9_-]*)\s*$",
)
_CONFIG_DEFAULT = re.compile(
    r"(?ms)^ai:\s*\n(?:[ \t].*\n)*?[ \t]+defaults:\s*\n"
    r"(?:[ \t].*\n)*?[ \t]+([a-z][a-z0-9_-]*):\s*([^\s#]+)\s*$",
)
_CONFIG_AGENT_MODEL = re.compile(
    r"(?ms)^ai:\s*\n(?:[ \t].*\n)*?[ \t]+agents:\s*\n"
    r"(?:[ \t].*\n)*?[ \t]+([a-z][a-z0-9_-]*):\s*\n"
    r"(?:[ \t].*\n)*?[ \t]+([a-z][a-z0-9_-]*):\s*([^\s#]+)\s*$",
)
_CONFIG_CODE_RUNTIME = re.compile(
    r"(?ms)^ai:\s*\n(?:[ \t].*\n)*?[ \t]+code_runtime:\s*([a-z][a-z0-9_-]*)\s*$",
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def agents_dir() -> Path:
    return repo_root() / ".agents"


def agent_doc_path(agent_slug: str) -> Path:
    slug = normalize_agent_slug(agent_slug)
    return agents_dir() / f"agent-{slug}.md"


def normalize_agent_slug(agent_slug: str) -> str:
    key = (agent_slug or "").strip().lower().replace("_", "-")
    if key not in _AGENT_SLUGS:
        raise ValueError(f"Unknown agent slug: {agent_slug!r}")
    return key


def squad_config_path() -> Path | None:
    path = repo_root() / ".agents" / "squad-config.yaml"
    return path if path.is_file() else None


def _load_config_text() -> str:
    path = squad_config_path()
    if not path:
        return ""
    return path.read_text(encoding="utf-8")


def resolve_code_runtime() -> str:
    """Coding runtime for developer/devops: SQUAD_CODE_RUNTIME > squad-config > default actions."""
    env = os.environ.get("SQUAD_CODE_RUNTIME", "").strip().lower()
    if env:
        if env not in SUPPORTED_CODE_RUNTIMES:
            raise ValueError(
                f"SQUAD_CODE_RUNTIME={env!r} invalid; use: {', '.join(sorted(SUPPORTED_CODE_RUNTIMES))}"
            )
        return env

    text = _load_config_text()
    match = _CONFIG_CODE_RUNTIME.search(text)
    if match:
        runtime = match.group(1).lower()
        if runtime in SUPPORTED_CODE_RUNTIMES:
            return runtime

    if resolve_provider() == "huggingface":
        return DEFAULT_CODE_RUNTIME
    return "copilot"


def _config_agent_provider(agent_slug: str) -> str | None:
    text = _load_config_text()
    if not text:
        return None
    slug = normalize_agent_slug(agent_slug)
    pattern = re.compile(
        rf"(?ms)^[ \t]+{re.escape(slug)}:\s*\n"
        r"(?:[ \t].*\n)*?[ \t]+provider:\s*([a-z][a-z0-9_-]*)\s*$",
    )
    match = pattern.search(text)
    if not match:
        return None
    provider = match.group(1).lower()
    if provider in SUPPORTED_PROVIDERS:
        return provider
    return None


def resolve_provider_for_agent(agent_slug: str) -> str:
    """Per-agent AI provider override, else global resolve_provider()."""
    cfg = _config_agent_provider(agent_slug)
    if cfg:
        return cfg
    return resolve_provider()


def resolve_dispatch_mode(agent_slug: str) -> str:
    """
    How to run an agent: hf (issue comment), actions (coding loop), copilot (legacy assign).

    Coding agents (developer, devops) use SQUAD_CODE_RUNTIME when set to actions.
    Other agents use resolve_provider_for_agent (huggingface -> hf, else copilot).
    """
    slug = normalize_agent_slug(agent_slug)
    if slug in CODING_AGENT_SLUGS and resolve_code_runtime() == "actions":
        return "actions"
    if slug in CODING_AGENT_SLUGS and resolve_code_runtime() == "copilot":
        return "copilot"
    if resolve_provider_for_agent(slug) == "huggingface":
        return "hf"
    return "copilot"


def resolve_provider() -> str:
    """Active provider: SQUAD_AI_PROVIDER env > squad-config ai.provider > copilot."""
    env = os.environ.get("SQUAD_AI_PROVIDER", "").strip().lower()
    if env:
        if env not in SUPPORTED_PROVIDERS:
            raise ValueError(
                f"SQUAD_AI_PROVIDER={env!r} invalid; use: {', '.join(sorted(SUPPORTED_PROVIDERS))}"
            )
        return env

    text = _load_config_text()
    match = _CONFIG_PROVIDER.search(text)
    if match:
        provider = match.group(1).lower()
        if provider in SUPPORTED_PROVIDERS:
            return provider

    return DEFAULT_PROVIDER


def _config_default_model(provider: str) -> str | None:
    text = _load_config_text()
    if not text:
        return None
    for match in _CONFIG_DEFAULT.finditer(text):
        if match.group(1).lower() == provider.lower():
            return match.group(2).strip().strip("`")
    return None


def _config_agent_model(agent_slug: str, provider: str) -> str | None:
    text = _load_config_text()
    if not text:
        return None
    slug = normalize_agent_slug(agent_slug)
    for match in _CONFIG_AGENT_MODEL.finditer(text):
        if match.group(1).lower() != slug:
            continue
        if match.group(2).lower() == provider.lower():
            return match.group(3).strip().strip("`")
    return None


def parse_ai_model_section(markdown: str) -> dict[str, str]:
    """Parse ## AI Model section into provider -> model id."""
    heading = _AI_MODEL_HEADING.search(markdown)
    if not heading:
        return {}

    section = markdown[heading.end() :]
    next_heading = re.search(r"^##\s+", section, re.MULTILINE)
    if next_heading:
        section = section[: next_heading.start()]

    models: dict[str, str] = {}
    for pattern in (_TABLE_ROW, _LIST_BOLD, _LIST_PLAIN):
        for match in pattern.finditer(section):
            provider = match.group(1).lower()
            model = match.group(2).strip().strip("`").strip()
            if provider in ("provider",) or model.lower() in ("model",):
                continue
            if re.fullmatch(r"-+", provider) or re.fullmatch(r"-+", model):
                continue
            if not model or model.lower() in ("_", "default", "(default)", "—", "-"):
                continue
            if model.startswith("_(") and model.endswith(")_"):
                continue
            models[provider] = model
    return models


def parse_agent_doc_models(agent_slug: str) -> dict[str, str]:
    path = agent_doc_path(agent_slug)
    if not path.is_file():
        return {}
    return parse_ai_model_section(path.read_text(encoding="utf-8"))


def default_model_for_provider(provider: str) -> str:
    if provider == "huggingface":
        env = os.environ.get("SQUAD_HF_DEFAULT_MODEL", "").strip()
        if env:
            return env
        cfg = _config_default_model("huggingface")
        if cfg:
            return cfg
        return DEFAULT_HF_MODEL
    return ""


def resolve_model(agent_slug: str, provider: str | None = None) -> str:
    """
    Model for an agent on a provider.

    Precedence: agent doc ## AI Model > squad-config ai.agents > env default > built-in default.
    """
    provider = (provider or resolve_provider()).lower()
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(f"Unsupported provider: {provider!r}")

    # Highest precedence: a per-dispatch override (model-escalation ladder, or a
    # Director-chosen model from the dashboard). Beats the agent doc / config.
    override = os.environ.get("SQUAD_AGENT_MODEL_OVERRIDE", "").strip()
    if override and provider == "huggingface":
        return override

    doc_models = parse_agent_doc_models(agent_slug)
    if provider in doc_models:
        return doc_models[provider]

    cfg_model = _config_agent_model(agent_slug, provider)
    if cfg_model:
        return cfg_model

    return default_model_for_provider(provider)


def model_summary(agent_slug: str, provider: str | None = None) -> str:
    """Human-readable model line for dispatch comments."""
    mode = resolve_dispatch_mode(agent_slug)
    if mode == "actions":
        model = resolve_model(agent_slug, "huggingface")
        return f"GitHub Actions coding agent · HF `{model}`"
    provider = provider or resolve_provider_for_agent(agent_slug)
    if provider == "copilot":
        return "Copilot custom agent (legacy — GitHub Copilot coding agent)"
    model = resolve_model(agent_slug, provider)
    return f"`{model}`"
