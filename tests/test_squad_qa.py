"""Tests for QA validation and compile-only auto-pass."""

from ai_alpha_squad.squad_qa import (
    artifact_paths_in_changed,
    format_auto_qa_pass_comment,
    is_compile_only_job,
    validate_pr_changed_files,
    validate_qa_report,
)
from ai_alpha_squad.squad_v2 import QA_FAIL_MARKER, QA_PASS_MARKER


def test_validate_qa_pass_ok():
    body = f"""# QA Report

## Criteria
- ✅ Build passes

{QA_PASS_MARKER}
"""
    assert validate_qa_report(body) == "pass"


def test_validate_qa_fail_requires_fix_list():
    body = f"""# QA Report

## Criteria
- ❌ missing file

{QA_FAIL_MARKER}
"""
    assert validate_qa_report(body) is None


def test_validate_qa_fail_with_blockers():
    body = f"""# QA Report

## Criteria
- ❌ compile error

## Fixes required
1. [BLOCKER] src/Foo.java — fix type

{QA_FAIL_MARKER}
"""
    assert validate_qa_report(body) == "fail"


def test_compile_only_job_detected():
    body = """
### Success criteria
- mvn compile succeeds on Java 25
"""
    assert is_compile_only_job(body) is True


def test_compile_only_false_when_package_required():
    body = """
### Success criteria
mvn clean package run successfully
"""
    assert is_compile_only_job(body) is False


def test_validate_pr_rejects_target_only():
    ok, reason = validate_pr_changed_files(
        ("target/classes/x.stapler", "target/maven-status/foo.lst")
    )
    assert not ok
    assert "target/" in reason


def test_validate_pr_accepts_pom_change():
    ok, _ = validate_pr_changed_files(("pom.xml",))
    assert ok


def test_validate_pr_accepts_src_change():
    ok, _ = validate_pr_changed_files(("src/main/java/Foo.java",))
    assert ok


def test_compile_only_false_when_tests_required():
    body = """
### Success criteria
- mvn compile succeeds
- unit tests pass with 80% coverage
"""
    assert is_compile_only_job(body) is False


def test_auto_qa_pass_marker():
    assert QA_PASS_MARKER in format_auto_qa_pass_comment()


def test_artifact_paths_in_pr():
    assert artifact_paths_in_changed(("src/Foo.java", "target/classes/x")) == ("target/classes/x",)
