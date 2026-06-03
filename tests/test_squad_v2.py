"""Tests for minimal squad v2 phase logic."""

from ai_alpha_squad.squad_v2 import (
    IssueView,
    developer_instruction_appendix,
    extract_target_repo,
    find_stale_in_progress,
    has_deliverable,
    is_squad_internal_comment,
    latest_trusted_developer_deliverable_index,
    next_action,
    resolve_target_repo,
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


def test_in_progress_when_reworking_after_deliverable():
    comments = (
        {"body": "# Developer Deliverable\n\nPR: https://github.com/o/r/pull/1\n" + "x" * 200},
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


def test_in_progress_ignored_after_build_gate_comment():
    comments = (
        {"body": "squad-v2-run:in_progress:developer"},
        {
            "body": "**Squad developer — build verification failed.**\n\n```\n"
            "[ERROR] cannot find symbol\n```"
        },
    )
    assert run_in_progress(comments) is None


def test_director_delivery_accept_comment_closes_narrative():
    from ai_alpha_squad.squad_v2 import (
        DIRECTOR_DELIVERY_ACCEPT_MARKER,
        format_director_delivery_accept_comment,
    )

    body = format_director_delivery_accept_comment()
    assert body.lower().startswith("released — job accepted by director")
    assert DIRECTOR_DELIVERY_ACCEPT_MARKER in body


def test_developer_instruction_appendix_includes_build_log():
    comments = (
        {"body": "**Squad developer — build verification failed.**\n\n```\nmvn error line\n```"},
    )
    text = developer_instruction_appendix(comments)
    assert "build verification failure" in text.lower()
    assert "mvn error line" in text
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


def test_failed_comment_triggers_phase_watch():
    assert not is_squad_internal_comment("squad-v2-run:failed:qa — dispatch failed for qa")


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


def test_resolve_target_repo_from_director_comment():
    body = "Summary\nstill not working\n"
    comments = (
        {"body": "approve"},
        {
            "body": "https://github.com/eduardocerqueira/experimental-jenkins-plugin-quote",
        },
    )
    assert resolve_target_repo(body, comments) == (
        "eduardocerqueira/experimental-jenkins-plugin-quote"
    )


def test_director_reject_after_qa_redispatches_developer():
    comments = (
        _DEV,
        _QA_PASS,
        {"body": "**Director:** Job rejected by director.\n\nsquad-v2-director:delivery-reject"},
    )
    from ai_alpha_squad.squad_v2 import qa_passed

    assert not qa_passed(comments)
    act = next_action(_dev_approved(comments))
    assert act.kind == "dispatch" and act.agent == "developer"
    assert "Director rejected" in act.reason


def test_trusted_deliverable_invalid_after_actions_failure():
    comments = (
        _DEV,
        {"body": "squad-v2-run:failed:developer — push rejected"},
    )
    assert latest_trusted_developer_deliverable_index(comments) is None
    act = next_action(_dev_approved(comments))
    assert act.kind == "dispatch" and act.agent == "developer"
    assert "invalid" in act.reason.lower() or "rework" in act.reason.lower()


def test_director_approved_dispatches_when_repo_only_in_comment():
    view = IssueView(
        number=178,
        state="OPEN",
        labels=frozenset({"director-approved"}),
        comments=(
            {
                "body": "https://github.com/eduardocerqueira/experimental-jenkins-plugin-quote",
            },
        ),
        body="Summary\nproject does not compile\n",
    )
    action = next_action(view)
    assert action.kind == "dispatch"
    assert action.agent == "developer"


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
_DEV_REWORK = {
    "body": "# Developer Deliverable\n\nfixed it\n\n**Pull request:** https://github.com/o/r/pull/1\n"
    + "y" * 200
}
_QA_PASS = {
    "body": "# QA Report\n\n## Criteria\n- ✅ met\n\nsquad-v2-qa:pass\n",
}
_QA_FAIL = {
    "body": (
        "# QA Report\n\n## Criteria\n- ❌ gap\n\n## Fixes required\n"
        "1. [BLOCKER] src/Foo.java — fix gap\n\nsquad-v2-qa:fail\n"
    ),
}


def _dev_approved(comments):
    return IssueView(1, "OPEN", frozenset({"director-approved"}), tuple(comments), "https://github.com/o/r")


def test_qa_dispatched_after_developer_deliverable():
    act = next_action(_dev_approved([_DEV]))
    assert act.kind == "dispatch" and act.agent == "qa"


def test_qa_pass_advances_to_release_candidate():
    comments = [_DEV, _QA_PASS]
    act = next_action(_dev_approved(comments))
    assert act.kind == "idle" and "QA passed" in act.reason


def test_qa_fail_redispatches_developer():
    comments = [_DEV, _QA_FAIL]
    act = next_action(_dev_approved(comments))
    assert act.kind == "dispatch" and act.agent == "developer"
    assert "QA requested changes" in act.reason


def test_qa_reviews_redelivered_work():
    # dev → qa:fail → dev again; QA must review the new deliverable.
    comments = [
        _DEV,
        _QA_FAIL,
        _DEV_REWORK,
    ]
    act = next_action(_dev_approved(comments))
    assert act.kind == "dispatch" and act.agent == "qa"


def test_qa_fail_cap_escalates():
    comments = [_DEV]
    for _ in range(3):
        comments.append(_QA_FAIL)
        comments.append(_DEV_REWORK)
    comments.append(_QA_FAIL)
    act = next_action(_dev_approved(comments))
    assert act.kind == "failed" and "QA rejected" in act.reason


def test_qa_passed_helper():
    from ai_alpha_squad.squad_v2 import qa_passed
    assert qa_passed((_DEV, _QA_PASS))
    assert not qa_passed((_DEV,))
    # pass before the latest dev deliverable doesn't count
    assert not qa_passed((_DEV, {"body": "squad-v2-qa:pass"}, {"body": "# Developer Deliverable\n\nnew\n" + "x"*200}))


def test_stale_compile_only_qa_invalid_for_package_job():
    from ai_alpha_squad.squad_v2 import qa_passed
    compile_only_pass = {
        "body": "# QA Report\n\nsquad-v2-qa:pass\n(compile-only job — auto pass)\n",
    }
    body = "### Success criteria\nmvn clean package run successfully\n"
    assert not qa_passed(
        (_DEV, compile_only_pass),
        issue_body=body,
        queue_repo="org/queue",
        issue_number=180,
        target_repo="org/target",
    )


def test_stale_qa_pass_redispatches_developer(monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY", "eduardocerqueira/ai-alpha-squad")
    compile_only_pass = {
        "body": "# QA Report\n\nsquad-v2-qa:pass\n(compile-only job — auto pass)\n",
    }
    body = (
        "### Success criteria\nmvn clean package run successfully\n"
        "Target: https://github.com/eduardocerqueira/experimental-jenkins-plugin-quote"
    )
    view = IssueView(
        180,
        "OPEN",
        frozenset({"director-approved"}),
        (_DEV, compile_only_pass),
        body,
    )
    act = next_action(view)
    assert act.kind == "dispatch"
    assert act.agent == "developer"
    assert "Stale QA" in act.reason


def test_closed_not_planned_is_done():
    from ai_alpha_squad.squad_v2 import squad_closed_job_still_active, squad_job_is_done

    comments = (
        {"body": "**Director reset:** Closing this run.", "createdAt": "2026-06-01T02:00:00Z"},
    )
    labels = frozenset({"director-approved"})
    assert not squad_closed_job_still_active("CLOSED", labels, comments, state_reason="NOT_PLANNED")
    assert squad_job_is_done("CLOSED", labels, comments=comments, state_reason="NOT_PLANNED")


def test_closed_stale_job_without_v2_activity_is_done():
    from ai_alpha_squad.squad_v2 import squad_closed_job_still_active

    comments = ({"body": "# Business Analysis\nold", "createdAt": "2026-05-31T12:00:00Z"},)
    assert not squad_closed_job_still_active("CLOSED", frozenset({"new"}), comments)


def test_closed_recent_v2_activity_still_active():
    from ai_alpha_squad.squad_v2 import squad_closed_job_still_active

    comments = (
        {"body": "squad-v2-run:in_progress:developer", "createdAt": "2026-06-03T04:00:00Z"},
    )
    assert squad_closed_job_still_active("CLOSED", frozenset({"director-approved"}), comments)


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
    comments = [_DEV, _QA_FAIL, _QA_FAIL, _QA_FAIL]
    act = next_action(_dev_approved(comments), model_ladder=LADDER)
    assert act.kind == "dispatch" and act.agent == "developer"
    assert "escalating developer model to model-b" in act.reason


def test_fails_counted_since_escalation_marker():
    from ai_alpha_squad.squad_v2 import qa_fails_since_escalation, current_dev_model
    comments = (
        _QA_FAIL,
        _QA_FAIL,
        {"body": "squad-v2-model:model-b — escalated"},
        _QA_FAIL,
    )
    assert qa_fails_since_escalation(comments) == 1
    assert current_dev_model(comments, LADDER) == "model-b"


def test_ladder_exhausted_blocks():
    # at the top rung (model-c) with 3 more fails → no next → failed + needs_human
    comments = [
        _DEV,
        {"body": "squad-v2-model:model-c — escalated"},
        _QA_FAIL,
        _QA_FAIL,
        _QA_FAIL,
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
        {
            "body": (
                "# QA Report\n\n## Criteria\n- ❌ dup\n\n## Fixes required\n"
                "1. [BLOCKER] Foo.java — remove duplicate field\n\nsquad-v2-qa:fail\n"
            )
        },
        {"body": "squad-v2-model:model-b — escalated"},
        _DEV_REWORK,
        {
            "body": (
                "# QA Report\n\n## Criteria\n- ❌ dup\n\n## Fixes required\n"
                "1. [BLOCKER] Foo.java — still duplicated\n\nsquad-v2-qa:fail\n"
            )
        },
    )
    msg = human_assistance_summary(comments, LADDER)
    assert "needs human assistance" in msg.lower()
    assert "model-a" in msg and "model-b" in msg  # models tried
    assert "2 QA review round" in msg  # two qa:fail markers
    assert "still duplicated" in msg  # latest blocker, not the earlier one


def test_no_ladder_blocks_after_3_like_before():
    comments = [_DEV, _QA_FAIL, _QA_FAIL, _QA_FAIL]
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
    comments = [_DEV, _QA_FAIL, _QA_FAIL, _QA_FAIL]
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
        _QA_FAIL,
        _QA_FAIL,
        _QA_FAIL,
    ]
    act = next_action(
        _dev_approved(comments), model_ladder=[], forced_model="Qwen/Qwen2.5-Coder-32B-Instruct"
    )
    assert act.kind == "failed"
