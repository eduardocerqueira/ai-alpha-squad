"""Classify Director WhatsApp replies per whatsapp-director-channel.md."""

from enum import Enum
import re

from ai_alpha_squad.comments import agent_icon_img, format_squad_comment


class DirectorReplyIntent(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    CHANGES = "changes"
    AMBIGUOUS = "ambiguous"


_APPROVE_PHRASES = (
    "approved",
    "approve",
    "yes",
    "lgtm",
    "go",
    "ship it",
    "ok to release",
    "release",
)

_REJECT_PHRASES = (
    "reject",
    "rejected",
    "no",
    "hold",
    "stop",
    "not approved",
)

_CHANGES_PHRASES = (
    "changes",
    "revise",
    "questions",
    "need more",
    "clarify",
)

_APPROVE_EMOJI = frozenset({"👍", "✅", "✔", "✔️"})


def classify_director_reply(text: str) -> DirectorReplyIntent:
    """Map Director message body to squad intent."""
    raw = (text or "").strip()
    if not raw:
        return DirectorReplyIntent.AMBIGUOUS

    if raw in _APPROVE_EMOJI:
        return DirectorReplyIntent.APPROVE

    upper_prefix = raw.upper()
    if upper_prefix.startswith("REJECT:") or upper_prefix.startswith("REJECT "):
        return DirectorReplyIntent.REJECT
    if upper_prefix.startswith("CHANGES:") or upper_prefix.startswith("CHANGES "):
        return DirectorReplyIntent.CHANGES
    if upper_prefix.startswith("APPROVE"):
        return DirectorReplyIntent.APPROVE

    normalized = re.sub(r"\s+", " ", raw.lower())

    def _has_phrase(phrase: str) -> bool:
        if " " in phrase:
            return phrase in normalized
        return re.search(rf"\b{re.escape(phrase)}\b", normalized) is not None

    if any(_has_phrase(p) for p in _REJECT_PHRASES):
        return DirectorReplyIntent.REJECT

    if any(_has_phrase(p) for p in _CHANGES_PHRASES):
        return DirectorReplyIntent.CHANGES

    if any(_has_phrase(p) for p in _APPROVE_PHRASES):
        return DirectorReplyIntent.APPROVE

    return DirectorReplyIntent.AMBIGUOUS


def format_audit_comment(
    *,
    received_at: str,
    classification: DirectorReplyIntent,
    message: str,
    agent: str,
    repo: str | None = None,
    ref: str | None = None,
) -> str:
    """GitHub issue comment body for a WhatsApp Director response."""
    agent_icon = agent_icon_img(agent, repo=repo, ref=ref)
    body = (
        "## Director response (WhatsApp)\n\n"
        f"**Received:** {received_at}\n"
        f"**Classification:** {classification.value}\n"
        f"**Message:** {message.strip()}\n"
        f"**Agent:** {agent_icon} `{agent}`\n\n"
        f"_Posted automatically by Cloudflare Worker `whatsapp-webhook`._"
    )
    return format_squad_comment(
        body,
        avatar="director",
        repo=repo,
        ref=ref,
    )
