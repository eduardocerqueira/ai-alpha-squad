#!/usr/bin/env bash
# Dispatch the next v2 agent on a single parent issue (sequential, HF + Actions for dev).
# In inline mode (orchestrator, SQUAD_ACTIONS_INLINE=1) it CHAINS: after an agent runs
# inline it re-evaluates and dispatches the next one (dev → QA → rework → …) until it
# reaches a Director gate / idle / done, so the loop doesn't wait on the 15m cron.
# In non-inline mode (phase-watch, dev spawns an async workflow) it dispatches once.
# Usage: squad-v2-dispatch.sh <queue_repo> <issue_number>
set -euo pipefail

REPO="${1:?queue repo}"
ISSUE="${2:?issue number}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
export SQUAD_V2=1

FORMAT="${ROOT}/scripts/format-squad-comment.py"
DISPATCH="${ROOT}/scripts/squad-dispatch-subissue.sh"
SYNC="${ROOT}/scripts/squad-sync-planning-labels.sh"

export SQUAD_AI_PROVIDER=huggingface
export SQUAD_CODE_RUNTIME=actions
export SQUAD_ACTIONS_SKIP_DISPATCH_COMMENT=1

# Chain multiple inline steps in one run; single dispatch otherwise (an async
# dedicated workflow wouldn't have finished, so re-evaluating would be premature).
MAX_CHAIN=1
if [[ "${SQUAD_ACTIONS_INLINE:-}" == "1" ]]; then
  # High enough that one run can walk the whole model ladder to a terminal verdict
  # (release-candidate or needs-human) rather than stalling mid-escalation: a full
  # ladder is len(ladder) × MAX_QA_ROUNDS dev⇄QA steps. The 90-minute job timeout
  # is the real backstop.
  MAX_CHAIN="${SQUAD_V2_MAX_CHAIN:-20}"
fi
# Resilience: if an EXTERNAL actor closes the issue mid-chain (we've seen a process
# auto-close issues seconds after reopen), reopen and continue rather than abandon a
# loop we already started. Bounded so we never fight indefinitely.
MAX_REOPEN="${SQUAD_V2_MAX_REOPEN:-6}"
reopens=0

TARGET="$(python3 -c "
import json, subprocess, sys
from ai_alpha_squad.squad_v2 import resolve_target_repo
repo, issue = sys.argv[1], sys.argv[2]
data = json.loads(subprocess.check_output(
    ['gh', 'issue', 'view', issue, '--repo', repo, '--json', 'body,comments'],
    text=True,
))
comments = tuple(data.get('comments') or [])
print(resolve_target_repo(data.get('body') or '', comments) or repo)
" "$REPO" "$ISSUE")"

for ((step = 1; step <= MAX_CHAIN; step++)); do
  ACTION="$(python3 -c "
from ai_alpha_squad.squad_v2 import IssueView, next_action, dev_model_ladder
import os, json, subprocess, sys

repo, issue = sys.argv[1], int(sys.argv[2])
data = json.loads(subprocess.check_output(
    ['gh', 'issue', 'view', str(issue), '--repo', repo,
     '--json', 'state,labels,body,comments'],
    text=True,
))
labels = frozenset(x['name'] for x in data.get('labels') or [])
comments = tuple(data.get('comments') or [])
view = IssueView(issue, data.get('state') or 'OPEN', labels, comments, data.get('body') or '')
ladder = dev_model_ladder(os.environ.get('SQUAD_DEV_MODEL_LADDER'))
forced = os.environ.get('SQUAD_DEV_MODEL_INPUT', '').strip() or None
act = next_action(view, model_ladder=ladder, forced_model=forced)
print(act.kind)
print(act.agent or '')
print('1' if act.needs_human else '0')
print(act.reason)
" "$REPO" "$ISSUE")"

  KIND="$(echo "$ACTION" | sed -n '1p')"
  AGENT="$(echo "$ACTION" | sed -n '2p')"
  NEEDS_HUMAN="$(echo "$ACTION" | sed -n '3p')"
  REASON="$(echo "$ACTION" | sed -n '4,$p' | head -1)"

  echo "v2 #$ISSUE [step $step/$MAX_CHAIN]: kind=$KIND agent=$AGENT — $REASON"

  case "$KIND" in
    dispatch) ;;
    done)
      # Mid-chain external close: we already dispatched at least one agent this run
      # (step > 1) and the issue is now closed under us — reopen and continue the
      # loop instead of abandoning it. Only for "Issue closed" (not "Released"), and
      # only inline, bounded by MAX_REOPEN. A genuinely released/closed job ends its
      # chain at the release-candidate gate before this, so it isn't resurrected.
      if [[ "${SQUAD_ACTIONS_INLINE:-}" == "1" && "$REASON" == *"Issue closed"* \
            && $step -gt 1 && $reopens -lt $MAX_REOPEN ]]; then
        reopens=$((reopens + 1))
        echo "v2 #$ISSUE: issue closed mid-chain — reopening to continue (resilience ${reopens}/${MAX_REOPEN})"
        gh issue reopen "$ISSUE" --repo "$REPO" 2>/dev/null || true
        sleep 2
        continue
      fi
      exit 0
      ;;
    gate | idle)
      exit 0
      ;;
    failed)
      if [[ "$NEEDS_HUMAN" == "1" ]]; then
        # The squad exhausted every model + retry and still can't pass QA. Post a
        # clear human-assistance message (how many tries, which models, last
        # blocker) and flag the issue needs-human so the dashboard surfaces it.
        MSG="$(python3 -c "
from ai_alpha_squad.squad_v2 import human_assistance_summary, dev_model_ladder
import os, json, subprocess, sys
repo, issue = sys.argv[1], int(sys.argv[2])
data = json.loads(subprocess.check_output(
    ['gh','issue','view',str(issue),'--repo',repo,'--json','comments'], text=True))
comments = tuple(data.get('comments') or [])
ladder = dev_model_ladder(os.environ.get('SQUAD_DEV_MODEL_LADDER'))
print(human_assistance_summary(comments, ladder))
" "$REPO" "$ISSUE")"
        BODY="$(python3 "$FORMAT" notice --message "$MSG" --repo "$REPO")"
        gh issue comment "$ISSUE" --repo "$REPO" --body "$BODY"
        gh issue edit "$ISSUE" --repo "$REPO" --add-label "blocked" --add-label "needs-human" 2>/dev/null || true
      else
        BODY="$(python3 "$FORMAT" notice --message "**Squad v2:** $REASON" --repo "$REPO")"
        gh issue comment "$ISSUE" --repo "$REPO" --body "$BODY"
        gh issue edit "$ISSUE" --repo "$REPO" --add-label "blocked" 2>/dev/null || true
      fi
      exit 1
      ;;
    *)
      exit 0
      ;;
  esac

  # in_progress is posted when the agent job actually starts (squad-run-actions-agent.sh),
  # not here — posting before dispatch orphans the marker when dispatch fails (#178).

  INSTRUCTIONS="$(mktemp)"
  case "$AGENT" in
    business-owner)
      cat > "$INSTRUCTIONS" <<EOF
You are the Business Owner for AI Alpha Squad (v2 — single issue, no sub-issues).

Read .agents/agent-business-owner.md and .agents/templates/business-analysis-template.md

Issue: https://github.com/${REPO}/issues/${ISSUE}
Target repo (for context): ${TARGET}

1. Post the full Business Analysis on THIS issue (#${ISSUE}) — heading must include: # Business Analysis
2. Do not open sub-issues. Do not open PRs on ${REPO}.
3. When complete, the orchestrator will add label awaiting-approval.
EOF
      ;;
    developer)
      python3 -m ai_alpha_squad.squad_dispatch_instructions developer "$REPO" "$ISSUE" "$TARGET" > "$INSTRUCTIONS"
      ;;
    qa)
      PR_DIFF=""
      QA_CHANGED=""
      QA_TREE=""
      QA_PR="$(gh pr list --repo "$TARGET" --head "squad/developer-issue-${ISSUE}" --state open --json number -q '.[0].number' 2>/dev/null || true)"
      if [[ -n "$QA_PR" ]]; then
        PR_DIFF="$(gh pr diff "$QA_PR" --repo "$TARGET" 2>/dev/null | head -c 60000 || true)"
        QA_CHANGED="$(gh pr view "$QA_PR" --repo "$TARGET" --json files -q '.files[].path' 2>/dev/null || true)"
      fi
      QA_TREE="$(gh api "repos/${TARGET}/git/trees/${SQUAD_TARGET_BASE_BRANCH:-main}?recursive=1" \
        --jq '[.tree[] | select(.type=="blob") | .path] | join("\n")' 2>/dev/null | head -c 16000 || true)"
      ISSUE_BODY_QA="$(gh issue view "$ISSUE" --repo "$REPO" --json body -q .body 2>/dev/null || true)"
      QA_CTX_FILE="$(mktemp)"
      export QA_PR_DIFF="$PR_DIFF" QA_CHANGED_FILES="$QA_CHANGED" QA_BASE_TREE="$QA_TREE" QA_ISSUE_BODY="$ISSUE_BODY_QA"
      python3 <<'PY' > "$QA_CTX_FILE"
import json, os
payload = {
    "pr_diff": os.environ.get("QA_PR_DIFF", ""),
    "changed_files": [l for l in os.environ.get("QA_CHANGED_FILES", "").splitlines() if l.strip()],
    "base_tree": os.environ.get("QA_BASE_TREE", ""),
    "build_ok": True,
    "issue_body": os.environ.get("QA_ISSUE_BODY", ""),
}
print(json.dumps(payload))
PY
      python3 -m ai_alpha_squad.squad_dispatch_instructions qa "$REPO" "$ISSUE" "$TARGET" < "$QA_CTX_FILE" > "$INSTRUCTIONS"
      rm -f "$QA_CTX_FILE"
      ;;
    *)
      echo "Unknown agent: $AGENT" >&2
      exit 1
      ;;
  esac

  # Developer model selection: a Director-chosen model (SQUAD_DEV_MODEL_INPUT) wins;
  # otherwise escalate up SQUAD_DEV_MODEL_LADDER after MAX_QA_ROUNDS rejections. The
  # chosen model is applied via SQUAD_AGENT_MODEL_OVERRIDE; an escalation records a
  # squad-v2-model marker (which resets the per-model QA-round counter).
  unset SQUAD_AGENT_MODEL_OVERRIDE
  if [[ "$AGENT" == "developer" ]]; then
    DEV_MODEL_OUT="$(python3 -c "
import os, json, subprocess, sys
from ai_alpha_squad.squad_v2 import (
    dev_model_ladder, current_dev_model, next_dev_model,
    qa_fails_since_escalation, MAX_QA_ROUNDS, model_marker_comment)
repo, issue = sys.argv[1], int(sys.argv[2])
data = json.loads(subprocess.check_output(
    ['gh','issue','view',str(issue),'--repo',repo,'--json','comments'], text=True))
comments = tuple(data.get('comments') or ())
ladder = dev_model_ladder(os.environ.get('SQUAD_DEV_MODEL_LADDER'))
forced = os.environ.get('SQUAD_DEV_MODEL_INPUT','').strip()
cur = current_dev_model(comments, ladder)
escalate_to = None
if forced and forced != cur:
    escalate_to = forced
elif qa_fails_since_escalation(comments) >= MAX_QA_ROUNDS:
    escalate_to = next_dev_model(comments, ladder)
model = escalate_to or cur or ''
print(model)
print(model_marker_comment(escalate_to) if escalate_to else '')
" "$REPO" "$ISSUE")"
    MODEL_LINE="$(echo "$DEV_MODEL_OUT" | sed -n '1p')"
    ESC_MARKER="$(echo "$DEV_MODEL_OUT" | sed -n '2,$p' | head -1)"
    if [[ -n "$ESC_MARKER" ]]; then
      gh issue comment "$ISSUE" --repo "$REPO" --body "$ESC_MARKER"
    fi
    if [[ -n "$MODEL_LINE" ]]; then
      export SQUAD_AGENT_MODEL_OVERRIDE="$MODEL_LINE"
      echo "developer model: $MODEL_LINE"
    fi
  fi

  # Deterministic compile gate before HF QA — catches incomplete PRs (e.g. import-only).
  if [[ "$AGENT" == "qa" ]]; then
    ISSUE_BODY="$(gh issue view "$ISSUE" --repo "$REPO" --json body -q .body 2>/dev/null || true)"
    if ! python3 -m ai_alpha_squad.target_build_verify gate-pr "$REPO" "$ISSUE" "$TARGET" "$ISSUE_BODY"; then
      echo "v2 #$ISSUE: build verification failed — posted squad-v2-qa:fail; developer rework next"
      "$SYNC" "$REPO" "$ISSUE" || true
      [[ "${SQUAD_ACTIONS_INLINE:-}" == "1" ]] || exit 0
      continue
    fi
    AUTO_QA="$(python3 -c "
import sys
sys.path.insert(0, 'src')
from ai_alpha_squad.squad_v2 import auto_qa_pass_body
print(auto_qa_pass_body(sys.argv[1], build_ok=True) or '')
" "$ISSUE_BODY")"
    if [[ -n "$AUTO_QA" ]]; then
      gh issue comment "$ISSUE" --repo "$REPO" --body "$AUTO_QA"
      echo "v2 #$ISSUE: compile-only job — deterministic QA pass (HF QA skipped)"
      "$SYNC" "$REPO" "$ISSUE" || true
      [[ "${SQUAD_ACTIONS_INLINE:-}" == "1" ]] || exit 0
      continue
    fi
  fi

  if ! "$DISPATCH" "$REPO" "$ISSUE" "$AGENT" "$TARGET" "$INSTRUCTIONS"; then
    ERR="dispatch failed for ${AGENT}"
    FAIL="$(python3 -c "from ai_alpha_squad.squad_v2 import failed_comment; print(failed_comment('$AGENT', '''$ERR'''))")"
    gh issue comment "$ISSUE" --repo "$REPO" --body "$FAIL"
    exit 1
  fi

  rm -f "$INSTRUCTIONS"
  echo "Dispatched $AGENT on #$ISSUE"

  # Advance lifecycle labels immediately (the agent ran inline and just posted its
  # deliverable) instead of waiting up to 15m for the next phase-watch cron tick.
  chmod +x "$SYNC" 2>/dev/null || true
  "$SYNC" "$REPO" "$ISSUE" || true

  # Non-inline: the dispatched dev runs in an async workflow that hasn't finished,
  # so stop here; the next cron tick / its completion drives the rest.
  [[ "${SQUAD_ACTIONS_INLINE:-}" == "1" ]] || exit 0
done

echo "v2 #$ISSUE: chain step cap (${MAX_CHAIN}) reached"
