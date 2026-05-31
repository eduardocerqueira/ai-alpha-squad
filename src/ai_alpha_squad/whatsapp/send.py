"""Send WhatsApp messages to the Director via Meta Cloud API."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request


def normalize_phone_e164_digits(phone: str) -> str:
    """Meta `to` field: digits only, no leading +."""
    return re.sub(r"\D", "", phone)


def format_business_analysis_ready(
    issue_number: int,
    title: str,
    *,
    summary: str,
    repo: str = "eduardocerqueira/ai-alpha-squad",
) -> str:
    owner, name = repo.split("/", 1) if "/" in repo else ("eduardocerqueira", repo)
    url = f"https://github.com/{owner}/{name}/issues/{issue_number}"
    return (
        "[AI Alpha Squad] Business Analysis ready\n\n"
        f"Issue: #{issue_number} — {title}\n"
        f"{url}\n\n"
        f"Summary: {summary}\n\n"
        "Please reply:\n"
        "• APPROVE — proceed to architecture\n"
        "• REJECT: <reason>\n"
        "• CHANGES: <what to clarify>\n\n"
        "Full report is on the issue."
    )


def send_text_message(
    *,
    phone_number_id: str,
    access_token: str,
    to_phone: str,
    body: str,
    api_version: str = "v21.0",
) -> dict:
    """Send a session text message. Requires open 24h window or prior user message."""
    url = f"https://graph.facebook.com/{api_version}/{phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": normalize_phone_e164_digits(to_phone),
        "type": "text",
        "text": {"body": body},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"WhatsApp send failed {e.code}: {err_body}") from e
