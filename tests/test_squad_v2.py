"""Tests for minimal squad v2 phase logic."""

from ai_alpha_squad.squad_v2 import (
    IssueView,
    extract_target_repo,
    find_stale_in_progress,
    has_deliverable,
    is_squad_internal_comment,
    next_action,
    run_failures,
    run_in_progress,
)


def test_new_dispatches_business_owner():
    act = next_action(IssueView(1, "OPEN", frozenset({"new"}), (), "Target: https://github.com/o/r"))
    assert act.kind == "dispatch"
    assert act.agent == "business-owner"


def test_awaiting_approval_is_gate():
    act = next_action(
        IssueView(
            1,
            "OPEN",
            frozenset({"awaiting-approval"}),
            ({"body": "# Business Analysis\n\ncontent"},),
            "",
        )
    )
    assert act.kind == "gate"


def test_director_approved_dispatches_developer():
    act = next_action(
        IssueView(
            1,
            "OPEN",
            frozenset({"director-approved"}),
            (),
            "https://github.com/org/target",
        )
    )
    assert act.kind == "dispatch"
    assert act.agent == "developer"


def test_sequential_blocks_second_dispatch():
    comments = ({"body": "squad-v2-run:in_progress:business-owner"},)
    assert run_in_progress(comments) == "business-owner"
    act = next_action(IssueView(1, "OPEN", frozenset({"new"}), comments, ""))
    assert act.kind == "idle"


def test_in_progress_ignored_after_failed_run():
    comments = (
        {"body": "squad-v2-run:in_progress:developer"},
        {"body": "squad-v2-run:failed:developer — timeout"},
    )
    assert run_in_progress(comments) is None


def test_in_progress_active_when_failure_before_latest_marker():
    comments = (
        {"body": "squad-v2-run:failed:developer — old"},
        {"body": "squad-v2-run:in_progress:developer"},
    )
    assert run_in_progress(comments) == "developer"


def test_in_progress_ignored_after_actions_result():
    comments = (
        {"body": "squad-v2-run:in_progress:developer"},
        {
            "body": "**Squad Actions agent result** — developer\n\nAgent loop reached max turns."
        },
    )
    assert run_in_progress(comments) is None
    act = next_action(
        IssueView(
            94,
            "OPEN",
            frozenset({"director-approved"}),
            comments,
            "https://github.com/org/experimental-hello-world",
        )
    )
    assert act.kind == "dispatch"
    assert act.agent == "developer"


def test_squad_work_branch():
    from ai_alpha_squad.squad_v2 import squad_work_branch

    assert squad_work_branch("developer", 94) == "squad/developer-issue-94"


def test_stale_in_progress_ignored_after_deliverable():
    comments = (
        {"body": "squad-v2-run:in_progress:business-owner"},
        {"body": "# Business Analysis\n\n" + "x" * 50},
    )
    assert run_in_progress(comments) is None


def test_ba_detected():
    assert has_deliverable(({"body": "# Business Analysis\n\nx" * 50},), "business-owner")


def test_internal_comment_detection():
    assert is_squad_internal_comment("squad-v2-run:in_progress:developer")
    assert is_squad_internal_comment("**Squad HF agent result** — foo")
    assert is_squad_internal_comment("squad-v2-run:reset:developer — cleared")
    assert not is_squad_internal_comment("approve")


def test_run_failures_counts_all_without_reset():
    comments = (
        {"body": "squad-v2-run:failed:developer — a"},
        {"body": "squad-v2-run:failed:developer — b"},
        {"body": "squad-v2-run:failed:developer — c"},
    )
    assert run_failures(comments, "developer") == 3


def test_reset_marker_clears_failure_count():
    comments = (
        {"body": "squad-v2-run:failed:developer — a"},
        {"body": "squad-v2-run:failed:developer — b"},
        {"body": "squad-v2-run:failed:developer — c"},
        {"body": "squad-v2-run:reset:developer — cleared"},
        {"body": "squad-v2-run:failed:developer — d"},
    )
    assert run_failures(comments, "developer") == 1


def test_reset_all_clears_failure_count():
    comments = (
        {"body": "squad-v2-run:failed:developer — a"},
        {"body": "squad-v2-run:reset:all — fresh start"},
    )
    assert run_failures(comments, "developer") == 0


def test_reset_unblocks_developer_dispatch():
    comments = (
        {"body": "squad-v2-run:failed:developer — 1"},
        {"body": "squad-v2-run:failed:developer — 2"},
        {"body": "squad-v2-run:failed:developer — 3"},
        {"body": "squad-v2-run:reset:developer — cleared"},
    )
    act = next_action(
        IssueView(94, "OPEN", frozenset({"director-approved"}), comments, "https://github.com/o/r")
    )
    assert act.kind == "dispatch"
    assert act.agent == "developer"


def test_retry_limit_blocks_without_reset():
    comments = tuple({"body": "squad-v2-run:failed:developer — x"} for _ in range(3))
    act = next_action(
        IssueView(94, "OPEN", frozenset({"director-approved"}), comments, "https://github.com/o/r")
    )
    assert act.kind == "failed"


def test_find_stale_in_progress_detects_orphaned_run():
    comments = (
        {"body": "squad-v2-run:in_progress:developer", "createdAt": "2026-06-01T10:00:00Z"},
    )
    # 3h later, no terminal marker → stale.
    assert find_stale_in_progress(comments, "2026-06-01T13:00:00Z", 120) == "developer"
    # Only 30m later → still considered live.
    assert find_stale_in_progress(comments, "2026-06-01T10:30:00Z", 120) is None


def test_find_stale_in_progress_ignores_completed_run():
    comments = (
        {"body": "squad-v2-run:in_progress:developer", "createdAt": "2026-06-01T10:00:00Z"},
        {"body": "squad-v2-run:failed:developer — done", "createdAt": "2026-06-01T10:05:00Z"},
    )
    assert find_stale_in_progress(comments, "2026-06-01T20:00:00Z", 120) is None


def test_extract_target_repo_prefers_target_line():
    body = (
        "See related work at https://github.com/some-org/reference-lib\n"
        "Target repo: https://github.com/eduardocerqueira/experimental-hello-world\n"
    )
    assert extract_target_repo(body) == "eduardocerqueira/experimental-hello-world"


def test_extract_target_repo_falls_back_to_first_url():
    body = "Implement here: https://github.com/o/r and reference https://github.com/x/y"
    assert extract_target_repo(body) == "o/r"


def test_extract_target_repo_skips_self():
    body = "Queue: https://github.com/eduardocerqueira/ai-alpha-squad/issues/94"
    assert extract_target_repo(body) is None


def test_developer_deliverable_requires_heading_not_inline_mention():
    ba_plan = (
        "# Business Analysis\n\n"
        "5. Post the PR link as a comment (heading `# Developer Deliverable`).\n"
    )
    assert not has_deliverable(({"body": ba_plan},), "developer")
    assert has_deliverable(
        ({"body": "# Developer Deliverable\n\nPR: https://github.com/o/r/pull/1\n" + "x" * 400},),
        "developer",
    )


# --- QA gate (Developer⇄QA rework loop) ---

_DEV = {"body": "# Developer Deliverable\n\nPR: https://github.com/o/r/pull/1\n" + "x" * 200}


def _dev_approved(comments):
    return IssueView(1, "OPEN", frozenset({"director-approved"}), tuple(comments), "https://github.com/o/r")


def test_qa_dispatched_after_developer_deliverable():
    act = next_action(_dev_approved([_DEV]))
    assert act.kind == "dispatch" and act.agent == "qa"


def test_qa_pass_advances_to_release_candidate():
    comments = [_DEV, {"body": "# QA Report\n\nAll good.\n\nsquad-v2-qa:pass"}]
    act = next_action(_dev_approved(comments))
    assert act.kind == "idle" and "QA passed" in act.reason


def test_qa_fail_redispatches_developer():
    comments = [_DEV, {"body": "# QA Report\n\nGaps.\n\nsquad-v2-qa:fail\n- missing X"}]
    act = next_action(_dev_approved(comments))
    assert act.kind == "dispatch" and act.agent == "developer"
    assert "QA requested changes" in act.reason


def test_qa_reviews_redelivered_work():
    # dev → qa:fail → dev again; QA must review the new deliverable.
    comments = [
        _DEV,
        {"body": "# QA Report\n\nsquad-v2-qa:fail\n- gap"},
        {"body": "# Developer Deliverable\n\nfixed it\n" + "y" * 200},
    ]
    act = next_action(_dev_approved(comments))
    assert act.kind == "dispatch" and act.agent == "qa"


def test_qa_fail_cap_escalates():
    comments = [_DEV]
    for _ in range(3):
        comments.append({"body": "# QA Report\n\nsquad-v2-qa:fail\n- gap"})
        comments.append({"body": "# Developer Deliverable\n\nattempt\n" + "z" * 200})
    # 3 fails recorded; latest is a fresh dev deliverable awaiting QA, but the cap
    # is checked when QA next fails — simulate a 3rd fail as the latest verdict:
    comments.append({"body": "# QA Report\n\nsquad-v2-qa:fail\n- still wrong"})
    act = next_action(_dev_approved(comments))
    assert act.kind == "failed" and "QA rejected" in act.reason


def test_qa_passed_helper():
    from ai_alpha_squad.squad_v2 import qa_passed
    assert qa_passed((_DEV, {"body": "# QA Report\n\nsquad-v2-qa:pass"}))
    assert not qa_passed((_DEV,))
    # pass before the latest dev deliverable doesn't count
    assert not qa_passed((_DEV, {"body": "squad-v2-qa:pass"}, {"body": "# Developer Deliverable\n\nnew\n" + "x"*200}))


def test_qa_markers_are_internal():
    assert is_squad_internal_comment("squad-v2-qa:pass")
    assert is_squad_internal_comment("# QA Report\n\nsquad-v2-qa:fail\n- gap")


# --- developer model-escalation ladder ---

LADDER = ["model-a", "model-b", "model-c"]


def test_dev_model_ladder_parsing():
    from ai_alpha_squad.squad_v2 import dev_model_ladder
    assert dev_model_ladder("a, b ,a,c") == ["a", "b", "c"]
    assert dev_model_ladder("") == []
    assert dev_model_ladder(None) == []


def test_current_and_next_model_base():
    from ai_alpha_squad.squad_v2 import current_dev_model, next_dev_model
    assert current_dev_model((), LADDER) == "model-a"
    assert next_dev_model((), LADDER) == "model-b"


def test_escalation_after_3_fails_dispatches_dev_on_next_model():
    # dev deliverable + 3 QA fails at base tier → escalate (still a dispatch, not failed)
    comments = [_DEV] + [{"body": "squad-v2-qa:fail"} for _ in range(3)]
    act = next_action(_dev_approved(comments), model_ladder=LADDER)
    assert act.kind == "dispatch" and act.agent == "developer"
    assert "escalating developer model to model-b" in act.reason


def test_fails_counted_since_escalation_marker():
    from ai_alpha_squad.squad_v2 import qa_fails_since_escalation, current_dev_model
    comments = (
        {"body": "squad-v2-qa:fail"},
        {"body": "squad-v2-qa:fail"},
        {"body": "squad-v2-model:model-b — escalated"},
        {"body": "squad-v2-qa:fail"},
    )
    assert qa_fails_since_escalation(comments) == 1
    assert current_dev_model(comments, LADDER) == "model-b"


def test_ladder_exhausted_blocks():
    # at the top rung (model-c) with 3 more fails → no next → failed + needs_human
    comments = [
        _DEV,
        {"body": "squad-v2-model:model-c — escalated"},
        {"body": "squad-v2-qa:fail"},
        {"body": "squad-v2-qa:fail"},
        {"body": "squad-v2-qa:fail"},
    ]
    act = next_action(_dev_approved(comments), model_ladder=LADDER)
    assert act.kind == "failed" and "ladder is exhausted" in act.reason
    assert act.needs_human is True


def test_developer_retry_limit_sets_needs_human():
    # 3 dev run-failures, no deliverable ever produced → needs human
    comments = [{"body": "squad-v2-run:failed:developer — x"} for _ in range(3)]
    act = next_action(_dev_approved(comments), model_ladder=LADDER)
    assert act.kind == "failed" and act.needs_human is True


def test_missing_target_repo_is_not_needs_human():
    # a malformed issue (config error) blocks but is NOT an AI-exhausted case
    act = next_action(IssueView(1, "OPEN", frozenset({"director-approved"}), (), "no repo here"))
    assert act.kind == "failed" and act.needs_human is False


def test_models_tried_lists_base_then_escalations():
    from ai_alpha_squad.squad_v2 import models_tried
    comments = (
        _DEV,
        {"body": "squad-v2-model:model-b — escalated"},
        {"body": "squad-v2-model:model-c — escalated"},
    )
    assert models_tried(comments, LADDER) == ["model-a", "model-b", "model-c"]
    assert models_tried((), LADDER) == ["model-a"]


def test_human_assistance_summary_content():
    from ai_alpha_squad.squad_v2 import human_assistance_summary
    comments = (
        _DEV,
        {"body": "# QA Report\n## Fixes required\n1. [BLOCKER] Foo.java:7 — remove duplicate field\nsquad-v2-qa:fail"},
        {"body": "squad-v2-model:model-b — escalated"},
        {"body": "# Developer Deliverable\n\nattempt 2\n" + "z" * 200},
        {"body": "# QA Report\n## Fixes required\n1. [BLOCKER] Foo.java:7 — still duplicated\nsquad-v2-qa:fail"},
    )
    msg = human_assistance_summary(comments, LADDER)
    assert "needs human assistance" in msg.lower()
    assert "model-a" in msg and "model-b" in msg  # models tried
    assert "2 QA review round" in msg  # two qa:fail markers
    assert "still duplicated" in msg  # latest blocker, not the earlier one


def test_no_ladder_blocks_after_3_like_before():
    comments = [_DEV] + [{"body": "squad-v2-qa:fail"} for _ in range(3)]
    act = next_action(_dev_approved(comments), model_ladder=[])
    assert act.kind == "failed"


def test_model_override_in_resolve_model(monkeypatch):
    import ai_alpha_squad.agent_models as am
    monkeypatch.setenv("SQUAD_AGENT_MODEL_OVERRIDE", "org/super-model")
    assert am.resolve_model("developer", "huggingface") == "org/super-model"


def test_model_marker_is_internal():
    assert is_squad_internal_comment("squad-v2-model:model-b — escalated")


def test_forced_model_bypasses_qa_cap_even_with_empty_ladder():
    # 3 QA fails, NO ladder, but the Director picked a model via the dropdown →
    # dispatch the developer on that model instead of blocking (the #140 dropdown bug).
    comments = [_DEV] + [{"body": "squad-v2-qa:fail"} for _ in range(3)]
    act = next_action(
        _dev_approved(comments), model_ladder=[], forced_model="Qwen/Qwen2.5-Coder-32B-Instruct"
    )
    assert act.kind == "dispatch" and act.agent == "developer"
    assert "Qwen/Qwen2.5-Coder-32B-Instruct" in act.reason


def test_forced_model_equal_to_current_does_not_loop():
    # Forced == current model already in effect → no escalation → blocks at the cap.
    comments = [
        _DEV,
        {"body": "squad-v2-model:Qwen/Qwen2.5-Coder-32B-Instruct — escalated"},
        {"body": "squad-v2-qa:fail"},
        {"body": "squad-v2-qa:fail"},
        {"body": "squad-v2-qa:fail"},
    ]
    act = next_action(
        _dev_approved(comments), model_ladder=[], forced_model="Qwen/Qwen2.5-Coder-32B-Instruct"
    )
    assert act.kind == "failed"
