#!/usr/bin/env python3
"""CLI: format a squad GitHub issue comment with agent avatar(s)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_alpha_squad.comments import (  # noqa: E402
    format_dispatch_comment,
    format_dispatch_fallback_comment,
    format_orchestrator_notice,
    format_squad_comment,
)


def main() -> int:
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument("--repo", default=None, help="owner/name for icon URLs")
    parent.add_argument("--ref", default=None, help="git ref (default: main)")

    parser = argparse.ArgumentParser(description=__doc__, parents=[parent])
    sub = parser.add_subparsers(dest="cmd", required=True)

    dispatch = sub.add_parser("dispatch", parents=[parent], help="Copilot assign success comment")
    dispatch.add_argument("agent")
    dispatch.add_argument("label")

    fallback = sub.add_parser("fallback", parents=[parent], help="Copilot assign failed comment")
    fallback.add_argument("agent")
    fallback.add_argument("--instructions-file", required=True)

    notice = sub.add_parser("notice", parents=[parent], help="Generic orchestrator notice")
    notice.add_argument("--message", required=True)

    custom = sub.add_parser("comment", parents=[parent], help="Arbitrary message with avatar")
    custom.add_argument("--avatar", required=True)
    custom.add_argument("--message", required=True)

    args = parser.parse_args()
    repo, ref = args.repo, args.ref

    if args.cmd == "dispatch":
        body = format_dispatch_comment(args.agent, args.label, repo=repo, ref=ref)
    elif args.cmd == "fallback":
        instructions = Path(args.instructions_file).read_text()
        body = format_dispatch_fallback_comment(
            args.agent, instructions, repo=repo, ref=ref
        )
    elif args.cmd == "notice":
        body = format_orchestrator_notice(args.message, repo=repo, ref=ref)
    else:
        body = format_squad_comment(args.message, avatar=args.avatar, repo=repo, ref=ref)

    print(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
