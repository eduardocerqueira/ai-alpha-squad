#!/usr/bin/env python3
"""Embed squad-flow.svg into about/index.html (run before landing deploy)."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SVG_PATH = ROOT / "site/public/assets/images/squad-flow.svg"
ABOUT_PATH = ROOT / "site/public/about/index.html"
MARKER_START = "    <!-- FLOW-DIAGRAM-START -->"
MARKER_END = "    <!-- FLOW-DIAGRAM-END -->"


def main() -> None:
    svg = SVG_PATH.read_text(encoding="utf-8").strip()
    if 'class="flow-diagram"' not in svg:
        svg = svg.replace("<svg ", '<svg class="flow-diagram" ', 1)

    block = f"{MARKER_START}\n    <figure class=\"flow-wrap\">\n      {svg}\n    </figure>\n{MARKER_END}"
    html = ABOUT_PATH.read_text(encoding="utf-8")
    pattern = re.compile(
        re.escape(MARKER_START) + r".*?" + re.escape(MARKER_END),
        re.DOTALL,
    )
    if not pattern.search(html):
        raise SystemExit(f"Markers not found in {ABOUT_PATH}")
    ABOUT_PATH.write_text(pattern.sub(block, html, count=1), encoding="utf-8")
    print(f"Embedded {SVG_PATH.name} into {ABOUT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
