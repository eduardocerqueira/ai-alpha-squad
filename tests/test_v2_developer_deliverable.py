"""v2 Developer deliverable comment format."""

from ai_alpha_squad.comments import format_v2_developer_deliverable
from ai_alpha_squad.nudge import has_heading_marker


def test_v2_developer_deliverable_heading():
    body = format_v2_developer_deliverable(
        "Implemented hello world samples.",
        pr_url="https://github.com/o/r/pull/2",
        repo="eduardocerqueira/ai-alpha-squad",
    )
    assert has_heading_marker(body, "# Developer Deliverable")
    assert "https://github.com/o/r/pull/2" in body
