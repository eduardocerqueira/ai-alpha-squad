"""Regression checks for DevOps validation instructions and templates."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_devops_agent_requires_release_readiness_artifacts() -> None:
    text = read(".github/agents/devops.agent.md")

    assert ".agents/templates/runbook-template.md" in text
    assert ".agents/templates/pull-request-template.md" in text
    assert "technical spec" in text.lower()
    assert "Do not merge to production without Director approval." in text


def test_validation_dispatch_devops_instructions_cover_cicd_hardening() -> None:
    text = read("scripts/squad-dispatch-validation.sh")

    assert ".agents/templates/runbook-template.md" in text
    assert ".agents/templates/pull-request-template.md" in text
    assert "Verify default GITHUB_TOKEN permissions/config" in text
    assert "Comment summary + deliverable links on parent" in text
    assert "rollback/runbook notes" in text
    assert "Do not merge to production without Director approval" in text


def test_deployment_checklist_tracks_traceability_and_schedules() -> None:
    text = read(".agents/templates/deployment-checklist-template.md")

    assert "| Sub-issue       | #     |" in text
    assert "| Technical Specification | Link |" in text
    assert "| Runbook / rollback notes | Link |" in text
    assert "GITHUB_TOKEN`/environment permissions" in text
    assert "Scheduled jobs enabled and next run verified" in text
    assert "## Operational Notes" in text


def test_secrets_reference_documents_github_token_usage() -> None:
    text = read(".github/SECRETS_AND_VARIABLES.md")

    assert "## Workflow token guidance" in text
    assert "Do **not** store it as a repository secret." in text
    assert "Verify each workflow's `permissions:` block" in text
    assert "Use `SQUAD_ORCHESTRATOR_TOKEN` only" in text
