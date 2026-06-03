"""QA validation, compile-only auto-pass, and deterministic pre-checks (Squad v2)."""

from __future__ import annotations

import re

from ai_alpha_squad.squad_v2 import QA_FAIL_MARKER, QA_PASS_MARKER

_QA_REPORT_HEADING = re.compile(r"#\s*QA Report\b", re.IGNORECASE)
_FIX_ITEM_RE = re.compile(
    r"^\s*\d+\.\s*\[(BLOCKER|REQUIRED|NICE)\]\s*.+",
    re.IGNORECASE | re.MULTILINE,
)
_VERDICT_LINE_RE = re.compile(
    rf"^\s*({re.escape(QA_PASS_MARKER)}|{re.escape(QA_FAIL_MARKER)})\s*$",
    re.MULTILINE,
)

# Success criteria that require HF judgment — not compile-only.
_SUBJECTIVE_CRITERIA_RE = re.compile(
    r"\b("
    r"e2e|end[- ]to[- ]end|integration test|unit tests?|test coverage|"
    r"ui\b|ux\b|design|accessibility|performance|latency|"
    r"every file|all files|each file|all existing|"
    r"behavior|functional|user story|screenshot|"
    r"documentation|readme must|security audit"
    r")\b",
    re.IGNORECASE,
)

_ARTIFACT_PATH_RE = re.compile(r"^target/", re.MULTILINE)


def is_compile_only_job(issue_body: str) -> bool:
    """True when success criteria are build/compile focused (no subjective QA needed)."""
    from ai_alpha_squad.target_build_verify import issue_expects_build, issue_requires_package

    body = issue_body or ""
    if not issue_expects_build(body):
        return False
    if issue_requires_package(body):
        return False
    # Focus on the success criteria section when present.
    section = body
    m = re.search(r"(?i)(success criteria|acceptance criteria)\s*:?\s*\n([\s\S]*)", body)
    if m:
        section = m.group(2)[:4000]
    if _SUBJECTIVE_CRITERIA_RE.search(section):
        return False
    return True


def validate_qa_report(body: str) -> str | None:
    """Return 'pass', 'fail', or None when the report is invalid / not a QA report."""
    text = body or ""
    if not _QA_REPORT_HEADING.search(text):
        return None
    lower = text.lower()
    if QA_PASS_MARKER not in lower and QA_FAIL_MARKER not in lower:
        return None
    if not _VERDICT_LINE_RE.search(text):
        return None
    verdict = "fail" if QA_FAIL_MARKER in lower else "pass"
    if verdict == "fail":
        if "## fixes required" not in lower:
            return None
        if not _FIX_ITEM_RE.search(text):
            return None
    return verdict


def format_auto_qa_pass_comment(*, build_ok: bool = True, compile_only: bool = True) -> str:
    lines = [
        "# QA Report",
        "",
        "## Criteria",
        "- ✅ Build verification (deterministic gate): PR branch compiles",
    ]
    if compile_only:
        lines.append("- ✅ Compile-only job: no subjective criteria require HF review")
    lines.extend(
        [
            "",
            "## Automated review",
            "Deterministic QA — build gate passed on the developer PR branch; "
            "HF QA skipped for this compile-focused job.",
            "",
            QA_PASS_MARKER,
        ]
    )
    return "\n".join(lines)


def format_qa_prechecks_section(
    *,
    build_ok: bool,
    build_log_excerpt: str = "",
    changed_files: tuple[str, ...] = (),
    artifact_paths_in_pr: tuple[str, ...] = (),
) -> str:
    lines = ["## Deterministic pre-checks (orchestrator)", ""]
    lines.append(
        f"- Build gate on PR branch: {'✅ passed' if build_ok else '❌ failed — do not pass QA'}"
    )
    if changed_files:
        lines.append(f"- Files changed in PR: {len(changed_files)}")
        for p in changed_files[:20]:
            lines.append(f"  - `{p}`")
        if len(changed_files) > 20:
            lines.append(f"  - … and {len(changed_files) - 20} more")
    if artifact_paths_in_pr:
        lines.append(
            f"- ⚠️ Build artifacts in PR (should fail): {', '.join(artifact_paths_in_pr[:8])}"
        )
    if not build_ok and build_log_excerpt.strip():
        lines.extend(["", "### Build log excerpt", "```", build_log_excerpt.strip()[-3000:], "```"])
    return "\n".join(lines)


def artifact_paths_in_changed(changed_files: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(p for p in changed_files if p.startswith("target/") or "/target/" in p)


_MEANINGFUL_CHANGE_PATHS = (
    "src/",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "package.json",
    "Makefile",
    "README",
    "docs/",
)


def validate_pr_changed_files(changed_files: tuple[str, ...]) -> tuple[bool, str]:
    """Reject PRs that only touch build artifacts or have no changes."""
    if not changed_files:
        return False, "PR has no file changes — deliver a source or build-config fix."
    if all(p.startswith("target/") or "/target/" in p for p in changed_files):
        return (
            False,
            "PR only modifies build artifacts (target/) — commit source or pom.xml changes, "
            "not Maven output.",
        )
    if not any(
        p == prefix.rstrip("/") or p.startswith(prefix)
        for p in changed_files
        for prefix in _MEANINGFUL_CHANGE_PATHS
    ):
        return (
            False,
            "PR has no meaningful source or build-config changes (expected src/, pom.xml, etc.).",
        )
    return True, ""
