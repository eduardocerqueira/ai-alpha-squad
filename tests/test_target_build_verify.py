"""Tests for deterministic target-repo build verification."""

from pathlib import Path

from ai_alpha_squad.target_build_verify import (
    detect_build_command,
    format_build_gate_qa_fail,
    issue_expects_build,
    should_verify_build,
)


def test_issue_expects_build_from_compile_criteria():
    body = "### Success criteria\ncompilation success\n"
    assert issue_expects_build(body)


def test_detect_maven_command(tmp_path: Path):
    (tmp_path / "pom.xml").write_text("<project/>", encoding="utf-8")
    cmd = detect_build_command(tmp_path)
    assert cmd is not None
    assert "compile" in " ".join(cmd)


def test_should_verify_when_pom_present(tmp_path: Path):
    (tmp_path / "pom.xml").write_text("<project/>", encoding="utf-8")
    assert should_verify_build(tmp_path, "")


def test_build_gate_qa_fail_marker():
    body = format_build_gate_qa_fail("error: symbol not found")
    assert "squad-v2-qa:fail" in body
    assert "[BLOCKER]" in body
