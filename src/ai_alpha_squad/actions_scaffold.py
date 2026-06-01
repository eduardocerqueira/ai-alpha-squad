"""Deterministic greenfield scaffolds for Squad Actions agent (no LLM required)."""

from __future__ import annotations

from pathlib import Path

_SKIP_NAMES = frozenset({".git"})


def is_greenfield_repo(workdir: Path) -> bool:
    """True when the clone has no implementation files (README-only or empty)."""
    workdir = workdir.resolve()
    entries = [
        p
        for p in workdir.iterdir()
        if p.name not in _SKIP_NAMES and not p.name.startswith(".")
    ]
    if not entries:
        return True
    if len(entries) == 1 and entries[0].name == "README.md" and entries[0].is_file():
        return True
    return False


def _write(workdir: Path, rel: str, content: str) -> str:
    path = workdir / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return rel


def apply_vscode_squad_director_scaffold(workdir: Path) -> list[str]:
    """
    Minimal compilable VS Code extension for Job 1 (Squad Director v1).
    See docs/jobs/job-1-vscode-squad-director.md.
    """
    written: list[str] = []

    written.append(
        _write(
            workdir,
            "package.json",
            """{
  "name": "squad-director",
  "displayName": "Squad Director",
  "description": "AI Alpha Squad Director console — queue, lifecycle, approvals",
  "version": "0.0.1",
  "publisher": "eduardocerqueira",
  "engines": { "vscode": "^1.85.0" },
  "categories": ["Other"],
  "activationEvents": ["onStartupFinished"],
  "main": "./out/extension.js",
  "contributes": {
    "viewsContainers": {
      "activitybar": [
        {
          "id": "squad-director",
          "title": "Squad",
          "icon": "media/icon.svg"
        }
      ]
    },
    "views": {
      "squad-director": [
        {
          "id": "squadDirector.queue",
          "name": "Queue"
        }
      ]
    },
    "commands": [
      {
        "command": "squadDirector.refresh",
        "title": "Squad: Refresh Queue",
        "icon": "$(refresh)"
      },
      {
        "command": "squadDirector.signIn",
        "title": "Squad: Sign in with GitHub"
      }
    ],
    "configuration": {
      "title": "Squad Director",
      "properties": {
        "squadDirector.queueRepo": {
          "type": "string",
          "default": "eduardocerqueira/ai-alpha-squad",
          "description": "Queue repository (owner/name)"
        }
      }
    }
  },
  "scripts": {
    "compile": "tsc -p ./",
    "lint": "eslint src --ext ts",
    "vscode:prepublish": "npm run compile",
    "package": "vsce package --no-dependencies"
  },
  "devDependencies": {
    "@types/node": "^20.14.0",
    "@types/vscode": "^1.85.0",
    "@typescript-eslint/eslint-plugin": "^7.18.0",
    "@typescript-eslint/parser": "^7.18.0",
    "@vscode/test-electron": "^2.4.0",
    "eslint": "^8.57.0",
    "typescript": "^5.5.0",
    "@vscode/vsce": "^3.2.0"
  }
}
""",
        )
    )

    written.append(
        _write(
            workdir,
            "tsconfig.json",
            """{
  "compilerOptions": {
    "module": "commonjs",
    "target": "ES2022",
    "outDir": "out",
    "lib": ["ES2022"],
    "sourceMap": true,
    "rootDir": "src",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true
  },
  "exclude": ["node_modules", ".vscode-test"]
}
""",
        )
    )

    written.append(
        _write(
            workdir,
            ".vscodeignore",
            """.vscode/**
.vscode-test/**
src/**
.gitignore
tsconfig.json
**/*.map
**/*.ts
node_modules/**
""",
        )
    )

    written.append(
        _write(
            workdir,
            ".gitignore",
            """out
node_modules
.vscode-test
*.vsix
.DS_Store
""",
        )
    )

    written.append(
        _write(
            workdir,
            ".eslintrc.json",
            """{
  "root": true,
  "parser": "@typescript-eslint/parser",
  "parserOptions": { "ecmaVersion": 2022, "sourceType": "module" },
  "plugins": ["@typescript-eslint"],
  "extends": ["eslint:recommended", "plugin:@typescript-eslint/recommended"],
  "ignorePatterns": ["out", "node_modules"],
  "rules": { "@typescript-eslint/naming-convention": "off" }
}
""",
        )
    )

    written.append(
        _write(
            workdir,
            "media/icon.svg",
            """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#0078d4">
  <circle cx="12" cy="12" r="9"/>
</svg>
""",
        )
    )

    written.append(
        _write(
            workdir,
            "src/extension.ts",
            """import * as vscode from 'vscode';

const QUEUE_REPO_KEY = 'squadDirector.queueRepo';

export function activate(context: vscode.ExtensionContext): void {
  const provider = new SquadQueueProvider();
  vscode.window.registerTreeDataProvider('squadDirector.queue', provider);

  context.subscriptions.push(
    vscode.commands.registerCommand('squadDirector.refresh', () => provider.refresh()),
    vscode.commands.registerCommand('squadDirector.signIn', async () => {
      await vscode.authentication.getSession('github', ['read:user', 'repo'], {
        createIfNone: true,
      });
      void vscode.window.showInformationMessage('Squad Director: signed in with GitHub');
      provider.refresh();
    }),
  );

  void provider.refresh();
}

class SquadQueueProvider implements vscode.TreeDataProvider<vscode.TreeItem> {
  private readonly onDidChangeTreeDataEmitter = new vscode.EventEmitter<void>();
  readonly onDidChangeTreeData = this.onDidChangeTreeDataEmitter.event;

  refresh(): void {
    this.onDidChangeTreeDataEmitter.fire();
  }

  getTreeItem(element: vscode.TreeItem): vscode.TreeItem {
    return element;
  }

  getChildren(): vscode.ProviderResult<vscode.TreeItem[]> {
    const repo = vscode.workspace.getConfiguration().get<string>(QUEUE_REPO_KEY)
      ?? 'eduardocerqueira/ai-alpha-squad';
    const root = new vscode.TreeItem(`Queue: ${repo}`, vscode.TreeItemCollapsibleState.Expanded);
    root.contextValue = 'squadQueueRoot';

    const needsYou = section('Needs you', 'awaiting-approval, release-candidate');
    const intake = section('Intake / analysis', 'new, business-owner');
    const build = section('Build', 'director-approved, designed, implemented');
    const validation = section('Validation', 'validation');
    const done = section('Done / blocked', 'released, blocked');

    return [root, needsYou, intake, build, validation, done];
  }
}

function section(label: string, subtitle: string): vscode.TreeItem {
  const item = new vscode.TreeItem(label, vscode.TreeItemCollapsibleState.Collapsed);
  item.description = subtitle;
  item.contextValue = 'squadSection';
  return item;
}

export function deactivate(): void {}
""",
        )
    )

    written.append(
        _write(
            workdir,
            "src/github.ts",
            """import * as vscode from 'vscode';

/** Placeholder for GitHub queue API — wired in follow-up iterations. */
export async function getGitHubSession(): Promise<vscode.AuthenticationSession | undefined> {
  return vscode.authentication.getSession('github', ['read:user', 'repo'], {
    createIfNone: false,
  });
}
""",
        )
    )

    written.append(
        _write(
            workdir,
            ".github/workflows/ci.yml",
            """name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
      - run: npm install
      - run: npm run compile
      - run: npm run lint
""",
        )
    )

    readme = workdir / "README.md"
    note = """

## Squad Director (v1 scaffold)

Automated greenfield scaffold from [AI Alpha Squad](https://github.com/eduardocerqueira/ai-alpha-squad) Job 1.
Run `npm install && npm run compile` locally; use **Squad: Sign in with GitHub** from the command palette.
"""
    if readme.is_file():
        text = readme.read_text(encoding="utf-8")
        if "Squad Director (v1 scaffold)" not in text:
            readme.write_text(text.rstrip() + note, encoding="utf-8")
            written.append("README.md")
    else:
        written.append(_write(workdir, "README.md", f"# Squad Director\n{note}"))

    return written
