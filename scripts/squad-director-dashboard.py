#!/usr/bin/env python3
"""Generate or serve the Director dashboard (single view of all jobs).

Local ``--serve`` reads ``site/public/director/jobs.json`` only (zero GitHub API calls).
That file is refreshed by GitHub Actions (``director-dashboard.yml``) every 15 minutes.
Use ``--write`` locally only when you need an immediate snapshot and ``gh`` is available.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_alpha_squad.director_dashboard import (  # noqa: E402
    GhCliError,
    build_dashboard,
    fetch_dashboard_json,
)

DEFAULT_JSON = ROOT / "site" / "public" / "director" / "jobs.json"
DIRECTOR_HTML = ROOT / "site" / "public" / "director" / "index.html"
PUBLIC_ROOT = ROOT / "site" / "public"


def write_json(path: Path, repo: str) -> None:
    try:
        data = build_dashboard(repo).to_json()
    except GhCliError as err:
        print(f"error: {err}", file=sys.stderr)
        if path.is_file():
            print(f"Keeping existing {path} (gh failed)", file=sys.stderr)
            return
        raise SystemExit(1) from err
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {path} ({data['counts']})")


def read_snapshot(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "counts" not in data:
        raise ValueError(f"invalid dashboard file: {path}")
    return data


class Handler(BaseHTTPRequestHandler):
    json_path: Path = DEFAULT_JSON
    live_api: bool = False
    repo: str = "eduardocerqueira/ai-alpha-squad"

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"[dashboard] {self.address_string()} {fmt % args}")

    def _send_json(self, payload: dict, *, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _snapshot_payload(self) -> dict:
        return read_snapshot(self.json_path)

    def _live_payload(self, *, force: bool) -> dict:
        return fetch_dashboard_json(
            self.repo,
            cache_path=self.json_path,
            force_refresh=force,
        )

    def do_GET(self) -> None:
        raw_path = self.path
        path = raw_path.split("?", 1)[0]
        query = raw_path.split("?", 1)[1] if "?" in raw_path else ""
        want_live = self.live_api and "live=1" in query

        if path in ("/api/jobs", "/api/director/jobs", "/director/jobs.json"):
            try:
                if want_live:
                    self._send_json(self._live_payload(force="refresh=1" in query))
                else:
                    self._send_json(self._snapshot_payload())
            except FileNotFoundError:
                self._send_json(
                    {
                        "error": "missing_jobs_json",
                        "fetch_error": (
                            f"No {self.json_path.name} yet. Run: "
                            "./scripts/squad-director-dashboard.py --write "
                            "or git pull (CI updates this file every 15 min)."
                        ),
                        "counts": {
                            "needs_you": 0,
                            "in_progress": 0,
                            "stuck": 0,
                            "completed": 0,
                        },
                        "needs_you": [],
                        "in_progress": [],
                        "stuck": [],
                        "completed": [],
                    },
                    status=404,
                )
            except GhCliError as err:
                try:
                    data = self._snapshot_payload()
                    data["stale"] = True
                    data["fetch_error"] = str(err)
                    self._send_json(data)
                except FileNotFoundError:
                    self.send_error(503, str(err))
            return

        if path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(DIRECTOR_HTML.read_bytes())
            return

        rel = path.lstrip("/")
        if rel.startswith("director/") or rel.startswith("assets/"):
            file_path = PUBLIC_ROOT / rel
            if file_path.is_file():
                if path.endswith(".css"):
                    ctype = "text/css; charset=utf-8"
                elif path.endswith(".js"):
                    ctype = "application/javascript; charset=utf-8"
                elif path.endswith(".json"):
                    ctype = "application/json; charset=utf-8"
                else:
                    ctype = "application/octet-stream"
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.end_headers()
                self.wfile.write(file_path.read_bytes())
                return
        self.send_error(404)


def serve(port: int, repo: str, *, live_api: bool, sync: bool) -> None:
    Handler.repo = repo
    Handler.json_path = DEFAULT_JSON
    Handler.live_api = live_api

    if sync:
        print("Syncing jobs.json from GitHub (one gh call batch)…", file=sys.stderr)
        write_json(DEFAULT_JSON, repo)

    if DEFAULT_JSON.is_file():
        data = read_snapshot(DEFAULT_JSON)
        at = data.get("generated_at", "?")
        print(f"Snapshot: {DEFAULT_JSON} (generated_at={at})")
    else:
        print(f"Missing {DEFAULT_JSON}", file=sys.stderr)
        print(
            "  git pull origin main   # CI commits jobs.json every 15 min\n"
            "  ./scripts/squad-director-dashboard.py --write   # or build locally",
            file=sys.stderr,
        )

    if live_api:
        print("Live GitHub API enabled (?live=1) — may hit rate limits", file=sys.stderr)
    else:
        print("Mode: static snapshot only (no GitHub calls on refresh)")

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Director dashboard: http://127.0.0.1:{port}/")
    print("Press Ctrl+C to stop.")
    server.serve_forever()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default="eduardocerqueira/ai-alpha-squad")
    parser.add_argument("--write", type=Path, nargs="?", const=DEFAULT_JSON, metavar="PATH")
    parser.add_argument("--serve", type=int, nargs="?", const=8788, metavar="PORT")
    parser.add_argument(
        "--sync",
        action="store_true",
        help="With --serve: run --write once before serving (uses gh)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="With --serve: allow ?live=1 to call gh (not recommended)",
    )
    parser.add_argument("--print", action="store_true", help="Print JSON to stdout")
    parser.add_argument(
        "--tick",
        type=int,
        metavar="PARENT_ISSUE",
        help="Run squad-phase-tick for parent job (unblock pipeline)",
    )
    args = parser.parse_args()

    if args.tick is not None:
        tick = ROOT / "scripts" / "squad-phase-tick.sh"
        subprocess.run([str(tick), args.repo, str(args.tick)], cwd=ROOT, check=False)

    if args.write is not None:
        write_json(args.write, args.repo)
    if args.print:
        if DEFAULT_JSON.is_file() and not args.sync:
            json.dump(read_snapshot(DEFAULT_JSON), sys.stdout, indent=2)
        else:
            try:
                json.dump(fetch_dashboard_json(args.repo, cache_path=DEFAULT_JSON), sys.stdout, indent=2)
            except GhCliError as err:
                print(f"error: {err}", file=sys.stderr)
                return 1
        print()
    if args.serve is not None:
        serve(args.serve, args.repo, live_api=args.live, sync=args.sync)
    if args.write is None and not args.print and args.serve is None:
        parser.print_help()
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
