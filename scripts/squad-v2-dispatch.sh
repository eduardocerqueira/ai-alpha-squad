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
  MAX_CHAIN="${SQUAD_V2_MAX_CHAIN:-8}"
fi
# Resilience: if an EXTERNAL actor closes the issue mid-chain (we've seen a process
# auto-close issues seconds after reopen), reopen and continue rather than abandon a
# loop we already started. Bounded so we never fight indefinitely.
MAX_REOPEN="${SQUAD_V2_MAX_REOPEN:-6}"
reopens=0

TARGET="$(python3 -c "
import subprocess, sys
from ai_alpha_squad.squad_v2 import extract_target_repo
repo, issue = sys.argv[1], sys.argv[2]
body = subprocess.check_output(
    ['gh', 'issue', 'view', issue, '--repo', repo, '--json', 'body', '-q', '.body'],
    text=True,
)
print(extract_target_repo(body) or repo)
" "$REPO" "$ISSUE")"

for ((step = 1; step <= MAX_CHAIN; step++)); do
  ACTION="$(python3 -c "
from ai_alpha_squad.squad_v2 import IssueView, next_action
import json, subprocess, sys

repo, issue = sys.argv[1], int(sys.argv[2])
data = json.loads(subprocess.check_output(
    ['gh', 'issue', 'view', str(issue), '--repo', repo,
     '--json', 'state,labels,body,comments'],
    text=True,
))
labels = frozenset(x['name'] for x in data.get('labels') or [])
comments = tuple(data.get('comments') or [])
view = IssueView(issue, data.get('state') or 'OPEN', labels, comments, data.get('body') or '')
act = next_action(view)
print(act.kind)
print(act.agent or '')
print(act.reason)
" "$REPO" "$ISSUE")"

  KIND="$(echo "$ACTION" | sed -n '1p')"
  AGENT="$(echo "$ACTION" | sed -n '2p')"
  REASON="$(echo "$ACTION" | sed -n '3,$p' | head -1)"

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
      BODY="$(python3 "$FORMAT" notice --message "**Squad v2:** $REASON" --repo "$REPO")"
      gh issue comment "$ISSUE" --repo "$REPO" --body "$BODY"
      gh issue edit "$ISSUE" --repo "$REPO" --add-label "blocked" 2>/dev/null || true
      exit 1
      ;;
    *)
      exit 0
      ;;
  esac

  if ! python3 -c "
import json, subprocess, sys
sys.path.insert(0, 'src')
from ai_alpha_squad.squad_v2 import run_in_progress
repo, issue, agent = sys.argv[1], int(sys.argv[2]), sys.argv[3]
data = json.loads(subprocess.check_output(
    ['gh', 'issue', 'view', str(issue), '--repo', repo, '--json', 'comments'],
    text=True,
))
comments = tuple(data.get('comments') or [])
active = run_in_progress(comments)
raise SystemExit(0 if active == agent else 1)
" "$REPO" "$ISSUE" "$AGENT"; then
    MARKER="$(python3 -c "from ai_alpha_squad.squad_v2 import in_progress_comment; print(in_progress_comment('$AGENT'))")"
    gh issue comment "$ISSUE" --repo "$REPO" --body "$MARKER"
  fi

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
      cat > "$INSTRUCTIONS" <<EOF
You are the Developer for AI Alpha Squad (v2 — single issue, no sub-issues).

Read .agents/agent-developer.md. Target repo: ${TARGET}

Issue: https://github.com/${REPO}/issues/${ISSUE}

1. Implement on ${TARGET} (branch + PR)
2. Post on THIS issue (#${ISSUE}) — heading must include: # Developer Deliverable
   Include the PR URL and summary of changes.
3. If the issue has a "# QA Report" comment ending in \`squad-v2-qa:fail\`, this is a
   REWORK on the EXISTING branch. The QA "## Fixes required" list gives you the EXACT
   file path (and often line numbers) for each item. Work it ONE ITEM AT A TIME:
   - Go STRAIGHT to the file each fix names and edit it — do NOT search or list_dir to
     "explore the codebase" first; QA already told you where to go. Land your first
     edit within a few turns.
   - Fix BLOCKER items FIRST (compile errors, missing required files) — they gate
     everything else. Then REQUIRED, then NICE-to-have.
   - Use TARGETED edit_file (never rewrite a whole file — you will drop code). To
     remove a DUPLICATE declaration, set old_string to the whole block containing all
     the copies and new_string to the single line you want to keep (a bare duplicated
     line is not unique, so edit_file will reject it otherwise). After each edit,
     re-read that region to confirm it applied before moving on.
   - Do NOT re-implement parts QA already marked ✅ — leave working code alone.
   - Verify the project still builds (run the build/compile command if available)
     before posting. Then post an updated # Developer Deliverable listing which
     fix-list items you addressed.
4. Do not create sub-issues.
EOF
      ;;
    qa)
      PR_DIFF=""
      QA_CHANGED=""
      QA_CHANGED_COUNT=0
      QA_TREE=""
      QA_PR="$(gh pr list --repo "$TARGET" --head "squad/developer-issue-${ISSUE}" --state open --json number -q '.[0].number' 2>/dev/null || true)"
      if [[ -n "$QA_PR" ]]; then
        # Large budget so QA sees the WHOLE diff — a truncated diff makes QA think
        # unshown files are missing and wrongly fail bulk/multi-file deliverables.
        PR_DIFF="$(gh pr diff "$QA_PR" --repo "$TARGET" 2>/dev/null | head -c 60000)"
        # Explicit changed-file list + count: a reliable completeness signal that
        # doesn't depend on parsing a (possibly truncated) diff.
        QA_CHANGED="$(gh pr view "$QA_PR" --repo "$TARGET" --json files -q '.files[].path' 2>/dev/null || true)"
        QA_CHANGED_COUNT="$(printf '%s\n' "$QA_CHANGED" | grep -c . || true)"
      fi
      # Files that exist in the base branch (so QA can judge "all existing X were touched").
      QA_TREE="$(gh api "repos/${TARGET}/git/trees/${SQUAD_TARGET_BASE_BRANCH:-main}?recursive=1" \
        --jq '[.tree[] | select(.type=="blob") | .path] | join("\n")' 2>/dev/null | head -c 16000 || true)"
      cat > "$INSTRUCTIONS" <<EOF
You are the QA engineer for AI Alpha Squad (v2). Read .agents/agent-qa.md.

Issue: https://github.com/${REPO}/issues/${ISSUE}
Target repo: ${TARGET}

Evaluate whether the Developer's deliverable satisfies EVERY success criterion in
the issue above (the criteria are in the issue body).

## Files changed in this PR (${QA_CHANGED_COUNT})
${QA_CHANGED:-(no open PR / no files changed — treat as not delivered)}

## Files in the repository base branch (for completeness checks)
${QA_TREE:-(unavailable)}

Use the two lists above to judge **completeness** (e.g. "the task requires every
existing file to be changed, but only N of M were"). Then review the actual changes:

\`\`\`diff
${PR_DIFF:-(no open PR diff found — treat as not delivered)}
\`\`\`

Be a strict but OBJECTIVE reviewer. The Developer is a code model that acts best on a
short, concrete fix-list — not prose. Keep the report tight.

Post ONE comment on THIS issue (#${ISSUE}) with heading: # QA Report
- "## Criteria" — one line per success criterion: \`✅\` or \`❌ <≤12-word reason>\`.
  For any count/coverage criterion, give numbers (e.g. "47/54 files changed").
  Do NOT write paragraphs, code blocks, or restate the criteria text.
- "## Fixes required" — ONLY if failing. A prioritized, numbered list the Developer
  can act on directly. Each item EXACTLY: \`[BLOCKER|REQUIRED|NICE] <file path> — <the
  concrete change to make>\`. Order BLOCKER (won't compile / missing required file)
  first, then REQUIRED, then NICE. Be specific (name the file, function, and line if
  known). No item should need interpretation.
- End with EXACTLY one verdict line, nothing after it:
  - \`squad-v2-qa:pass\` — if and only if every criterion is fully met.
  - \`squad-v2-qa:fail\` — otherwise.
Do not open PRs or sub-issues; review only.
EOF
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
