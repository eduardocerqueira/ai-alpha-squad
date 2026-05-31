# WhatsApp lifecycle notifications

Short, objective WhatsApp messages to the Director on every squad lifecycle step.

## Message format

```
[AI Alpha Squad] <headline>

#N — <issue title>
Now: <what is happening>
Next: <what you or the squad does next>

<github issue url>
```

## When messages are sent

| Trigger | Step key | Who sends |
| ------- | -------- | --------- |
| Label `new` | `new` | Squad orchestrator (Actions) |
| Label `awaiting-approval` | `awaiting-approval` | Squad orchestrator |
| Label `director-approved` | `director-approved` | Squad orchestrator |
| Label `designed` … `blocked` | same as label | Squad orchestrator |
| Copilot assigned | `dispatched-business-owner` / `dispatched-architect` | Squad orchestrator |
| Director WhatsApp APPROVE/REJECT/CHANGES | `inbound-*` | WhatsApp Worker |
| Unauthorized approval label | `unauthorized-approval` | Director gate (Actions) |

## Configuration

Same as [whatsapp-setup.md](whatsapp-setup.md):

| Secret / var | Purpose |
| ------------ | ------- |
| `WHATSAPP_ACCESS_TOKEN` | Send API |
| `WHATSAPP_PHONE_NUMBER_ID` | Send API |
| `WHATSAPP_DIRECTOR_PHONE` | Your E.164 number |

GitHub Actions: set secrets on `ai-alpha-squad`. Worker: redeploy with `./scripts/deploy-whatsapp-webhook.sh` so outbound acks work.

## Manual test

```bash
./scripts/notify-director-lifecycle.sh awaiting-approval 1
./scripts/notify-director-lifecycle.sh dispatched-architect 1
```

Templates live in [`src/ai_alpha_squad/whatsapp/lifecycle.py`](../src/ai_alpha_squad/whatsapp/lifecycle.py).

## Related

- [whatsapp-director-channel.md](../.agents/whatsapp-director-channel.md)
- [director-gate.md](director-gate.md)
