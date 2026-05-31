---
name: whatsapp-director
description: "AI Alpha Squad — send WhatsApp messages to the Director and classify inbound replies. Use when Business Owner needs approval on Business Analysis, or Release Manager needs release approval or status updates. Requires whatsapp-cloud-api or integrate-whatsapp for API calls. GitHub Issues stay the source of truth."
---

# WhatsApp Director Channel (AI Alpha Squad)

Read the full protocol: [../../whatsapp-director-channel.md](../../whatsapp-director-channel.md).

## When to use

| Agent | Trigger |
| ----- | ------- |
| Business Owner | Label `awaiting-approval` added; need Director decision on BA |
| Release Manager | Status `release-candidate`; deployment notification; rollback/incident alert |

Do **not** use for technical design, code review, or Security/DevOps topics — use GitHub only.

## Prerequisites

- `WHATSAPP_DIRECTOR_PHONE` set (E.164)
- Sending credentials configured (`WHATSAPP_ACCESS_TOKEN` + `WHATSAPP_PHONE_NUMBER_ID`, or Kapso CLI logged in)
- Parent issue number known

Load API skills as needed:

- **Meta Cloud API:** `whatsapp-cloud-api`
- **Kapso:** `integrate-whatsapp` (send), `observe-whatsapp` (delivery/debug)

## Outbound templates

### Business Owner — analysis ready

```
[AI Alpha Squad] Business Analysis ready

Issue: #<N> — <title>
Repo: https://github.com/eduardocerqueira/ai-alpha-squad/issues/<N>

Summary: <1-2 sentences>

Please reply:
• APPROVE — proceed to architecture
• REJECT: <reason>
• CHANGES: <what to clarify>

Full report is on the issue.
```

### Release Manager — release candidate

```
[AI Alpha Squad] Release candidate

Issue: #<N>
Version: <X.Y.Z>
Planned: <date/window>

Gates: QA ✓ Security ✓ DevOps ✓ Docs ✓

Reply APPROVE to release or REJECT: <reason>
Details: https://github.com/eduardocerqueira/ai-alpha-squad/issues/<N>
```

### Release Manager — deployed

```
[AI Alpha Squad] Released <version>

Issue: #<N>
Status: deployed / monitoring

Reply if you need rollback or have concerns.
```

## Inbound reply handling

1. Normalize text: trim, lowercase for matching.
2. Classify using [whatsapp-director-channel.md](../../whatsapp-director-channel.md) table.
3. Post audit comment on issue (required format in protocol doc).
4. Update labels:
   - Business Owner + **Approve** → add `director-approved`, remove `awaiting-approval` if policy says so
   - **Reject** → comment, notify on issue, do not add `director-approved`
   - **Changes** → list questions on issue, keep `awaiting-approval`
5. If ambiguous, send one WhatsApp follow-up:

```
Please reply with one of:
APPROVE
REJECT: <reason>
CHANGES: <detail>
```

## Multi-turn understanding

Director replies may be conversational. Extract intent:

- Approval with conditions → classify **Changes**, copy conditions to issue
- Multiple questions → **Changes**, numbered list on issue
- Emoji-only (👍, ✅) → **Approve** if prior message asked for APPROVE/REJECT/CHANGES
- Voice notes → transcribe if tooling available; else ask Director to type APPROVE/REJECT/CHANGES

Never treat WhatsApp approval as sufficient without the audit comment on GitHub.

## Errors

| Problem | Action |
| ------- | ------ |
| Send failed | Log on issue; retry once; use `observe-whatsapp` if Kapso |
| Wrong number | Stop; verify `WHATSAPP_DIRECTOR_PHONE` |
| Director reply with no issue context | Ask which issue # in WhatsApp and on GitHub |

## Security

- Never send API tokens in WhatsApp messages
- Verify inbound `from` matches `WHATSAPP_DIRECTOR_PHONE` before auto-applying labels
- Ignore WhatsApp from unknown numbers (log to issue as security note)
