import pytest

from ai_alpha_squad.comments import (
    format_dispatch_comment,
    format_squad_comment,
    icon_url,
    normalize_agent_slug,
)


def test_normalize_agent_slug_aliases() -> None:
    assert normalize_agent_slug("business_owner") == "business-owner"
    assert normalize_agent_slug("Architect") == "architect"


def test_icon_url() -> None:
    url = icon_url("architect", repo="eduardocerqueira/ai-alpha-squad", ref="main")
    assert url.endswith("/assets/agents/architect.svg")
    assert "raw.githubusercontent.com" in url


def test_format_dispatch_comment_includes_avatars() -> None:
    body = format_dispatch_comment("architect", "approved")
    assert "<table>" in body
    assert "orchestrator.svg" in body
    assert "architect.svg" in body
    assert "**Squad orchestrator**" in body
    assert "`architect`" in body
    assert "`approved`" in body


def test_format_squad_comment_unknown_slug() -> None:
    with pytest.raises(ValueError, match="Unknown agent"):
        format_squad_comment("hello", avatar="not-a-role")


def test_format_audit_comment_has_director_avatar() -> None:
    from ai_alpha_squad.whatsapp.classify import format_audit_comment
    from ai_alpha_squad.whatsapp import DirectorReplyIntent

    body = format_audit_comment(
        received_at="2026-05-31T12:00:00Z",
        classification=DirectorReplyIntent.APPROVE,
        message="APPROVE",
        agent="business-owner",
    )
    assert "director.svg" in body
    assert "business-owner.svg" in body
    assert "## Director response (WhatsApp)" in body
