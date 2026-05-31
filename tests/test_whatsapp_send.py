from ai_alpha_squad.whatsapp.send import format_business_analysis_ready, normalize_phone_e164_digits


def test_normalize_phone():
    assert normalize_phone_e164_digits("+13399276695") == "13399276695"


def test_format_business_analysis_ready():
    body = format_business_analysis_ready(
        1,
        "Review and modernize seeker",
        summary="Incremental modernization recommended.",
    )
    assert "#1" in body
    assert "github.com/eduardocerqueira/ai-alpha-squad/issues/1" in body
    assert "APPROVE" in body
    assert "Incremental modernization" in body
