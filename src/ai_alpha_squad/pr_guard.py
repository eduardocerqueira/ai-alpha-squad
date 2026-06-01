"""Squad Copilot PR guard — detect disallowed changes on the work-queue repo."""
from __future__ import annotations

import re
from typing import Iterable

COPILOT_ASSIGNEE_LOGINS = frozenset(
    {
        "copilot",
        "copilot-swe-agent",
        "app/copilot-swe-agent",
        "copilot-swe-agent[bot]",
    }
)

# Paths that are normal on ai-alpha-squad (orchestration, docs, site, Python package).
QUEUE_REPO_ALLOWED_PREFIXES: tuple[str, ...] = (
    ".agents/",
    ".github/",
    "scripts/",
    "docs/",
    "tests/",
    "site/",
    "assets/",
    "workers/",
    "src/ai_alpha_squad/",
    "pyproject.toml",
    "setup.cfg",
    "setup.py",
    "requirements",
    ".env.example",
    "README.md",
    "AGENTS.md",
    "LICENSE",
    ".gitignore",
    ".pre-commit-config.yaml",
)

# File patterns that indicate product / VS Code extension work on the queue repo.
QUEUE_REPO_PRODUCT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^package\.json$"),
    re.compile(r"^package-lock\.json$"),
    re.compile(r"^pnpm-lock\.yaml$"),
    re.compile(r"^tsconfig(\..*)?\.json$"),
    re.compile(r"^vite\.config\.(ts|js|mjs)$"),
    re.compile(r"^webpack\.config\.(ts|js|mjs)$"),
    re.compile(r".*\.vsixmanifest$"),
    re.compile(r"^src/extension\.(ts|js)$"),
    re.compile(r"^src/webviews?/"),
    re.compile(r"^extension/"),
    re.compile(r"^vscode-extension/"),
)

# Title/body hints when diff is empty (draft PR) or incomplete.
PRODUCT_PR_TITLE_RE = re.compile(
    r"(vscode extension|vs code extension|squad director extension|"
    r"open vsx|vsce|extension for github queue)",
    re.IGNORECASE,
)

# Business Owner / Architect planning handoffs often mention the product name — not product PRs.
PLANNING_HANDOFF_RE = re.compile(
    r"(business\s+analysis|technical\s+specification|issue-first|"
    r"planning\s+handoff|ba\.md|tech[-_ ]?spec)",
    re.IGNORECASE,
)
PLANNING_MARKER_HEADING_RE = re.compile(
    r"(?m)^#\s+(Business Analysis|Technical Specification)\s*$",
    re.IGNORECASE,
)


def is_work_queue_repo(repo: str) -> bool:
    return repo.lower().endswith("/ai-alpha-squad") or repo.lower() == "ai-alpha-squad"


def _path_allowed(path: str) -> bool:
    normalized = path.strip().lstrip("./")
    if not normalized:
        return True
    for prefix in QUEUE_REPO_ALLOWED_PREFIXES:
        if normalized == prefix.rstrip("/") or normalized.startswith(prefix):
            return True
    return False


def product_paths_in_diff(paths: list[str]) -> list[str]:
    """Return changed paths that look like product code on the queue repo."""
    flagged: list[str] = []
    for raw in paths:
        path = raw.strip().lstrip("./")
        if not path or _path_allowed(path):
            continue
        if QUEUE_REPO_PRODUCT_PATTERNS and any(p.search(path) for p in QUEUE_REPO_PRODUCT_PATTERNS):
            flagged.append(path)
            continue
        # TypeScript outside site/ and allowed src/ is almost always extension work here.
        if path.endswith((".ts", ".tsx")) and not path.startswith("site/"):
            flagged.append(path)
    return flagged


def pr_looks_like_planning_handoff(title: str, body: str) -> bool:
    """Copilot BO/Architect PR on the queue repo (issue-first), even with empty diff."""
    text = f"{title}\n{body}"
    if PLANNING_MARKER_HEADING_RE.search(text):
        return True
    if re.search(r"(?i)business\s+analysis\s+handoff", title):
        return True
    if re.search(r"(?i)technical\s+specification\s+handoff", title):
        return True
    if "issue-first" in text.lower() and PLANNING_HANDOFF_RE.search(text):
        return True
    # WIP extension implementation titles are product work, not planning.
    if re.search(r"(?i)\[wip\].*(vscode|vs code).*extension", title):
        return False
    return False


def pr_looks_like_product_handoff(title: str, body: str) -> bool:
    if pr_looks_like_planning_handoff(title, body):
        return False
    text = f"{title}\n{body}"
    return bool(PRODUCT_PR_TITLE_RE.search(text))


def should_close_queue_product_pr(
    repo: str,
    *,
    changed_paths: list[str],
    title: str = "",
    body: str = "",
) -> tuple[bool, str]:
    """
    Return (close, reason).

    Product/extension implementation must ship on the target repo, not ai-alpha-squad.
    """
    if not is_work_queue_repo(repo):
        return False, ""

    flagged = product_paths_in_diff(changed_paths)
    if flagged:
        sample = ", ".join(flagged[:5])
        suffix = "…" if len(flagged) > 5 else ""
        return (
            True,
            f"PR changes product/extension paths on the work-queue repo ({sample}{suffix}). "
            "Implementation belongs on the target product repository.",
        )

    if changed_paths and not pr_looks_like_product_handoff(title, body):
        return False, ""

    # Draft PRs may have no diff yet — use title/body heuristics.
    if pr_looks_like_product_handoff(title, body):
        return (
            True,
            "PR title/body indicates VS Code extension implementation on the work-queue repo. "
            "Use the Developer sub-issue and target product repo instead.",
        )

    return False, ""


def is_copilot_assignee(login: str) -> bool:
    return login.strip().lower() in {name.lower() for name in COPILOT_ASSIGNEE_LOGINS}


def issue_numbers_from_pr_text(text: str) -> list[int]:
    """Extract issue numbers from PR title/body (all #N references, in order)."""
    seen: list[int] = []
    for match in re.finditer(
        r"(?:issue|Issue|Fixes|fixes|Closes|closes)[^#]*#\s*(\d+)|#(\d+)",
        text,
    ):
        num = int(match.group(1) or match.group(2))
        if num not in seen:
            seen.append(num)
    return seen


def pick_guard_issue_number(
    closing_numbers: Iterable[int],
    body_numbers: Iterable[int],
    *,
    state_by_number: dict[int, str],
) -> int | None:
    """
    Choose the issue to attach guard actions to.

    Prefer OPEN issues; when several are open, use the highest number (usually the
    current parent job). Never target a closed issue when an open candidate exists.
    """
    candidates: list[int] = []
    for num in list(closing_numbers) + list(body_numbers):
        if num not in candidates:
            candidates.append(num)
    if not candidates:
        return None

    open_issues = [n for n in candidates if state_by_number.get(n) == "OPEN"]
    if open_issues:
        return max(open_issues)
    return None
