from ai_alpha_squad.whatsapp import verify_meta_webhook


def test_verify_meta_webhook_success() -> None:
    assert (
        verify_meta_webhook(
            mode="subscribe",
            verify_token="my-secret",
            challenge="12345",
            expected_verify_token="my-secret",
        )
        == "12345"
    )


def test_verify_meta_webhook_wrong_token() -> None:
    assert (
        verify_meta_webhook(
            mode="subscribe",
            verify_token="wrong",
            challenge="12345",
            expected_verify_token="my-secret",
        )
        is None
    )


def test_verify_meta_webhook_missing_params() -> None:
    assert (
        verify_meta_webhook(
            mode=None,
            verify_token="my-secret",
            challenge="12345",
            expected_verify_token="my-secret",
        )
        is None
    )
