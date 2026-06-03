"""E2E-style pipeline tests for Dev⇄QA (pure logic, no GitHub)."""

from ai_alpha_squad.squad_v2 import (
    IssueView,
    QA_FAIL_MARKER,
    QA_PASS_MARKER,
    auto_qa_pass_body,
    classify_failure_mode,
    latest_qa_verdict,
    latest_trusted_developer_deliverable_index,
    next_action,
    qa_passed,
)


def _valid_qa_pass() -> str:
    return f"# QA Report\n\n## Criteria\n- ✅ ok\n\n{QA_PASS_MARKER}\n"


def _valid_qa_fail() -> str:
    return (
        f"# QA Report\n\n## Criteria\n- ❌ bad\n\n## Fixes required\n"
        f"1. [BLOCKER] src/Foo.java — fix it\n\n{QA_FAIL_MARKER}\n"
    )


def _dev_deliverable(pr: str = "https://github.com/o/r/pull/1") -> str:
    return f"# Developer Deliverable\n\nFixed compile.\n\n**Pull request:** {pr}\n"


def test_compile_only_auto_qa_body():
    body = "### Success criteria\nmvn compile must pass\n"
    assert auto_qa_pass_body(body, build_ok=True) is not None
    assert auto_qa_pass_body(body, build_ok=False) is None


def test_invalid_qa_ignored_for_verdict():
    comments = (
        {"body": _dev_deliverable()},
        {"body": "squad-v2-qa:pass inline without a valid QA Report"},
    )
    assert latest_qa_verdict(comments) == (None, None)


def test_valid_qa_pass_enables_release_path():
    comments = (
        {"body": _dev_deliverable()},
        {"body": _valid_qa_pass()},
    )
    idx, v = latest_qa_verdict(comments)
    assert v == "pass"
    assert qa_passed(comments) is True
    act = next_action(
        IssueView(1, "OPEN", frozenset({"director-approved"}), comments, "https://github.com/o/t")
    )
    assert act.kind == "idle"
    assert "release-candidate" in act.reason or "QA passed" in act.reason


def test_build_fail_after_deliverable_untrusts():
    comments = (
        {"body": _dev_deliverable()},
        {"body": "**Squad developer — build verification failed.**\n\n```\nerr\n```"},
    )
    assert latest_trusted_developer_deliverable_index(comments) is None
    act = next_action(
        IssueView(1, "OPEN", frozenset({"director-approved"}), comments, "https://github.com/o/t")
    )
    assert act.kind == "dispatch"
    assert act.agent == "developer"


def test_failure_mode_stall():
    comments = (
        {
            "body": "**Squad Actions agent result** — developer\n\n"
            "Aborted after 20 turns: read-only churn"
        },
    )
    mode = classify_failure_mode(comments, frozenset())
    assert mode == "stall_abort"


def test_qa_fail_triggers_rework():
    comments = (
        {"body": _dev_deliverable()},
        {"body": _valid_qa_fail()},
    )
    act = next_action(
        IssueView(1, "OPEN", frozenset({"director-approved"}), comments, "https://github.com/o/t")
    )
    assert act.kind == "dispatch"
    assert act.agent == "developer"
