#!/usr/bin/env bash
# Install or restore project skills for AI Alpha Squad (Cursor).
# Prefer lock file when present; otherwise installs the default set.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
AGENT="${AGENT:-cursor}"

if [[ -f skills-lock.json ]]; then
  echo "Restoring from skills-lock.json..."
  npx skills experimental_install -y --agent "$AGENT"
  exit 0
fi

echo "No skills-lock.json — installing default skill set..."
install() { npx skills add "$1" --agent "$AGENT" -y; }

install s-hiraoku/vscode-sidebar-terminal@vscode-extension-expert
install wshobson/agents@typescript-advanced-types
install github/awesome-copilot@refactor
install github/awesome-copilot@review-and-refactor
install mattpocock/skills@request-refactor-plan
install avdlee/swiftui-agent-skill@swiftui-expert-skill
install jmsktm/claude-settings@appstore-readiness
install sickn33/antigravity-awesome-skills@game-development
install xixu-me/skills@github-actions-docs
install wshobson/agents@changelog-automation
install currents-dev/playwright-best-practices-skill@playwright-best-practices
install huggingface/skills@hf-cli

for skill in wrangler workers-best-practices agents-sdk cloudflare durable-objects sandbox-sdk web-perf; do
  npx skills add cloudflare/skills --skill "$skill" --agent "$AGENT" -y
done

install vercel-labs/skills@find-skills
install gokapso/agent-skills@integrate-whatsapp
install gokapso/agent-skills@observe-whatsapp
install bellopushon/whatsapp-cloud-api@whatsapp-cloud-api

# whatsapp-director is squad-local: .agents/skills/whatsapp-director/ (no npx install)

echo "Done. List: npx skills ls"
