import pytest

from ai_alpha_squad.whatsapp import DirectorReplyIntent, classify_director_reply
from ai_alpha_squad.whatsapp.classify import format_audit_comment


@pytest.mark.parametrize(
    "text,expected",
    [
        ("APPROVE", DirectorReplyIntent.APPROVE),
        ("approved", DirectorReplyIntent.APPROVE),
        ("Yes, LGTM — go ahead", DirectorReplyIntent.APPROVE),
        ("ok to release", DirectorReplyIntent.APPROVE),
        ("👍", DirectorReplyIntent.APPROVE),
        ("REJECT: scope too large", DirectorReplyIntent.REJECT),
        ("no", DirectorReplyIntent.REJECT),
        ("hold", DirectorReplyIntent.REJECT),
        ("not approved", DirectorReplyIntent.REJECT),
        ("CHANGES: need pricing estimate", DirectorReplyIntent.CHANGES),
        ("please clarify the timeline", DirectorReplyIntent.CHANGES),
        ("revise section 2", DirectorReplyIntent.CHANGES),
        ("maybe?", DirectorReplyIntent.AMBIGUOUS),
        ("", DirectorReplyIntent.AMBIGUOUS),
        ("   ", DirectorReplyIntent.AMBIGUOUS),
    ],
)
def test_classify_director_reply(text: str, expected: DirectorReplyIntent) -> None:
    assert classify_director_reply(text) == expected


def test_format_audit_comment() -> None:
    body = format_audit_comment(
        received_at="2026-05-31T12:00:00Z",
        classification=DirectorReplyIntent.APPROVE,
        message="APPROVE",
        agent="business-owner",
    )
    assert "## Director response (WhatsApp)" in body
    assert "**Classification:** approve" in body
    assert "business-owner" in body
