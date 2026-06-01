#!/usr/bin/env bash
# Director status: approvals (you must act) + attention (open jobs squad should advance).
# Usage: squad-director-now.sh [queue_repo]
set -euo pipefail

REPO="${1:-eduardocerqueira/ai-alpha-squad}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"

python3 - "$REPO" <<'PY'
import json
import subprocess
import sys

repo = sys.argv[1]

def gh_json(args: list[str]):
    p = subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
    )
    if p.returncode != 0:
        print(p.stderr or p.stdout or "gh failed", file=sys.stderr)
        sys.exit(1)
    return json.loads(p.stdout)

SUB_PREFIXES = (
    "[Developer]", "[QA]", "[Security]", "[DevOps]", "[Tech Writer]", "Architect:",
)
GATE_LABELS = frozenset({"awaiting-approval", "release-candidate"})
ATTENTION_LABELS = frozenset(
    {"new", "director-approved", "designed", "implemented", "validation", "blocked"}
)


def is_parent(title: str) -> bool:
    t = (title or "").strip()
    return not any(t.startswith(p) for p in SUB_PREFIXES)


def main() -> None:
    rows = gh_json(
        [
            "issue",
            "list",
            "--repo",
            repo,
            "--state",
            "open",
            "--json",
            "number,title,url,labels",
            "--limit",
            "100",
        ]
    )
    parents = [r for r in rows if is_parent(r.get("title") or "")]

    gates = []
    attention = []
    for row in parents:
        labels = {x["name"] for x in row.get("labels") or []}
        line = (row["number"], row["title"], row["url"], labels)
        if labels & GATE_LABELS:
            gates.append(line)
        elif labels & ATTENTION_LABELS:
            attention.append(line)

    print(f"Director — {repo}\n")

    print("═══ 1. YOUR MOVE (reply on GitHub) ═══")
    if not gates:
        print("  (none — no awaiting-approval or release-candidate)\n")
    else:
        for num, title, url, labels in gates:
            gate = sorted(labels & GATE_LABELS)[0]
            action = (
                "Reply APPROVE or REQUEST CHANGES"
                if gate == "awaiting-approval"
                else "Reply APPROVE or REJECT"
            )
            print(f"  #{num} [{gate}] {title}")
            print(f"     → {action}")
            print(f"     {url}\n")

    print("═══ 2. ATTENTION (squad should be working — if idle, pipeline is stuck) ═══")
    if not attention:
        print("  (no open parent jobs in active phases)\n")
    else:
        for num, title, url, labels in attention:
            phase = sorted(labels & ATTENTION_LABELS, key=lambda x: list(ATTENTION_LABELS).index(x) if x in ATTENTION_LABELS else 99)
            phase_s = phase[0] if phase else "?"
            print(f"  #{num} [phase: {phase_s}] {title}")
            print(f"     {url}")
        print()
        print("  If nothing moves for hours: ./scripts/squad-phase-tick.sh", repo, "<parent#>")
        print()

    if not gates and not attention:
        print("All clear — no open squad jobs.")


if __name__ == "__main__":
    main()
PY
