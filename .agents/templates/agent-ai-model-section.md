# Template: Agent AI Model section

Paste under the agent **GitHub Label** section in `.agents/agent-<slug>.md`.

```markdown
## AI Model

Per-provider overrides (optional). When unset, defaults apply (`SQUAD_HF_DEFAULT_MODEL`, `squad-config.yaml`).

| Provider | Model |
| -------- | ----- |
| huggingface | `org/model-id` |
| copilot | _(custom agent profile — no model ID)_ |
```

List form also works:

```markdown
## AI Model

- **huggingface:** `org/model-id`
```

See [docs/agent-ai-providers.md](../../docs/agent-ai-providers.md).
