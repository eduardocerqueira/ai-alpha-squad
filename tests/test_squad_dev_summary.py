"""Tests for developer summary sanitization."""

from ai_alpha_squad.squad_dev_summary import is_stall_abort_summary, sanitize_developer_summary


def test_sanitize_abort_when_build_ok():
    raw = "Aborted after 96 turns: stalling without edits"
    out = sanitize_developer_summary(raw, build_verified=True, pr_url="https://github.com/o/r/pull/3")
    assert "Build verified" in out
    assert "pull/3" in out
    assert "Aborted" not in out


def test_sanitize_keeps_normal_summary():
    raw = "Changed Foo.java to fix compile."
    assert sanitize_developer_summary(raw, build_verified=True) == raw


def test_is_stall_abort():
    assert is_stall_abort_summary("Aborted after 14 read-only turns")
    assert not is_stall_abort_summary("Implemented feature")
