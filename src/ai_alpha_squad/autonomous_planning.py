"""Autonomous planning fallback when Copilot cannot deliver on the issue thread."""
from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from ai_alpha_squad.nudge import (
    NUDGE_MARKER,
    PHASE_MARKERS,
    comment_body,
    has_heading_marker,
    is_substantive_deliverable,
    issue_has_deliverable,
    minutes_since,
)

AUTONOMOUS_MARKER = "Squad autonomous planning"
JOB_PACK_RE = re.compile(
    r"(?:docs/jobs/|blob/main/docs/jobs/)(job[-\w]+\.md)",
    re.IGNORECASE,
)
TARGET_REPO_RE = re.compile(
    r"https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)",
)

ARCHITECT_ROLES = (
    ("developer", "Developer", "Implement Squad Director extension on target repo per tech spec."),
    ("qa", "QA", "Test plan, automated tests, and QA report on Developer sub-issue."),
    ("security", "Security", "Security review and report for the extension."),
    ("devops", "DevOps", "CI/CD, packaging, and deployment checklist for release."),
    ("tech-writer", "Tech Writer", "Release notes and user-facing documentation."),
)


def autonomous_enabled() -> bool:
    return os.environ.get("SQUAD_AUTONOMOUS_PLANNING", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def max_planning_nudges() -> int:
    return int(os.environ.get("SQUAD_MAX_PLANNING_NUDGES", "2"))


def count_planning_nudges(comments: list[dict]) -> int:
    return sum(1 for c in comments if NUDGE_MARKER in comment_body(c))


def resolve_job_pack_path(issue_body: str, repo_root: Path) -> Path | None:
    for match in JOB_PACK_RE.finditer(issue_body):
        candidate = repo_root / "docs" / "jobs" / match.group(1)
        if candidate.is_file():
            return candidate
    if (repo_root / "docs/jobs/job-1-vscode-squad-director.md").is_file():
        if "squad director" in issue_body.lower() or "job 1" in issue_body.lower():
            return repo_root / "docs/jobs/job-1-vscode-squad-director.md"
    return None


def extract_target_repo(issue_body: str) -> str:
    for match in TARGET_REPO_RE.finditer(issue_body):
        repo = match.group(1)
        if "ai-alpha-squad" not in repo.lower():
            return repo
    return "eduardocerqueira/vscode-squad-director"


def _section_after(md: str, heading: str) -> str:
    pattern = re.compile(
        rf"(?ms)^##\s+{re.escape(heading)}\s*\n(.*?)(?=^##\s+|\Z)",
    )
    match = pattern.search(md)
    return match.group(1).strip() if match else ""


def build_business_analysis_from_job_pack(
    job_md: str,
    *,
    issue_number: int,
    issue_title: str,
) -> str:
    summary = _section_after(job_md, "Summary") or issue_title
    context = _section_after(job_md, "Business context") or _section_after(job_md, "Business Context")
    scope_ui = _section_after(job_md, "v1 scope (frozen)") or _section_after(job_md, "v1 scope")
    out_scope = _section_after(job_md, "Out of scope (v1)") or _section_after(job_md, "Out of Scope")
    success = _section_after(job_md, "Success criteria")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    return f"""# Business Analysis

## Metadata

| Field | Value |
| ----- | ----- |
| Parent Issue | #{issue_number} |
| Title | {issue_title} |
| Author | Business Owner (autonomous fallback) |
| Date | {today} |
| Version | 1.0 |
| Status | Awaiting Approval |

## Executive Summary

{summary}

## Problem Statement

### Current Situation

{context.split("**Desired outcome:**")[0].replace("**Current situation:**", "").strip() if context else "Director manages squad jobs outside the IDE."}

### Problem

No in-editor visibility of squad queue, lifecycle phases, or approval gates.

### Impact

Slower approvals and higher context switching for the Director; delays downstream agent phases.

## Business Goals

| ID | Goal |
| -- | ---- |
| G1 | Ship Squad Director extension v1 on Marketplace and Open VSX |
| G2 | Prove end-to-end squad delivery with issue-first governance on the queue repo |

## Stakeholders

| Stakeholder | Role | Interest |
| ----------- | ---- | -------- |
| Director | Primary user | Approve BA, monitor queue, release |
| Squad agents | Indirect | Faster Director gates |

## User Stories

### US-001 — Sign in

**As a** Director  
**I want** to sign in with GitHub inside VS Code  
**So that** the extension can read my squad queue securely  

**Maps to:** BR-001

#### Acceptance Criteria

```gherkin
Given the extension is installed
When I run Squad: Sign in
Then I am authenticated with GitHub and the session is stored in SecretStorage
```

### US-002 — Queue sidebar

**As a** Director  
**I want** issues grouped by lifecycle in the Squad sidebar  
**So that** I see what needs attention without opening the browser  

**Maps to:** BR-002

#### Acceptance Criteria

```gherkin
Given I am signed in
When I open the Squad view
Then issues from the configured queue repo appear in lifecycle groups
```

### US-003 — Status bar

**As a** Director  
**I want** a status bar summary of pending approvals  
**So that** I know when to act without opening the sidebar  

**Maps to:** BR-003

### US-004 — Approve BA

**As a** Director  
**I want** to approve Business Analysis from the extension  
**So that** the architect phase starts without leaving VS Code  

**Maps to:** BR-004

#### Acceptance Criteria

```gherkin
Given an issue has label awaiting-approval
When I use Approve BA as an authorized Director
Then director-approved is applied per director-gate rules
```

## Scope

### In Scope

{scope_ui}

### Out of Scope

{out_scope}

## Assumptions

- Queue repo remains `ai-alpha-squad`; implementation repo is the target product repo.
- Director gates on GitHub remain authoritative for approval and release.

## Risks

| Risk | Impact | Likelihood | Mitigation |
| ---- | ------ | ---------- | ---------- |
| Copilot posts planning on PRs instead of issues | High | Medium | PR guard + autonomous fallback |
| GitHub auth scope too broad | Medium | Low | Fine-grained PAT / session scopes documented in job pack |

## Proposed Solution

Deliver a VS Code extension (Squad Director) that surfaces the squad work queue, lifecycle grouping, and approval actions using GitHub APIs only, with no telemetry.

## Success Metrics

| Metric | Baseline | Target | How measured |
| ------ | -------- | ------ | ------------ |
| Director approval latency | Browser-only | Approve from IDE | Time to director-approved label |
| Queue visibility | None in IDE | Daily use | Director uses sidebar weekly |

## Requirements Register

| ID | Requirement | Priority |
| -- | ----------- | -------- |
| BR-001 | GitHub sign-in via VS Code authentication / SecretStorage | Must |
| BR-002 | Sidebar tree of queue issues grouped by lifecycle | Must |
| BR-003 | Status bar pending approval count | Must |
| BR-004 | Open issue in browser and Approve BA (Director-only) | Must |
| BR-005 | Publish to VS Code Marketplace and Open VSX | Must |
| BR-006 | Target repo CI: compile, lint, test, package .vsix | Must |
| BR-007 | Full squad artifacts on parent issue through lifecycle | Must |

## Approval

| Field | Value |
| ----- | ----- |
| Director decision | Pending |
| Date | {today} |
| Notes | Generated by squad autonomous planning fallback from job pack. |

{success}
"""


def build_technical_specification(
    *,
    issue_number: int,
    issue_title: str,
    target_repo: str,
    job_md: str,
) -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    summary = _section_after(job_md, "Summary") or issue_title
    return f"""# Technical Specification

## Metadata

| Field | Value |
| ----- | ----- |
| Parent Issue | #{issue_number} |
| Business Analysis | Issue #{issue_number} thread |
| Author | Architect (autonomous fallback) |
| Date | {today} |
| Version | 1.0 |
| Status | Draft |

## Overview

Implement **Squad Director** as a VS Code extension in `{target_repo}`: TypeScript extension using `vscode.authentication`, tree view for queue issues by lifecycle, status bar summary, and Director-only approve action. All product code stays off the work-queue repo.

## Business Requirements Mapping

| Requirement | Summary | Technical Solution |
| ----------- | ------- | ------------------ |
| BR-001 | GitHub sign-in | FR-001 Auth module with SecretStorage |
| BR-002 | Sidebar queue | FR-002 TreeDataProvider + GitHub Issues API |
| BR-003 | Status bar | FR-003 StatusBarItem driven by label scan |
| BR-004 | Approve BA | FR-004 Command posts APPROVE / applies director-approved |
| BR-005 | Marketplace ship | FR-005 Packaging, publisher metadata, Open VSX |
| BR-006 | CI quality | FR-006 compile, lint, unit + smoke tests, vsce package |
| BR-007 | Squad artifacts | FR-007 No product changes on queue repo; sub-issues linked |

## Architecture Overview

### Context

Extension runs in VS Code; reads/writes GitHub Issues on configured queue repo via REST API.

### Components

| Component | Responsibility | Technology |
| --------- | -------------- | ---------- |
| AuthService | Session + token storage | vscode.authentication / SecretStorage |
| QueueProvider | Fetch and group issues | GitHub REST |
| ApproveCommand | Director gate integration | gh issue comment / label API |
| Extension entry | activate/deactivate | TypeScript VS Code API |

## Work Breakdown

| FR | Sub-issue role | Target repo |
| -- | -------------- | ----------- |
| FR-003–FR-006 | developer | {target_repo} |
| FR-007 | qa, security, devops, tech-writer | sub-issues on queue repo |

## Testing Strategy

Unit tests for grouping logic; `@vscode/test-electron` smoke test for activation; CI on `{target_repo}`.

## Deployment

DevOps sub-issue owns pipeline; Release Manager handles release-candidate after validation.

## Open Questions

None for v1 — scope frozen in job pack.
"""


def _gh(*args: str) -> None:
    subprocess.run(["gh", *args], check=True)


def post_issue_deliverable(repo: str, issue: int, body: str, phase: str) -> None:
    wrapped = (
        f"**{AUTONOMOUS_MARKER}** — Copilot could not complete issue-first delivery; "
        f"orchestrator posted this {phase} deliverable from the job pack so the squad pipeline "
        "can continue. Director approval gates still apply.\n\n"
        f"{body.strip()}\n"
    )
    _gh("issue", "comment", str(issue), "--repo", repo, "--body", wrapped)


def unassign_copilot(repo: str, issue: int) -> None:
    subprocess.run(
        [
            "gh",
            "issue",
            "edit",
            str(issue),
            "--repo",
            repo,
            "--remove-assignee",
            "Copilot",
        ],
        check=False,
    )


def create_subissue(
    repo: str,
    parent: int,
    role_label: str,
    title: str,
    body: str,
    extra_labels: list[str] | None = None,
) -> int:
    labels = [role_label, "medium"]
    if extra_labels:
        labels.extend(extra_labels)
    proc = subprocess.run(
        [
            "gh",
            "issue",
            "create",
            "--repo",
            repo,
            "--title",
            title,
            "--body",
            body,
            "--label",
            ",".join(labels),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    url = proc.stdout.strip()
    number = int(url.rstrip("/").split("/")[-1])
    return number


def create_architect_subissues(
    repo: str,
    parent: int,
    target_repo: str,
    parent_title: str,
) -> dict[str, int]:
    created: dict[str, int] = {}
    for role, role_title, objective in ARCHITECT_ROLES:
        if role == "developer":
            body = f"""# Sub-Issue: {role_title} — Squad Director extension

## Metadata

| Field | Value |
| ----- | ----- |
| Parent Issue | #{parent} |
| Target repo | {target_repo} |
| Role | {role_title} |

## Objective

{objective}

Parent: https://github.com/{repo}/issues/{parent}
Tech spec: parent issue #{parent}

## Requirements Traceability

| ID | Source | Description |
| -- | ------ | ----------- |
| FR-003 | Tech spec | Core extension UI and commands |
| FR-004 | Tech spec | Approve BA command |
| FR-005 | Tech spec | Packaging and publish prep |
| FR-006 | Tech spec | CI on {target_repo} |
"""
            num = create_subissue(
                repo,
                parent,
                role,
                f"[{role_title}] {parent_title[:60]} — implementation",
                body,
            )
        else:
            body = f"""# Sub-Issue: {role_title} — Squad Director

Parent issue: #{parent}
https://github.com/{repo}/issues/{parent}

## Objective

{objective}
"""
            num = create_subissue(
                repo,
                parent,
                role,
                f"[{role_title}] {parent_title[:50]} — validation",
                body,
            )
        created[role] = num
    return created


def should_run_autonomous_fallback(
    comments: list[dict],
    *,
    has_open_copilot_pr: bool,
    issue_created_at: str | None = None,
    force: bool = False,
) -> bool:
    if not autonomous_enabled():
        return False
    if force:
        return True
    nudges = count_planning_nudges(comments)
    if nudges >= max_planning_nudges():
        return True
    if not has_open_copilot_pr:
        age = minutes_since(issue_created_at)
        if age is not None and age >= 20 and nudges >= 1:
            return True
    return False


def try_autonomous_planning_fallback(
    repo: str,
    issue: int,
    phase: str,
    repo_root: Path,
    *,
    issue_title: str = "",
    issue_body: str = "",
    comments: list[dict] | None = None,
    has_open_copilot_pr: bool = False,
    issue_created_at: str | None = None,
    force: bool = False,
) -> bool:
    """Post planning deliverable and advance labels when Copilot cannot."""
    marker = PHASE_MARKERS.get(phase, "")
    if not marker:
        return False

    if comments is None:
        proc = subprocess.run(
            ["gh", "issue", "view", str(issue), "--repo", repo, "--json", "comments,body,title,createdAt"],
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(proc.stdout)
        comments = data.get("comments", [])
        issue_body = issue_body or data.get("body", "")
        issue_title = issue_title or data.get("title", "")
        issue_created_at = issue_created_at or data.get("createdAt")

    if issue_has_deliverable(comments, marker):
        return True

    if not should_run_autonomous_fallback(
        comments,
        has_open_copilot_pr=has_open_copilot_pr,
        issue_created_at=issue_created_at,
        force=force,
    ):
        return False

    job_path = resolve_job_pack_path(issue_body, repo_root)
    if not job_path:
        print(f"Issue #{issue}: no job pack found for autonomous fallback", flush=True)
        return False

    job_md = job_path.read_text(encoding="utf-8")
    target_repo = extract_target_repo(issue_body)

    if phase == "business-owner":
        ba = build_business_analysis_from_job_pack(
            job_md, issue_number=issue, issue_title=issue_title
        )
        if not is_substantive_deliverable(ba, marker):
            return False
        post_issue_deliverable(repo, issue, ba, "Business Analysis")
        subprocess.run(
            [
                "gh",
                "issue",
                "comment",
                str(issue),
                "--repo",
                repo,
                "--body",
                "Squad deliverable complete on this issue.",
            ],
            check=False,
        )
    elif phase == "architect":
        spec = build_technical_specification(
            issue_number=issue,
            issue_title=issue_title,
            target_repo=target_repo,
            job_md=job_md,
        )
        if not is_substantive_deliverable(spec, marker):
            return False
        post_issue_deliverable(repo, issue, spec, "Technical Specification")
        create_architect_subissues(repo, issue, target_repo, issue_title)
        subprocess.run(
            [
                "gh",
                "issue",
                "comment",
                str(issue),
                "--repo",
                repo,
                "--body",
                "Squad deliverable complete on this issue.",
            ],
            check=False,
        )
    else:
        return False

    unassign_copilot(repo, issue)
    return True
