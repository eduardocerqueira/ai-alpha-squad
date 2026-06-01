"""Tests for deterministic Squad Actions scaffolds."""

from __future__ import annotations

from ai_alpha_squad.actions_scaffold import (
    apply_vscode_squad_director_scaffold,
    is_greenfield_repo,
)


def test_is_greenfield_readme_only(tmp_path):
    (tmp_path / "README.md").write_text("# Hi", encoding="utf-8")
    assert is_greenfield_repo(tmp_path) is True


def test_is_greenfield_not_when_package_json(tmp_path):
    (tmp_path / "README.md").write_text("# Hi", encoding="utf-8")
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    assert is_greenfield_repo(tmp_path) is False


def test_apply_vscode_scaffold_writes_core_files(tmp_path):
    (tmp_path / "README.md").write_text("# Target", encoding="utf-8")
    paths = apply_vscode_squad_director_scaffold(tmp_path)
    assert "package.json" in paths
    assert (tmp_path / "src/extension.ts").is_file()
    assert (tmp_path / "package.json").read_text(encoding="utf-8").find("squad-director") >= 0
