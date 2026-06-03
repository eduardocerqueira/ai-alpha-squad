"""Tests for deterministic build log diagnosis (issue #180 class failures)."""

from pathlib import Path

from ai_alpha_squad.build_failure_diagnosis import (
    diagnose_build_log,
    diagnose_issue_body,
    format_business_owner_log_hints,
    format_developer_playbook,
    format_human_fix_hint,
    format_issue_diagnosis_section,
)

_LOG_SNIPPET = """
[INFO] Tests run: 4, Failures: 0, Errors: 0, Skipped: 0
[INFO] --- license:1.15:process (default) @ random-quote ---
Unsupported class file major version 69
at com.cloudbees.maven.license.ProcessMojo.execute
"""


def test_diagnose_license_plugin_jdk25():
    diag = diagnose_build_log(_LOG_SNIPPET)
    assert diag is not None
    assert diag.tests_passed is True
    assert "license" in diag.failure_phase
    assert diag.jdk_major == 25
    assert diag.license_plugin_version == "1.15"
    assert any("pom.xml" in f for f in diag.suggested_fixes)


def test_developer_playbook_warns_title_mismatch():
    diag = diagnose_build_log(_LOG_SNIPPET)
    text = format_developer_playbook(
        diag, issue_title="tests are failing and breaking mvn clean package"
    )
    assert "tests already pass" in text.lower() or "do not" in text.lower()
    assert "pom.xml" in text
    assert "target/" in text


def test_issue_diagnosis_section_from_upload():
    upload = Path(__file__).resolve().parents[1]
    # Minimal inline body matching #180
    body = "[Request]: tests are failing\n" + _LOG_SNIPPET
    section = format_issue_diagnosis_section(body, issue_title="tests are failing")
    assert "root-cause" in section.lower()
    assert "license" in section.lower()


def test_business_owner_hints():
    body = "tests failing\n" + _LOG_SNIPPET
    hints = format_business_owner_log_hints(body, issue_title="tests failing")
    assert "tests passed" in hints.lower()
    assert "mvn clean package" in hints


def test_human_fix_hint():
    hint = format_human_fix_hint(_LOG_SNIPPET)
    assert hint is not None
    assert "license-maven-plugin" in hint.lower() or "pom.xml" in hint


def test_diagnose_issue_body_same_as_log():
    assert diagnose_issue_body(_LOG_SNIPPET) == diagnose_build_log(_LOG_SNIPPET)
