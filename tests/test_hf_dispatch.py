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
