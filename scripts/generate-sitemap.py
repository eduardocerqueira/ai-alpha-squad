#!/usr/bin/env python3
"""Generate site/public/sitemap.xml from static pages (run before landing deploy)."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "site/public"
OUT = PUBLIC / "sitemap.xml"
BASE = "https://aialphasquad.com"

# url_path, source file (relative to PUBLIC), changefreq, priority, optional image metadata
ENTRIES: list[tuple[str, str, str, str, dict[str, str] | None]] = [
    ("/", "index.html", "weekly", "1.0", None),
    (
        "/about/",
        "about/index.html",
        "monthly",
        "0.9",
        {
            "loc": f"{BASE}/assets/images/squad-flow.svg",
            "title": "AI Alpha Squad delivery flow",
            "caption": "Director intake through autonomous agents to target repository release.",
        },
    ),
    ("/contact/", "contact/index.html", "monthly", "0.7", None),
    ("/llms.txt", "llms.txt", "weekly", "0.6", None),
]


def lastmod(relative: str) -> str:
    path = PUBLIC / relative
    ts = path.stat().st_mtime
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def render_url(
    loc: str,
    source: str,
    changefreq: str,
    priority: str,
    image: dict[str, str] | None,
) -> str:
    lines = [
        "  <url>",
        f"    <loc>{loc}</loc>",
        f"    <lastmod>{lastmod(source)}</lastmod>",
        f"    <changefreq>{changefreq}</changefreq>",
        f"    <priority>{priority}</priority>",
    ]
    if image:
        lines.extend(
            [
                "    <image:image>",
                f"      <image:loc>{image['loc']}</image:loc>",
                f"      <image:title>{image['title']}</image:title>",
                f"      <image:caption>{image['caption']}</image:caption>",
                "    </image:image>",
            ]
        )
    lines.append("  </url>")
    return "\n".join(lines)


def main() -> None:
    urls = []
    for url_path, source, changefreq, priority, image in ENTRIES:
        if not (PUBLIC / source).is_file():
            raise SystemExit(f"Missing source for sitemap entry: {PUBLIC / source}")
        loc = f"{BASE}/" if url_path == "/" else f"{BASE}{url_path}"
        urls.append(render_url(loc, source, changefreq, priority, image))

    xml = "\n".join(
        [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"',
            '        xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">',
            *urls,
            "</urlset>",
            "",
        ]
    )
    OUT.write_text(xml, encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)} ({len(ENTRIES)} URLs)")


if __name__ == "__main__":
    main()
