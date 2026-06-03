"""Deterministic build verification on target product repos (Squad v2 gate)."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from ai_alpha_squad.squad_v2 import QA_FAIL_MARKER, squad_work_branch

_BUILD_CRITERIA_RE = re.compile(
    r"\b(compil\w*|build\s+pass|build\s+succeed|mvn\s|maven|gradle|npm\s+run\s+build)\b",
    re.IGNORECASE,
)
_PR_URL_RE = re.compile(
    r"https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/pull/(\d+)",
)

MAX_LOG_CHARS = 6000
DEFAULT_TIMEOUT_SEC = int(os.environ.get("SQUAD_BUILD_VERIFY_TIMEOUT_SEC", "600"))


def issue_expects_build(body: str) -> bool:
    """True when success criteria likely require a compiling build."""
    text = body or ""
    if _BUILD_CRITERIA_RE.search(text):
        return True
    if re.search(r"\b(success criteria|acceptance criteria)\b", text, re.I) and re.search(
        r"\b(compil|build)\b", text, re.I
    ):
        return True
    return False


def detect_build_command(workdir: Path) -> list[str] | None:
    """Return a compile-only command for the repo, or None if unknown."""
    if (workdir / "pom.xml").is_file():
        mvnw = workdir / "mvnw"
        mvn = shutil.which("mvn")
        if mvnw.is_file():
            return [str(mvnw), "-q", "-DskipTests", "compile"]
        if mvn:
            return [mvn, "-q", "-DskipTests", "compile"]
        return None
    if (workdir / "build.gradle").is_file() or (workdir / "build.gradle.kts").is_file():
        gradlew = workdir / "gradlew"
        if gradlew.is_file():
            return [str(gradlew), "-q", "compileJava"]
        gradle = shutil.which("gradle")
        if gradle:
            return [gradle, "-q", "compileJava"]
        return None
    pkg = workdir / "package.json"
    if pkg.is_file():
        return ["npm", "run", "build", "--if-present"]
    if (workdir / "Makefile").is_file() and shutil.which("make"):
        return ["make", "-k"]
    return None


def run_build_command(workdir: Path, cmd: list[str], *, timeout: int = DEFAULT_TIMEOUT_SEC) -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, f"Build timed out after {timeout}s: {' '.join(cmd)}"
    except FileNotFoundError as exc:
        return False, f"Build tool not found: {exc}"
    out = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        tail = out[-MAX_LOG_CHARS:] if len(out) > MAX_LOG_CHARS else out
        return False, f"Command failed ({proc.returncode}): {' '.join(cmd)}\n\n{tail}"
    return True, out[-2000:] if out else "ok"


def should_verify_build(workdir: Path, issue_body: str = "") -> bool:
    """Run a build check when the repo has a known tool or the issue requires compile."""
    if detect_build_command(workdir) is not None:
        return True
    return issue_expects_build(issue_body)


def verify_workdir(
    workdir: Path,
    *,
    issue_body: str = "",
    force: bool = False,
) -> tuple[bool, str]:
    """Run compile/build in workdir. Skips when no build tool and issue does not require it."""
    if not force and not should_verify_build(workdir, issue_body):
        return True, "skipped (no build tool / not required)"
    cmd = detect_build_command(workdir)
    if cmd is None:
        return False, "No supported build tool detected (pom.xml, Gradle, package.json, Makefile)."
    return run_build_command(workdir, cmd)


def format_build_failure_issue_comment(agent: str, log: str) -> str:
    """Issue comment when the Actions post-loop gate rejects a non-compiling tree."""
    snippet = log.strip()[-MAX_LOG_CHARS:]
    slug = agent.replace("-", " ")
    return (
        f"**Squad {slug} — build verification failed.**\n\n"
        "The tree does not compile; no PR was finalized. Fix the errors below and re-run.\n\n"
        f"```\n{snippet}\n```"
    )


def format_build_gate_qa_fail(log: str) -> str:
    snippet = log.strip()[-MAX_LOG_CHARS:]
    return (
        "# QA Report\n\n"
        "## Criteria\n"
        "- ❌ Deterministic build verification failed (orchestrator gate)\n\n"
        "## Fixes required\n"
        "1. [BLOCKER] project — fix compilation/build errors; log excerpt below.\n\n"
        f"```\n{snippet}\n```\n\n"
        f"{QA_FAIL_MARKER}\n"
    )


def verify_pr_branch(
    target_repo: str,
    branch: str,
    *,
    base_branch: str = "main",
    issue_body: str = "",
) -> tuple[bool, str]:
    """Shallow clone target repo at branch and run build verification."""
    workdir = Path(tempfile.mkdtemp(prefix="squad-build-verify-"))
    try:
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
        origin = (
            f"https://x-access-token:{token}@github.com/{target_repo}.git"
            if token
            else f"https://github.com/{target_repo}.git"
        )
        clone = subprocess.run(
            ["git", "clone", "--depth", "1", "-b", base_branch, origin, str(workdir)],
            capture_output=True,
            text=True,
        )
        if clone.returncode != 0:
            return False, f"clone failed: {clone.stderr or clone.stdout}"
        fetch = subprocess.run(
            ["git", "fetch", "--depth", "1", "origin", f"{branch}:{branch}"],
            cwd=str(workdir),
            capture_output=True,
            text=True,
        )
        if fetch.returncode != 0:
            return False, f"fetch branch {branch}: {fetch.stderr or fetch.stdout}"
        checkout = subprocess.run(
            ["git", "checkout", branch],
            cwd=str(workdir),
            capture_output=True,
            text=True,
        )
        if checkout.returncode != 0:
            return False, f"checkout {branch}: {checkout.stderr or checkout.stdout}"
        return verify_workdir(workdir, issue_body=issue_body)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def gate_pr_before_qa(
    queue_repo: str,
    issue: int,
    target_repo: str,
    *,
    issue_body: str = "",
    post_comment: bool = True,
) -> bool:
    """Verify squad developer PR builds. On failure optionally post QA fail comment."""
    branch = squad_work_branch("developer", issue)
    ok, log = verify_pr_branch(target_repo, branch, issue_body=issue_body)
    if ok:
        return True
    if post_comment:
        from ai_alpha_squad.hf_dispatch import post_issue_comment

        post_issue_comment(queue_repo, issue, format_build_gate_qa_fail(log))
    return False


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print("usage: target_build_verify workdir <path> | gate-pr <queue> <issue> <target>", file=sys.stderr)
        return 2
    if argv[0] == "workdir":
        body = argv[2] if len(argv) > 2 else ""
        ok, log = verify_workdir(Path(argv[1]), issue_body=body, force=True)
        if not ok:
            print(log, file=sys.stderr)
            return 1
        print(log or "ok")
        return 0
    if argv[0] == "gate-pr":
        queue_repo, issue_s, target_repo = argv[1], argv[2], argv[3]
        body = ""
        if len(argv) > 4:
            body = argv[4]
        else:
            try:
                proc = subprocess.run(
                    [
                        "gh",
                        "issue",
                        "view",
                        str(issue_s),
                        "--repo",
                        queue_repo,
                        "--json",
                        "body",
                        "-q",
                        ".body",
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                body = proc.stdout.strip()
            except Exception:
                body = ""
        if gate_pr_before_qa(queue_repo, int(issue_s), target_repo, issue_body=body):
            return 0
        return 1
    print(f"unknown command: {argv[0]}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
