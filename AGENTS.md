# AI Alpha Squad

Agent documentation, governance, and templates: [.agents/README.md](.agents/README.md).

Before any task, read [.agents/squad-orchestrator.md](.agents/squad-orchestrator.md).

**Domain skills** (VS Code extensions, SwiftUI/App Store, refactor, Cloudflare, CI, HF): [.agents/skills/README.md](.agents/skills/README.md). Restore with `npx skills experimental_install -y --agent cursor` or `./.agents/skills-install.sh`.

**Director WhatsApp** (Business Owner + Release Manager): [.agents/whatsapp-director-channel.md](.agents/whatsapp-director-channel.md) and skill `whatsapp-director`.

**Infrastructure & credentials** (Director setup before first job): [.agents/infrastructure-prerequisites.md](.agents/infrastructure-prerequisites.md) — copy [.env.example](.env.example), run `./scripts/verify-prerequisites.sh`.

**Cloud agents (autonomous, no local machine):** [.agents/agent-runtime-strategy.md](.agents/agent-runtime-strategy.md) — GitHub Actions + Hugging Face ([docs/agent-ai-providers.md](docs/agent-ai-providers.md)); Copilot is legacy optional.
