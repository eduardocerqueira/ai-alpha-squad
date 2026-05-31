#!/usr/bin/env python3
"""Sync AI Alpha Squad issues to GitHub Project fields for Director visibility."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_alpha_squad.project_sync import Derived, derive_state  # noqa: E402

DEFAULT_OWNER = "eduardocerqueira"
DEFAULT_PROJECT_NUMBER = 6
DEFAULT_REPO = "eduardocerqueira/ai-alpha-squad"

FIELD_LIFECYCLE = "Lifecycle"
FIELD_ACTIVE_AGENT = "Active agent"
FIELD_NEEDS_DIRECTOR = "Needs Director"

LIFECYCLE_OPTIONS = (
    "new",
    "awaiting-approval",
    "director-approved",
    "designed",
    "implemented",
    "validation",
    "release-candidate",
    "released",
    "blocked",
)

ACTIVE_AGENT_OPTIONS = (
    "Director",
    "business-owner",
    "architect",
    "developer",
    "qa",
    "security",
    "devops",
    "tech-writer",
    "release-manager",
    "Done",
    "Blocked",
    "Unassigned",
)

NEEDS_DIRECTOR_OPTIONS = ("Yes", "No")


@dataclass(frozen=True)
class IssueState:
    number: int
    title: str
    state: str
    labels: tuple[str, ...]
    assignees: tuple[str, ...]
    node_id: str


def gh_api(query: str, **variables: object) -> dict:
    payload = {"query": query.strip(), "variables": variables}
    proc = subprocess.run(
        ["gh", "api", "graphql", "--input", "-"],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())
    body = json.loads(proc.stdout)
    if body.get("errors"):
        raise RuntimeError(json.dumps(body["errors"], indent=2))
    return body["data"]


def gh_json(args: list[str]) -> dict | list:
    proc = subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout)


def load_issue(repo: str, issue_number: int) -> IssueState:
    data = gh_json(
        [
            "issue",
            "view",
            str(issue_number),
            "--repo",
            repo,
            "--json",
            "number,title,state,labels,assignees,id",
        ]
    )
    labels = tuple(item["name"] for item in data.get("labels") or [])
    assignees = tuple(item["login"] for item in data.get("assignees") or [])
    return IssueState(
        number=int(data["number"]),
        title=str(data["title"]),
        state=str(data["state"]),
        labels=labels,
        assignees=assignees,
        node_id=str(data["id"]),
    )


def project_query(owner: str, project_number: int) -> dict:
    query = """
    query($login: String!, $number: Int!) {
      user(login: $login) {
        projectV2(number: $number) {
          id
          title
          url
          fields(first: 50) {
            nodes {
              ... on ProjectV2Field { id name }
              ... on ProjectV2SingleSelectField {
                id
                name
                options { id name }
              }
            }
          }
          items(first: 100) {
            nodes {
              id
              content {
                ... on Issue { id number repository { nameWithOwner } }
              }
            }
          }
        }
      }
    }
    """
    return gh_api(query, login=owner, number=project_number)["user"]["projectV2"]


def find_single_select(project: dict, field_name: str) -> dict | None:
    for node in project["fields"]["nodes"]:
        if node.get("name") == field_name and node.get("options") is not None:
            return node
    return None


def create_single_select_field(project_id: str, field_name: str, options: tuple[str, ...]) -> None:
    mutation = """
    mutation($projectId: ID!, $name: String!, $options: [ProjectV2SingleSelectFieldOptionInput!]!) {
      createProjectV2Field(input: {
        projectId: $projectId
        dataType: SINGLE_SELECT
        name: $name
        singleSelectOptions: $options
      }) {
        projectV2Field { ... on ProjectV2SingleSelectField { id name } }
      }
    }
    """
    payload = {
        "query": mutation,
        "variables": {
            "projectId": project_id,
            "name": field_name,
            "options": [{"name": name, "color": "GRAY", "description": ""} for name in options],
        },
    }
    proc = subprocess.run(
        ["gh", "api", "graphql", "--input", "-"],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip())
    body = json.loads(proc.stdout)
    if body.get("errors"):
        raise RuntimeError(json.dumps(body["errors"], indent=2))


def ensure_fields(owner: str, project_number: int) -> dict:
    project = project_query(owner, project_number)
    project_id = project["id"]
    specs = (
        (FIELD_LIFECYCLE, LIFECYCLE_OPTIONS),
        (FIELD_ACTIVE_AGENT, ACTIVE_AGENT_OPTIONS),
        (FIELD_NEEDS_DIRECTOR, NEEDS_DIRECTOR_OPTIONS),
    )
    for field_name, options in specs:
        if find_single_select(project, field_name) is None:
            print(f"Creating project field: {field_name}")
            create_single_select_field(project_id, field_name, options)
    return project_query(owner, project_number)


def option_id(field: dict, option_name: str) -> str:
    for option in field["options"]:
        if option["name"] == option_name:
            return option["id"]
    raise KeyError(f"Option {option_name!r} missing on field {field['name']!r}")


def find_project_item(project: dict, issue_node_id: str) -> dict | None:
    for item in project["items"]["nodes"]:
        content = item.get("content") or {}
        if content.get("id") == issue_node_id:
            return item
    return None


def add_issue_to_project(project_id: str, issue_node_id: str) -> str:
    mutation = """
    mutation($projectId: ID!, $contentId: ID!) {
      addProjectV2ItemById(input: { projectId: $projectId, contentId: $contentId }) {
        item { id }
      }
    }
    """
    data = gh_api(mutation, projectId=project_id, contentId=issue_node_id)
    return data["addProjectV2ItemById"]["item"]["id"]


def set_single_select(
    project_id: str,
    item_id: str,
    field_id: str,
    option_id_value: str,
) -> None:
    mutation = """
    mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) {
      updateProjectV2ItemFieldValue(input: {
        projectId: $projectId
        itemId: $itemId
        fieldId: $fieldId
        value: { singleSelectOptionId: $optionId }
      }) {
        projectV2Item { id }
      }
    }
    """
    gh_api(
        mutation,
        projectId=project_id,
        itemId=item_id,
        fieldId=field_id,
        optionId=option_id_value,
    )


def sync_issue(
    owner: str,
    project_number: int,
    repo: str,
    issue_number: int,
    *,
    ensure_project_item: bool = True,
) -> Derived:
    issue = load_issue(repo, issue_number)
    derived = derive_state(set(issue.labels))
    project = ensure_fields(owner, project_number)
    project_id = project["id"]

    item = find_project_item(project, issue.node_id)
    if item is None:
        if not ensure_project_item:
            raise RuntimeError(f"Issue #{issue_number} is not on project {project_number}")
        print(f"Adding issue #{issue_number} to project")
        item_id = add_issue_to_project(project_id, issue.node_id)
    else:
        item_id = item["id"]

    lifecycle_field = find_single_select(project, FIELD_LIFECYCLE)
    agent_field = find_single_select(project, FIELD_ACTIVE_AGENT)
    director_field = find_single_select(project, FIELD_NEEDS_DIRECTOR)
    if not lifecycle_field or not agent_field or not director_field:
        raise RuntimeError("Project fields missing after ensure_fields")

    if derived.lifecycle:
        set_single_select(
            project_id,
            item_id,
            lifecycle_field["id"],
            option_id(lifecycle_field, derived.lifecycle),
        )
    set_single_select(
        project_id,
        item_id,
        agent_field["id"],
        option_id(agent_field, derived.active_agent),
    )
    set_single_select(
        project_id,
        item_id,
        director_field["id"],
        option_id(director_field, derived.needs_director),
    )
    print(
        f"Synced #{issue_number}: lifecycle={derived.lifecycle or '-'} "
        f"agent={derived.active_agent} needs_director={derived.needs_director}"
    )
    return derived


def sync_all_open(owner: str, project_number: int, repo: str) -> None:
    issues = gh_json(
        [
            "issue",
            "list",
            "--repo",
            repo,
            "--state",
            "open",
            "--json",
            "number",
            "--limit",
            "100",
        ]
    )
    for row in issues:
        sync_issue(owner, project_number, repo, int(row["number"]))


def print_view_setup(owner: str, project_number: int, repo: str) -> None:
    project = project_query(owner, project_number)
    url = project["url"]
    print(
        f"""
Director project board setup
============================
Project: {project['title']} ({url})

One-time UI steps (Project → + New view):

1. **Director inbox** (Table)
   - Filter: `is:issue is:open repo:{repo} label:awaiting-approval,release-candidate,blocked`
   - Sort: Updated (newest first)
   - Columns: Title, Assignees, {FIELD_LIFECYCLE}, {FIELD_ACTIVE_AGENT}, {FIELD_NEEDS_DIRECTOR}, Labels

2. **Pipeline by phase** (Board)
   - Filter: `is:issue is:open repo:{repo}`
   - Group by: {FIELD_LIFECYCLE}
   - Sort: Updated (newest first)

3. **Pipeline by agent** (Board)
   - Filter: `is:issue is:open repo:{repo}`
   - Group by: {FIELD_ACTIVE_AGENT}
   - Sort: Updated (newest first)

4. **Needs you** (Board) — optional narrow view
   - Filter: `is:issue is:open repo:{repo} label:awaiting-approval,release-candidate`
   - Group by: {FIELD_LIFECYCLE}

Run `./scripts/setup-squad-project-board.sh sync-all` after label changes, or rely on the
squad-project-sync workflow.

Requires `gh auth refresh -s read:project,project` for field sync.
"""
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner", default=DEFAULT_OWNER)
    parser.add_argument("--project", type=int, default=DEFAULT_PROJECT_NUMBER)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("ensure-fields", help="Create Lifecycle / Active agent / Needs Director fields")
    sub.add_parser("sync-all", help="Sync all open queue-repo issues to the project")
    sub.add_parser("print-views", help="Print manual view setup instructions")

    sync_one = sub.add_parser("sync-issue", help="Sync one issue to the project")
    sync_one.add_argument("issue", type=int)

    args = parser.parse_args(argv)
    try:
        if args.command == "ensure-fields":
            ensure_fields(args.owner, args.project)
        elif args.command == "sync-all":
            sync_all_open(args.owner, args.project, args.repo)
        elif args.command == "sync-issue":
            sync_issue(args.owner, args.project, args.repo, args.issue)
        elif args.command == "print-views":
            print_view_setup(args.owner, args.project, args.repo)
        else:
            parser.error(f"Unknown command: {args.command}")
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
