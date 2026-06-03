"""Tests for deterministic target-repo build verification."""

from pathlib import Path

from ai_alpha_squad.target_build_verify import (
    detect_build_command,
    format_build_failure_issue_comment,
    format_build_gate_qa_fail,
    issue_expects_build,
    issue_requires_package,
    jdk_version_from_issue,
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


def test_detect_maven_package_when_criteria_require(tmp_path: Path):
    (tmp_path / "pom.xml").write_text("<project/>", encoding="utf-8")
    body = "### Success criteria\nmvn clean package run successfully\n"
    cmd = detect_build_command(tmp_path, body)
    assert cmd is not None
    assert "package" in " ".join(cmd)


def test_jdk_version_from_issue():
    assert jdk_version_from_issue("running with java 25, mvn clean package fails") == "25"
    assert jdk_version_from_issue("JDK 21") == "21"
    assert jdk_version_from_issue("no java here") is None
    body = "### Success criteria\nmvn clean package run successfully\n"
    assert issue_requires_package(body)
    assert not issue_requires_package("### Success criteria\nmvn compile succeeds\n")


def test_should_verify_when_pom_present(tmp_path: Path):
    (tmp_path / "pom.xml").write_text("<project/>", encoding="utf-8")
    assert should_verify_build(tmp_path, "")


def test_build_gate_qa_fail_marker():
    body = format_build_gate_qa_fail("error: symbol not found")
    assert "squad-v2-qa:fail" in body
    assert "[BLOCKER]" in body


def test_build_failure_issue_comment_includes_log():
    body = format_build_failure_issue_comment("developer", "cannot find symbol: AbstractBuild")
    assert "build verification failed" in body.lower()
    assert "AbstractBuild" in body
