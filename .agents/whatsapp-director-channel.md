# WhatsApp — Director Channel

The Director may approve or respond outside GitHub via WhatsApp. **GitHub Issues remain the source of truth**; every WhatsApp exchange must be summarized on the relevant issue within 15 minutes.

## Authorized agents

Only these agents may **send** WhatsApp messages to the Director:

| Agent | Label | When to message |
| ----- | ----- | ---------------- |
| Business Owner | `business-owner` | Business Analysis ready (`awaiting-approval`); clarification needed; scope questions |
| Release Manager | `release-manager` | Release candidate ready; deployment start/complete; rollback or SEV-1/2 incident summary |
| **Orchestrator (Actions)** | lifecycle labels | Every step — see [docs/whatsapp-lifecycle-notify.md](../docs/whatsapp-lifecycle-notify.md) |
| **WhatsApp Worker** | inbound ack | Confirms APPROVE / REJECT / CHANGES received |

No other agent may message the Director on WhatsApp. Other agents escalate through GitHub and mention Business Owner or Release Manager.

## Director contact

Configure via environment (never commit secrets):

| Variable | Description |
| -------- | ----------- |
| `WHATSAPP_DIRECTOR_PHONE` | Director E.164 number (e.g. `+15551234567`) |
| `WHATSAPP_PHONE_NUMBER_ID` | Sending business number ID (Cloud API) |
| `WHATSAPP_ACCESS_TOKEN` | Meta Cloud API token or provider API key |
| `WHATSAPP_WEBHOOK_VERIFY_TOKEN` | Webhook verification (inbound) |
| `WHATSAPP_API_PROVIDER` | `meta` (default) or `kapso` |

Optional Kapso: `KAPSO_API_KEY`, `KAPSO_API_BASE_URL` — see skill `integrate-whatsapp`.

## Outbound message rules

1. **Link the issue** — every message includes `Issue #N` and repo URL.
2. **One clear ask** — approval, rejection, or a numbered question list.
3. **Structured summary** — use the templates in [skills/whatsapp-director/SKILL.md](skills/whatsapp-director/SKILL.md).
4. **No secrets** — no tokens, internal URLs, or customer data in WhatsApp body.
5. **Rate limit** — max 3 proactive messages per issue per day unless Director replies.

## Inbound replies (understanding Director)

When the Director replies on WhatsApp, the handling agent must:

1. Load the skill [whatsapp-director](skills/whatsapp-director/SKILL.md) and apply reply classification below.
2. Post a **verbatim quote** (or webhook payload summary) on the GitHub issue as a comment.
3. Apply GitHub labels/actions that match the intent.

### Reply classification

| Intent | Example phrases (case-insensitive) | GitHub action |
| ------ | ---------------------------------- | ------------- |
| **Approve** | `approved`, `approve`, `yes`, `lgtm`, `go`, `ship it`, `release`, `ok to release` | Business: add `director-approved`, remove `awaiting-approval`. Release: note Director release approval; proceed per release plan |
| **Reject** | `reject`, `rejected`, `no`, `hold`, `stop`, `not approved` | Remove `awaiting-approval` / `release-candidate` if set; comment reason; return to Business Owner or blocked |
| **Changes requested** | `changes`, `revise`, `questions`, `need more`, `clarify` | Comment questions on issue; do not add `director-approved`; stay in current workflow state |
| **Ambiguous** | Short or unclear text | Reply on WhatsApp asking Director to reply with `APPROVE`, `REJECT`, or `CHANGES:` plus detail; do not change labels |

If WhatsApp and GitHub conflict, **GitHub label applied by the Director in the UI wins**; WhatsApp is used to prompt action, not override written issue history without a matching comment.

## Implementation skills

| Skill | Use for |
| ----- | ------- |
| [whatsapp-director](skills/whatsapp-director/SKILL.md) | Squad message templates, classification, agent duties |
| [whatsapp-cloud-api](skills/whatsapp-cloud-api/SKILL.md) | Meta WhatsApp Cloud API send/receive |
| [integrate-whatsapp](skills/integrate-whatsapp/SKILL.md) | Kapso onboarding, webhooks, flows (alternative provider) |
| [observe-whatsapp](skills/observe-whatsapp/SKILL.md) | Delivery failures, webhook retries (Kapso) |

## Webhook requirement (implementation)

Inbound Director messages require a deployed webhook (Worker, API route, or Kapso project webhook) that:

- Verifies signatures
- Maps `from` to `WHATSAPP_DIRECTOR_PHONE`
- Opens or finds the active issue (from last outbound context or issue ID in thread)
- Triggers the Business Owner or Release Manager agent with the message body

Until webhooks exist, agents poll or use manual paste of Director replies into the issue comment and still run classification.

**Director setup guide:** [docs/whatsapp-setup.md](../docs/whatsapp-setup.md). Reply classification is implemented in `src/ai_alpha_squad/whatsapp/` with tests in `tests/test_whatsapp_*.py`.

## Audit

Every approval or rejection via WhatsApp must appear on the issue as:

```
## Director response (WhatsApp)
**Received:** <timestamp>
**Classification:** Approve | Reject | Changes | Ambiguous
**Message:** <quote>
**Agent:** business-owner | release-manager
```
