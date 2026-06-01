"""Squad Copilot PR guard — detect disallowed changes on the work-queue repo."""
from __future__ import annotations

import re

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


def pr_looks_like_product_handoff(title: str, body: str) -> bool:
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
