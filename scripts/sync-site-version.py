#!/usr/bin/env python3
"""Sync site/VERSION into static page footers (optionally bump patch before next release)."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_PATH = ROOT / "site/VERSION"
PUBLIC = ROOT / "site/public"
DEFAULT_VERSION = "1.0.0"
VERSION_SPAN = re.compile(
    r'(<span class="site-version">)v[\d.]+(</span>)',
    re.IGNORECASE,
)


def parse_version(raw: str) -> tuple[int, int, int]:
    parts = raw.strip().split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise SystemExit(f"Invalid semver in {VERSION_PATH}: {raw!r}")
    return int(parts[0]), int(parts[1]), int(parts[2])


def bump_patch(version: str) -> str:
    major, minor, patch = parse_version(version)
    return f"{major}.{minor}.{patch + 1}"


def read_version() -> str:
    if not VERSION_PATH.is_file():
        return DEFAULT_VERSION
    return VERSION_PATH.read_text(encoding="utf-8").strip() or DEFAULT_VERSION


def write_version(version: str) -> None:
    VERSION_PATH.write_text(f"{version}\n", encoding="utf-8")


def sync_html(version: str) -> int:
    updated = 0
    for html_path in sorted(PUBLIC.rglob("*.html")):
        html = html_path.read_text(encoding="utf-8")
        if 'class="site-version"' not in html:
            continue
        new_html, count = VERSION_SPAN.subn(rf"\1v{version}\2", html, count=1)
        if count == 0:
            raise SystemExit(f"site-version span not found in {html_path.relative_to(ROOT)}")
        if new_html != html:
            html_path.write_text(new_html, encoding="utf-8")
            updated += 1
            print(f"  {html_path.relative_to(ROOT)} → v{version}")
    return updated


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bump",
        action="store_true",
        help="After syncing footers, increment patch in site/VERSION for the next deploy",
    )
    args = parser.parse_args()

    version = read_version()
    print(f"Syncing site version v{version}")
    updated = sync_html(version)
    if updated == 0:
        print("Footers already up to date")

    if args.bump:
        next_version = bump_patch(version)
        write_version(next_version)
        print(f"Next release version: v{next_version} (saved to {VERSION_PATH.relative_to(ROOT)})")


if __name__ == "__main__":
    main()
