# Squad AI providers

Phase 1 used **GitHub Copilot** only. The orchestrator can now route dispatch to **Copilot** or **Hugging Face Inference Providers** via a single flag.

## Configuration

| Setting | Where | Values |
| ------- | ----- | ------ |
| `SQUAD_AI_PROVIDER` | GitHub Variable or `.env` | `copilot` (default), `huggingface` |
| `HF_TOKEN` | GitHub Secret / `.env` | Required when provider is `huggingface` and `SQUAD_HF_RUN_IN_CI=1` |
| `SQUAD_HF_DEFAULT_MODEL` | GitHub Variable or `.env` | Default HF model if agent has no override |
| `SQUAD_HF_RUN_IN_CI` | GitHub Variable | `1` (default) run inference in Actions; `0` post dispatch comment only |
| `squad-config.yaml` → `ai:` | `.agents/squad-config.yaml` | `provider`, `defaults`, per-agent overrides |

```bash
gh variable set SQUAD_AI_PROVIDER --repo OWNER/ai-alpha-squad --body "huggingface"
gh variable set SQUAD_HF_DEFAULT_MODEL --repo OWNER/ai-alpha-squad --body "meta-llama/Meta-Llama-3.1-8B-Instruct"
gh secret set HF_TOKEN --repo OWNER/ai-alpha-squad
```

## Per-agent model overrides

Add a **## AI Model** section to any `.agents/agent-*.md` file:

```markdown
## AI Model

| Provider | Model |
| -------- | ----- |
| huggingface | `deepseek-ai/DeepSeek-V4-Flash` |
| copilot | _(custom agent profile — no model ID)_ |
```

**Precedence:** agent doc → `squad-config.yaml` `ai.agents.<slug>` → `SQUAD_HF_DEFAULT_MODEL` → built-in default.

### Default Hugging Face models by agent

Models are from the [Hugging Face model hub](https://huggingface.co/models); each agent doc has a **## AI Model** table.

| Agent | HF model | Why |
| ----- | -------- | --- |
| Business Owner | [deepseek-ai/DeepSeek-V4-Flash](https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash) | Business analysis and requirements reasoning |
| Architect | [Qwen/Qwen3.6-27B](https://huggingface.co/Qwen/Qwen3.6-27B) | Long technical specs and FR/BR mapping |
| Developer | [Qwen/Qwen2.5-Coder-32B-Instruct](https://huggingface.co/Qwen/Qwen2.5-Coder-32B-Instruct) | Implementation and code changes |
| QA | [deepseek-ai/DeepSeek-V4-Flash](https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash) | Test planning and QA reports |
| Security | [deepseek-ai/DeepSeek-V4-Flash](https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash) | Threat modeling and security reports |
| DevOps | [Qwen/Qwen2.5-Coder-32B-Instruct](https://huggingface.co/Qwen/Qwen2.5-Coder-32B-Instruct) | CI/CD, YAML, and automation |
| Tech Writer | [meta-llama/Meta-Llama-3.3-70B-Instruct](https://huggingface.co/meta-llama/Meta-Llama-3.3-70B-Instruct) | Documentation and release notes |
| Release Manager | [deepseek-ai/DeepSeek-V4-Flash](https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash) | Release plans and validation summaries |

## Runtime behavior

| Provider | Dispatch | Best for |
| -------- | -------- | -------- |
| **copilot** | Assigns `copilot-swe-agent[bot]` + custom agent; branch/PR on target repo | Developer implementation, DevOps PRs, repo edits |
| **huggingface** | Posts dispatch comment; optional CI calls [HF router](https://router.huggingface.co/v1/chat/completions) and posts deliverable markdown on the issue | Planning text (BA, tech spec), QA/security **reports** on issues |

**Recommendation:** Keep `developer` and `devops` on **Copilot** when work requires cloning, commits, and PRs. Use **Hugging Face** for issue-first planning and validation reports.

## Scripts

| Script | Role |
| ------ | ---- |
| `scripts/squad-dispatch-agent.sh` | Router (`SQUAD_AI_PROVIDER`) |
| `scripts/squad-dispatch-copilot.sh` | Lifecycle instructions + Copilot assign |
| `scripts/squad-run-hf-agent.sh` | HF inference + issue comments |
| `python -m ai_alpha_squad.agent_models` | Resolve provider/model (CLI via module) |

Orchestrator workflow: [.github/workflows/squad-orchestrator.yml](../.github/workflows/squad-orchestrator.yml).

### Nix `nix-ai` devshell

The [nix-devshells](https://github.com/eduardocerqueira/nix-devshells/tree/main/flakes/ai) AI flake ships the **`hf`** Hub CLI (`huggingface-hub` 1.x from nixpkgs-unstable). Squad dispatch still only needs **`HF_TOKEN`** and **`SQUAD_AI_PROVIDER=huggingface`**; the CLI is optional for local checks.

```bash
nix-ai
cd ~/git/eduardo/ai-alpha-squad
set -a && source .env && set +a
hf auth whoami   # optional; works when HF_TOKEN is set
./scripts/verify-prerequisites.sh
./scripts/test-hf-integration.sh
# Optional E2E on an issue: ./scripts/test-hf-integration.sh eduardocerqueira/ai-alpha-squad 80 qa
```

Outside `nix-ai`, install `hf` with: `curl -LsSf https://hf.co/cli/install.sh | bash -s` ([HF CLI docs](https://huggingface.co/docs/huggingface_hub/guides/cli)).

## Related

- [agent-runtime-strategy.md](../.agents/agent-runtime-strategy.md)
- [infrastructure-prerequisites.md](../.agents/infrastructure-prerequisites.md)
- [SECRETS_AND_VARIABLES.md](../.github/SECRETS_AND_VARIABLES.md)
