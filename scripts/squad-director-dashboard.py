#!/usr/bin/env python3
"""Generate or serve the Director dashboard (single view of all jobs)."""
from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_alpha_squad.director_dashboard import build_dashboard  # noqa: E402

DEFAULT_JSON = ROOT / "site" / "public" / "director" / "jobs.json"
DIRECTOR_HTML = ROOT / "site" / "public" / "director" / "index.html"


def write_json(path: Path, repo: str) -> None:
    data = build_dashboard(repo).to_json()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {path} ({data['counts']})")


class Handler(BaseHTTPRequestHandler):
    repo: str = "eduardocerqueira/ai-alpha-squad"

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"[dashboard] {self.address_string()} {fmt % args}")

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path in ("/api/jobs", "/api/director/jobs"):
            body = json.dumps(build_dashboard(self.repo).to_json()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        if path in ("/", "/index.html"):
            content = DIRECTOR_HTML.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(content)
            return
        if path.startswith("/assets/") or path.endswith(".css") or path.endswith(".js"):
            file_path = ROOT / "site" / "public" / path.lstrip("/")
            if file_path.is_file():
                ctype = "text/css" if path.endswith(".css") else "application/javascript"
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.end_headers()
                self.wfile.write(file_path.read_bytes())
                return
        self.send_error(404)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.end_headers()


def serve(port: int, repo: str) -> None:
    Handler.repo = repo
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Director dashboard: http://127.0.0.1:{port}/")
    print("Press Ctrl+C to stop.")
    server.serve_forever()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default="eduardocerqueira/ai-alpha-squad")
    parser.add_argument("--write", type=Path, nargs="?", const=DEFAULT_JSON, metavar="PATH")
    parser.add_argument("--serve", type=int, nargs="?", const=8788, metavar="PORT")
    parser.add_argument("--print", action="store_true", help="Print JSON to stdout")
    args = parser.parse_args()

    if args.write is not None:
        write_json(args.write, args.repo)
    if args.print:
        json.dump(build_dashboard(args.repo).to_json(), sys.stdout, indent=2)
        print()
    if args.serve is not None:
        serve(args.serve, args.repo)
    if args.write is None and not args.print and args.serve is None:
        parser.print_help()
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
