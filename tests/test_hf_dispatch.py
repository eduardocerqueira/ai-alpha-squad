"""Tests for Hugging Face squad dispatch (no live API calls)."""

from __future__ import annotations

import json
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from ai_alpha_squad import hf_dispatch as hd


def test_parse_parent_issue_number():
    body = "| Parent Issue | #64 |\n| Target repo | `org/repo` |"
    assert hd.parse_parent_issue_number(body) == 64
    assert hd.parse_parent_issue_number("see https://github.com/x/issues/64") == 64
    assert hd.parse_parent_issue_number("no parent") is None


def test_hf_run_enabled_defaults_true(monkeypatch):
    monkeypatch.delenv("SQUAD_HF_RUN_IN_CI", raising=False)
    assert hd.hf_run_enabled() is True


@pytest.mark.parametrize("value", ("0", "false", "no", "FALSE"))
def test_hf_run_enabled_disabled(monkeypatch, value):
    monkeypatch.setenv("SQUAD_HF_RUN_IN_CI", value)
    assert hd.hf_run_enabled() is False


@pytest.mark.parametrize(
    ("model", "policy", "expected"),
    [
        ("deepseek-ai/DeepSeek-V4-Flash", "cheapest", "deepseek-ai/DeepSeek-V4-Flash:cheapest"),
        ("org/model", "fastest", "org/model:fastest"),
        ("org/model:cheapest", "cheapest", "org/model:cheapest"),
        ("org/model:groq", "cheapest", "org/model:groq"),
        ("org/model", "none", "org/model"),
    ],
)
def test_router_model_id(monkeypatch, model, policy, expected):
    monkeypatch.setenv("SQUAD_HF_PROVIDER_POLICY", policy)
    assert hd.router_model_id(model) == expected


def test_chat_completion_uses_cheapest_router_model(monkeypatch):
    monkeypatch.setenv("SQUAD_HF_PROVIDER_POLICY", "cheapest")
    captured: dict = {}

    def fake_urlopen(req, timeout=0):
        captured["body"] = json.loads(req.data.decode())
        payload = {"choices": [{"message": {"content": "ok"}}]}
        body = json.dumps(payload).encode("utf-8")

        class FakeResp:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return body

        return FakeResp()

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        hd.chat_completion("meta-llama/Meta-Llama-3.1-8B-Instruct", system="s", user="u", token="t")
    assert captured["body"]["model"] == "meta-llama/Meta-Llama-3.1-8B-Instruct:cheapest"


def test_chat_completion_parses_response():
    payload = {
        "choices": [{"message": {"content": "# Business Analysis\n\nHello"}}],
    }
    body = json.dumps(payload).encode("utf-8")

    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return body

    with patch("urllib.request.urlopen", return_value=FakeResp()):
        out = hd.chat_completion(
            "meta-llama/Meta-Llama-3.1-8B-Instruct",
            system="sys",
            user="user",
            token="tok",
        )
    assert out.startswith("# Business Analysis")


def test_chat_completion_http_error():
    import urllib.error

    err = urllib.error.HTTPError(
        url="https://router.huggingface.co/v1/chat/completions",
        code=401,
        msg="Unauthorized",
        hdrs=None,
        fp=BytesIO(b'{"error":"bad token"}'),
    )
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(RuntimeError, match="HF inference HTTP 401"):
            hd.chat_completion("m", system="s", user="u", token="bad")


def test_chat_completion_402_raises_credits_depleted(monkeypatch):
    """A 402 is billing, not transient: raise the typed error immediately (no retry)."""
    import urllib.error

    monkeypatch.setattr(hd.time, "sleep", lambda *_: None)
    calls = {"n": 0}

    def fake_urlopen(req, timeout=0):
        calls["n"] += 1
        raise urllib.error.HTTPError(
            url="https://router.huggingface.co/v1/chat/completions",
            code=402, msg="Payment Required", hdrs=None,
            fp=BytesIO(b'{"error":"You have depleted your monthly included credits."}'),
        )

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        with pytest.raises(hd.HFCreditsDepletedError, match="depleted your monthly"):
            hd.chat_completion("m", system="s", user="u", token="t")
    assert calls["n"] == 1  # not retried


def test_extract_hf_error_json_and_html():
    assert hd._extract_hf_error('{"error":"boom"}') == "boom"
    assert hd._extract_hf_error('{"error":{"message":"nested boom"}}') == "nested boom"
    out = hd._extract_hf_error("<!doctype html><html><body>Hugging Face</body></html>")
    assert "Hugging Face" in out and "<" not in out


def test_dispatch_comment_only(monkeypatch):
    monkeypatch.setenv("SQUAD_AI_PROVIDER", "huggingface")
    monkeypatch.setenv("SQUAD_HF_RUN_IN_CI", "0")
    posted: list[str] = []

    def fake_post(repo: str, issue: int, body: str) -> None:
        posted.append(body)

    with (
        patch.object(hd, "post_issue_comment", side_effect=fake_post),
        patch.object(hd, "fetch_issue_context") as fetch_ctx,
        patch.object(hd, "chat_completion") as chat,
    ):
        assert hd.dispatch("o/r", 1, "business-owner", "Do BA", label="new") is True
        fetch_ctx.assert_not_called()
        chat.assert_not_called()

    assert len(posted) == 1
    assert "Squad HF agent dispatched" in posted[0]


def test_dispatch_requires_token_when_run_enabled(monkeypatch):
    monkeypatch.setenv("SQUAD_AI_PROVIDER", "huggingface")
    monkeypatch.setenv("SQUAD_HF_RUN_IN_CI", "1")
    monkeypatch.delenv("HF_TOKEN", raising=False)

    with (
        patch.object(hd, "post_issue_comment"),
        patch.object(hd, "fetch_issue_context", return_value="ctx"),
    ):
        with pytest.raises(RuntimeError, match="HF_TOKEN is required"):
            hd.dispatch("o/r", 1, "business-owner", "Do BA")


def test_dispatch_full_run(monkeypatch):
    monkeypatch.setenv("SQUAD_AI_PROVIDER", "huggingface")
    monkeypatch.setenv("SQUAD_HF_RUN_IN_CI", "1")
    monkeypatch.setenv("HF_TOKEN", "hf_test")
    comments: list[str] = []

    with (
        patch.object(hd, "post_issue_comment", side_effect=lambda _r, _i, b: comments.append(b)),
        patch.object(hd, "fetch_issue_context", return_value="# Issue\n\nbody"),
        patch.object(hd, "chat_completion", return_value="# Business Analysis\n\nDone."),
    ):
        assert hd.dispatch("o/r", 42, "business-owner", "Write BA", label="new") is True

    assert len(comments) == 2
    assert "Squad HF agent dispatched" in comments[0]
    assert "Squad HF agent result" in comments[1]
    assert "# Business Analysis" in comments[1]


def _http_error(code):
    import urllib.error
    return urllib.error.HTTPError(
        url="https://router.huggingface.co/v1/chat/completions",
        code=code, msg="err", hdrs=None, fp=BytesIO(b'{"error":"transient"}'),
    )


class _OkResp:
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False
    def read(self):
        return json.dumps({"choices": [{"message": {"content": "ok done"}}]}).encode()


def test_chat_completion_retries_transient_5xx(monkeypatch):
    monkeypatch.setattr(hd.time, "sleep", lambda *_: None)
    calls = {"n": 0}
    def fake_urlopen(req, timeout=0):
        calls["n"] += 1
        if calls["n"] < 3:
            raise _http_error(500)
        return _OkResp()
    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        out = hd.chat_completion("m", system="s", user="u", token="t")
    assert out == "ok done"
    assert calls["n"] == 3  # failed twice, succeeded on the third


def test_chat_completion_gives_up_after_max_attempts(monkeypatch):
    monkeypatch.setattr(hd.time, "sleep", lambda *_: None)
    monkeypatch.setattr(hd, "HF_MAX_ATTEMPTS", 3)
    calls = {"n": 0}
    def fake_urlopen(req, timeout=0):
        calls["n"] += 1
        raise _http_error(503)
    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        with pytest.raises(RuntimeError, match="HF inference HTTP 503"):
            hd.chat_completion("m", system="s", user="u", token="t")
    assert calls["n"] == 3  # exhausted all attempts


def test_chat_completion_does_not_retry_4xx(monkeypatch):
    monkeypatch.setattr(hd.time, "sleep", lambda *_: None)
    calls = {"n": 0}
    def fake_urlopen(req, timeout=0):
        calls["n"] += 1
        raise _http_error(401)
    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        with pytest.raises(RuntimeError, match="HF inference HTTP 401"):
            hd.chat_completion("m", system="s", user="u", token="t")
    assert calls["n"] == 1  # no retry on auth error
