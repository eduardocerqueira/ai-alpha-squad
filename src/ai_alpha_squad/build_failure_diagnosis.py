"""Deterministic diagnosis of Maven/Gradle build logs for squad developer and BA agents."""

from __future__ import annotations

import re
from dataclasses import dataclass

# Java class file major version → JDK major (common LTS + current).
_CLASS_MAJOR_TO_JDK = {
    52: 8,
    55: 11,
    61: 17,
    65: 21,
    69: 25,
}

_TESTS_SUMMARY_RE = re.compile(
    r"Tests run:\s*(\d+)\s*,\s*Failures:\s*(\d+)\s*,\s*Errors:\s*(\d+)",
    re.IGNORECASE,
)
_LICENSE_GOAL_RE = re.compile(r"---\s*license:(\d+\.\d+):process", re.IGNORECASE)
_MAJOR_VERSION_RE = re.compile(r"Unsupported class file major version\s+(\d+)", re.IGNORECASE)
_MISLEADING_TEST_TITLE_RE = re.compile(
    r"\b(tests?\s+(are\s+)?fail(ing|ed)|failing tests?|broken tests?)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class BuildFailureDiagnosis:
    tests_passed: bool | None
    failure_phase: str
    jdk_major: int | None
    license_plugin_version: str | None
    suggested_fixes: tuple[str, ...]
    misleading_test_claim: bool

    def has_actionable_fix(self) -> bool:
        return bool(self.suggested_fixes)


def _jdk_from_class_major(major: int) -> int | None:
    if major in _CLASS_MAJOR_TO_JDK:
        return _CLASS_MAJOR_TO_JDK[major]
    # Approximate for unknown majors (Java 10+ pattern: major = jdk + 44 for recent).
    if major >= 45:
        guess = major - 44
        if 8 <= guess <= 30:
            return guess
    return None


def diagnose_build_log(log: str) -> BuildFailureDiagnosis | None:
    """Parse a Maven/Gradle log excerpt into structured failure context."""
    if not log or not log.strip():
        return None

    tests_passed: bool | None = None
    m = _TESTS_SUMMARY_RE.search(log)
    if m:
        failures, errors = int(m.group(2)), int(m.group(3))
        tests_passed = failures == 0 and errors == 0

    license_ver: str | None = None
    lm = _LICENSE_GOAL_RE.search(log)
    if lm:
        license_ver = lm.group(1)

    jdk_major: int | None = None
    vm = _MAJOR_VERSION_RE.search(log)
    if vm:
        jdk_major = _jdk_from_class_major(int(vm.group(1)))

    failure_phase = ""
    if license_ver and (
        "license" in log.lower()
        or "ProcessMojo" in log
        or "major version" in log.lower()
    ):
        failure_phase = f"license-maven-plugin ({license_ver})"
    elif "BUILD FAILURE" in log or "BUILD FAILURE" in log.upper():
        failure_phase = "maven package/build"
    elif tests_passed is False:
        failure_phase = "unit tests (Surefire)"
    elif tests_passed is True and ("BUILD FAILURE" in log or "Failed to execute goal" in log):
        failure_phase = "post-test Maven goal"

    if not failure_phase and not (tests_passed is not None or jdk_major or license_ver):
        return None

    fixes: list[str] = []
    if tests_passed is True and license_ver:
        fixes.append(
            f"[BLOCKER] pom.xml — Upgrade `com.cloudbees.maven:license-maven-plugin` "
            f"from {license_ver} to **2.4.0+** (1.x Groovy breaks on JDK "
            f"{jdk_major or 25}). Do not commit `target/`."
        )
        fixes.append(
            "Run `mvn clean package` with the JDK version in the issue (e.g. Java 25) "
            "before finish."
        )
    elif jdk_major and license_ver:
        fixes.append(
            f"[BLOCKER] pom.xml — Fix license-maven-plugin for JDK {jdk_major} "
            f"(upgrade plugin to 2.4.0+)."
        )
    elif tests_passed is False:
        fixes.append(
            "[BLOCKER] src/test — Fix failing tests shown in the Surefire summary, "
            "then re-run `mvn clean package`."
        )

    misleading = bool(
        tests_passed is True
        and failure_phase.startswith("license")
        and _MISLEADING_TEST_TITLE_RE.search(log[:2000])
    )

    return BuildFailureDiagnosis(
        tests_passed=tests_passed,
        failure_phase=failure_phase or "build",
        jdk_major=jdk_major,
        license_plugin_version=license_ver,
        suggested_fixes=tuple(fixes),
        misleading_test_claim=misleading,
    )


def diagnose_issue_body(body: str) -> BuildFailureDiagnosis | None:
    """Diagnose from the full issue body (title + pasted logs)."""
    return diagnose_build_log(body or "")


def format_developer_playbook(
    diagnosis: BuildFailureDiagnosis,
    *,
    issue_title: str = "",
) -> str:
    """Concrete first-edit guidance for the developer agent."""
    lines = [
        "## Deterministic root-cause analysis (read before editing)",
        "",
    ]
    if diagnosis.tests_passed is True:
        lines.append(
            "- **Unit tests already pass** (Surefire: Failures: 0). Do not “fix tests”; "
            "the failure is elsewhere in the Maven lifecycle."
        )
    elif diagnosis.tests_passed is False:
        lines.append("- **Unit tests are failing** — fix Surefire failures first.")

    if diagnosis.failure_phase:
        lines.append(f"- **Failure phase:** {diagnosis.failure_phase}")
    if diagnosis.jdk_major:
        lines.append(f"- **JDK context:** class file / runtime points to Java {diagnosis.jdk_major}")

    if diagnosis.misleading_test_claim or (
        issue_title and _MISLEADING_TEST_TITLE_RE.search(issue_title)
        and diagnosis.tests_passed is True
        and "license" in diagnosis.failure_phase
    ):
        lines.append(
            "- **Title mismatch:** the request mentions failing tests, but the log shows "
            "tests passed — treat the license/plugin phase as the real blocker."
        )

    lines.extend(
        [
            "",
            "**Mandatory:**",
            "- Edit `pom.xml` / `src/` only — never commit `target/` or other build output.",
            "- Use the JDK version named in the issue when running Maven.",
        ]
    )

    if diagnosis.suggested_fixes:
        lines.extend(["", "## Suggested fix list (execute in order)", ""])
        for i, fix in enumerate(diagnosis.suggested_fixes, 1):
            lines.append(f"{i}. {fix}")

    return "\n".join(lines)


def format_issue_diagnosis_section(issue_body: str, *, issue_title: str = "") -> str:
    """Section appended to developer/BA instructions when logs are in the issue."""
    diag = diagnose_issue_body(issue_body)
    if not diag or not diag.has_actionable_fix():
        if diag and diag.tests_passed is True and "license" in diag.failure_phase:
            return format_developer_playbook(diag, issue_title=issue_title)
        return ""
    return format_developer_playbook(diag, issue_title=issue_title)


def format_business_owner_log_hints(issue_body: str, *, issue_title: str = "") -> str:
    """Hints for BA so success criteria match the actual failure in pasted logs."""
    diag = diagnose_issue_body(issue_body)
    if not diag:
        return ""
    lines = [
        "",
        "## Build log hints (deterministic — use in Problem Statement & Success Criteria)",
        "",
    ]
    if diag.tests_passed is True and "license" in diag.failure_phase:
        lines.append(
            "- The pasted log shows **tests passed**; failure is at "
            f"**{diag.failure_phase}**, not Surefire."
        )
        lines.append(
            "- Success criteria must require **`mvn clean package`** (not compile-only) "
            f"on **Java {diag.jdk_major or 'version in request'}**."
        )
        lines.append(
            "- Do **not** describe the problem as “tests failing” if Failures: 0 in the log."
        )
    elif diag.tests_passed is False:
        lines.append("- Log shows failing tests — criteria should reference fixing tests + package.")
    if issue_title and _MISLEADING_TEST_TITLE_RE.search(issue_title) and diag.tests_passed is True:
        lines.append(
            "- **Correct the executive summary:** title says tests fail but log shows they pass."
        )
    return "\n".join(lines)


def format_human_fix_hint(issue_body: str) -> str | None:
    """One-line fix hint for needs-human summary."""
    diag = diagnose_issue_body(issue_body)
    if not diag or not diag.suggested_fixes:
        return None
    return diag.suggested_fixes[0].replace("[BLOCKER] ", "")
