"""Parse compiler/build logs into structured fix-list items for the developer agent."""

from __future__ import annotations

import re
from dataclasses import dataclass

# Maven: [ERROR] /path/File.java:[62,8] message
_MAVEN_ERROR = re.compile(
    r"\[ERROR\]\s+(?:(?:\/)?(?:[\w.-]+\/)*([\w.-]+\.(?:java|kt|scala|groovy))):?\[(\d+)[^\]]*\]\s*(.+)",
    re.IGNORECASE,
)
# Gradle: /path/File.java:62: error: message
_GRADLE_ERROR = re.compile(
    r"(?:(?:\/)?(?:[\w.-]+\/)*([\w.-]+\.(?:java|kt|scala))):(\d+):\s*(?:error|warning):\s*(.+)",
    re.IGNORECASE,
)
# npm/tsc: src/file.ts(12,5): error TS2345: message
_TSC_ERROR = re.compile(
    r"([\w./-]+\.(?:tsx?|jsx?))\((\d+),\d+\):\s*error\s+TS\d+:\s*(.+)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CompileDiagnostic:
    file: str
    line: int | None
    message: str

    def blocker_line(self) -> str:
        loc = f"{self.file}:{self.line}" if self.line else self.file
        msg = self.message.strip()[:200]
        return f"[BLOCKER] {loc} — {msg}"


def parse_compile_diagnostics(log: str, *, limit: int = 12) -> tuple[CompileDiagnostic, ...]:
    """Extract unique file/line errors from a build log."""
    if not log:
        return ()
    seen: set[tuple[str, int | None, str]] = set()
    out: list[CompileDiagnostic] = []
    for line in log.splitlines():
        line = line.strip()
        if not line:
            continue
        for pattern in (_MAVEN_ERROR, _GRADLE_ERROR, _TSC_ERROR):
            m = pattern.search(line)
            if not m:
                continue
            path, line_s, msg = m.group(1), m.group(2), m.group(3)
            line_no = int(line_s) if line_s.isdigit() else None
            key = (path, line_no, msg.strip()[:120])
            if key in seen:
                continue
            seen.add(key)
            out.append(CompileDiagnostic(path, line_no, msg.strip()))
            if len(out) >= limit:
                return tuple(out)
    return tuple(out)


def format_compile_fix_list(log: str) -> str:
    """Numbered BLOCKER list for developer instructions."""
    items = parse_compile_diagnostics(log)
    if not items:
        return ""
    lines = ["## Parsed compile errors (fix in order)", ""]
    for i, d in enumerate(items, 1):
        lines.append(f"{i}. {d.blocker_line()}")
    return "\n".join(lines)
