"""Format GitHub issue comments with squad agent avatar icons."""

from __future__ import annotations

import os

DEFAULT_ICON_REPO = "eduardocerqueira/ai-alpha-squad"
DEFAULT_ICON_REF = "main"
ICON_SIZE_INLINE = 22
ICON_SIZE_AVATAR = 40

# Copilot custom_agent slugs and system roles → assets/agents/{slug}.svg
AGENT_SLUGS = frozenset(
    {
        "orchestrator",
        "business-owner",
        "architect",
        "developer",
        "qa",
        "security",
        "devops",
        "release-manager",
        "tech-writer",
        "director",
    }
)

_ALIAS: dict[str, str] = {
    "business_owner": "business-owner",
    "release_manager": "release-manager",
    "tech_writer": "tech-writer",
    "squad-orchestrator": "orchestrator",
    "squad_orchestrator": "orchestrator",
}


def normalize_agent_slug(slug: str) -> str:
    """Map agent id to assets/agents/{slug}.svg filename."""
    key = (slug or "").strip().lower().replace(" ", "-")
    key = _ALIAS.get(key, key)
    if key not in AGENT_SLUGS:
        raise ValueError(f"Unknown agent slug: {slug!r}. Known: {sorted(AGENT_SLUGS)}")
    return key


def icon_url(
    slug: str,
    *,
    repo: str | None = None,
    ref: str | None = None,
) -> str:
    """Public raw URL for an agent SVG (must exist on default branch)."""
    agent = normalize_agent_slug(slug)
    owner, name = _parse_repo(repo or os.environ.get("SQUAD_ICON_REPO", DEFAULT_ICON_REPO))
    branch = ref or os.environ.get("SQUAD_ICON_REF", DEFAULT_ICON_REF)
    return (
        f"https://raw.githubusercontent.com/{owner}/{name}/{branch}"
        f"/assets/agents/{agent}.svg"
    )


def agent_icon_img(slug: str, *, size: int = ICON_SIZE_INLINE, repo: str | None = None, ref: str | None = None) -> str:
    agent = normalize_agent_slug(slug)
    url = icon_url(agent, repo=repo, ref=ref)
    return (
        f'<img src="{url}" width="{size}" height="{size}" alt="{agent}" '
        f'title="{agent.replace("-", " ")}" style="vertical-align:middle" />'
    )


def format_squad_comment(
    message_md: str,
    *,
    avatar: str,
    repo: str | None = None,
    ref: str | None = None,
) -> str:
    """Wrap markdown/HTML message with a left-aligned agent avatar."""
    url = icon_url(avatar, repo=repo, ref=ref)
    agent = normalize_agent_slug(avatar)
    alt = agent.replace("-", " ")
    body = message_md.strip()
    return (
        "<table>\n<tr>\n"
        f'<td width="48" valign="top">'
        f'<img src="{url}" width="{ICON_SIZE_AVATAR}" height="{ICON_SIZE_AVATAR}" '
        f'alt="{alt}" title="{alt}" />\n'
        "</td>\n"
        f'<td valign="top">\n\n{body}\n\n</td>\n'
        "</tr>\n</table>"
    )


def format_dispatch_comment(agent: str, label: str, *, repo: str | None = None, ref: str | None = None) -> str:
    """Orchestrator assigned Copilot agent — orchestrator avatar + inline target agent icon."""
    agent_slug = normalize_agent_slug(agent)
    icon = agent_icon_img(agent_slug, repo=repo, ref=ref)
    message = (
        f"**Squad orchestrator** assigned Copilot agent {icon} `{agent_slug}` "
        f"for label `{label}`."
    )
    return format_squad_comment(message, avatar="orchestrator", repo=repo, ref=ref)


def format_dispatch_fallback_comment(
    agent: str,
    instructions: str,
    *,
    repo: str | None = None,
    ref: str | None = None,
) -> str:
    agent_slug = normalize_agent_slug(agent)
    icon = agent_icon_img(agent_slug, repo=repo, ref=ref)
    message = (
        "**Squad orchestrator** could not auto-assign Copilot "
        f"(check `SQUAD_ORCHESTRATOR_TOKEN` / Copilot agent API).\n\n"
        f"Please assign **Copilot** with custom agent {icon} **`{agent_slug}`** on this issue.\n\n"
        f"```\n{instructions.strip()}\n```"
    )
    return format_squad_comment(message, avatar="orchestrator", repo=repo, ref=ref)


def format_orchestrator_notice(message_md: str, *, repo: str | None = None, ref: str | None = None) -> str:
    return format_squad_comment(message_md, avatar="orchestrator", repo=repo, ref=ref)


def _parse_repo(repo: str) -> tuple[str, str]:
    if "/" not in repo:
        raise ValueError(f"Invalid repo {repo!r}; expected owner/name")
    owner, name = repo.split("/", 1)
    return owner, name
