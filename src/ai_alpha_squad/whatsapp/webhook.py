"""Meta WhatsApp webhook verification helpers."""


def verify_meta_webhook(
    *,
    mode: str | None,
    verify_token: str | None,
    challenge: str | None,
    expected_verify_token: str,
) -> str | None:
    """
    Handle Meta webhook subscription verification (GET).

    Returns hub.challenge when valid; otherwise None.
    """
    if mode != "subscribe" or not verify_token or not challenge:
        return None
    if verify_token != expected_verify_token:
        return None
    return challenge
