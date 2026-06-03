# Squad AI providers

The squad uses **GitHub Actions** as the runner and **Hugging Face Inference Providers** for models. **GitHub Copilot coding agent** is legacy optional (`SQUAD_CODE_RUNTIME=copilot`).

Tracked in [issue #85](https://github.com/eduardocerqueira/ai-alpha-squad/issues/85).

## Configuration

| Setting | Where | Values |
| ------- | ----- | ------ |
| `SQUAD_AI_PROVIDER` | GitHub Variable or `.env` | `huggingface` (recommended), `copilot` (legacy) |
| `SQUAD_CODE_RUNTIME` | GitHub Variable or `.env` | `actions` (default with HF), `copilot` (legacy assign API) |
| `HF_TOKEN` | GitHub Secret / `.env` | Required for HF planning + Actions coding loop |
| `SQUAD_HF_DEFAULT_MODEL` | GitHub Variable or `.env` | Default HF model if agent has no override |
| `SQUAD_HF_RUN_IN_CI` | GitHub Variable | `1` run HF inference in Actions; `0` dispatch comment only |
| `SQUAD_HF_PROVIDER_POLICY` | GitHub Variable / `.env` | `cheapest` (default), `fastest`, `preferred`, or `none` — appended to model id as `:cheapest` etc. on [HF router](https://router.huggingface.co/v1/chat/completions) requests |
| `SQUAD_HF_ARCHITECT_SUBISSUES` | Env | `1` (default) create sub-issues after Architect HF run |
| `SQUAD_DEV_MODEL_LADDER` | GitHub Variable / `site/wrangler.jsonc` | Comma-separated HF models for **developer**; first model is the default, escalates after QA rejects or stall aborts. Default: `Qwen/Qwen3-Coder-480B-A35B-Instruct`, then `deepseek-ai/DeepSeek-V4-Pro`, … — see [HF models](https://huggingface.co/models) for coding-capable options. |
| `squad-config.yaml` → `ai:` | `.agents/squad-config.yaml` | `provider`, `code_runtime`, per-agent overrides |

```bash
gh variable set SQUAD_AI_PROVIDER --repo OWNER/ai-alpha-squad --body "huggingface"
gh variable set SQUAD_CODE_RUNTIME --repo OWNER/ai-alpha-squad --body "actions"
gh variable set SQUAD_HF_DEFAULT_MODEL --repo OWNER/ai-alpha-squad --body "meta-llama/Meta-Llama-3.1-8B-Instruct"
gh secret set HF_TOKEN --repo OWNER/ai-alpha-squad
```

## Per-agent dispatch

`resolve_dispatch_mode(agent)` in `agent_models.py`:

| Agent roles | Mode when `SQUAD_CODE_RUNTIME=actions` |
| ----------- | -------------------------------------- |
| business-owner, architect, qa, security, tech-writer, release-manager | **hf** — issue comment deliverables |
| developer, devops | **actions** — clone target repo, HF tool loop, PR |

## Runtime behavior

| Mode | Dispatch | Best for |
| ---- | -------- | -------- |
| **hf** | `hf_dispatch` → [HF router](https://router.huggingface.co/v1/chat/completions) with `:cheapest` routing by default | BA, tech spec, QA/security reports |
| **actions** | `squad-actions-agent.yml` + tool loop | Implementation PRs on target repo |
| **copilot** (legacy) | `copilot-swe-agent[bot]` assign | Deprecated |

Architect: after HF tech spec, `ensure_architect_subissues` creates validation sub-issues (no `gh` from the model).

### Build-log diagnosis (developer / BA)

When a request pastes Maven logs, `build_failure_diagnosis.py` parses Surefire vs plugin phases (e.g. license-maven-plugin on JDK 25) and injects a **deterministic fix list** into developer dispatch instructions and BA hints — so models are not misled by titles like “tests failing” when `Failures: 0`. Gates still require `mvn package` when criteria say so and reject `target/`-only PRs.

## Scripts

| Script | Role |
| ------ | ---- |
| `scripts/squad-dispatch-agent.sh` | Lifecycle dispatch entry |
| `scripts/squad-dispatch-subissue.sh` | Per-agent router (hf / actions / copilot) |
| `scripts/squad-run-hf-agent.sh` | HF inference + issue comments |
| `scripts/squad-run-actions-agent.sh` | Coding agent + PR |
| `scripts/squad-build-actions-instructions.sh` | Developer/DevOps instructions |
| `scripts/test-hf-integration.sh` | HF smoke tests |
| `scripts/test-actions-agent-integration.sh` | Actions routing smoke tests |

Workflows: [squad-orchestrator.yml](../.github/workflows/squad-orchestrator.yml), [squad-actions-agent.yml](../.github/workflows/squad-actions-agent.yml).

### Local checks

```bash
set -a && source .env && set +a
./scripts/verify-prerequisites.sh
./scripts/test-hf-integration.sh
./scripts/test-actions-agent-integration.sh
```

## Related

- [agent-runtime-strategy.md](../.agents/agent-runtime-strategy.md)
- [infrastructure-prerequisites.md](../.agents/infrastructure-prerequisites.md)
- [SECRETS_AND_VARIABLES.md](../.github/SECRETS_AND_VARIABLES.md)
