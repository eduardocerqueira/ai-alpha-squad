// Real-time dashboard compute — TypeScript port of the v2 model in
// src/ai_alpha_squad/squad_v2.py + director_dashboard.py (_load_job_card_v2).
// Keep these in sync; tests pin parity. Model: Business Owner → Developer → QA,
// deliverables as parent-issue comments, no sub-issues.

export interface RawComment {
  body?: string | null;
  createdAt?: string | null;
}
export interface RawIssue {
  number: number;
  title?: string | null;
  body?: string | null;
  state?: string | null; // OPEN | CLOSED
  labels: string[];
  updatedAt?: string | null;
  comments: RawComment[];
}

const LIFECYCLE_LABELS_V2 = [
  "released",
  "blocked",
  "release-candidate",
  "director-approved",
  "awaiting-approval",
  "new",
] as const;

const GATE_LABELS = new Set(["awaiting-approval", "release-candidate"]);
const AGENTS_V2 = ["business-owner", "developer", "qa"] as const;
const DELIVERABLE_MARKERS: Record<string, string> = {
  "business-owner": "# Business Analysis",
  developer: "# Developer Deliverable",
  qa: "# QA Report",
};
const QA_PASS = "squad-v2-qa:pass";
const QA_FAIL = "squad-v2-qa:fail";
const DIRECTOR_DELIVERY_REJECT = "squad-v2-director:delivery-reject";
const RUN_FAILED = "squad-v2-run:failed:";
const RUN_RESET = "squad-v2-run:reset:";
const MAX_QA_ROUNDS = 3;
const MAX_RUN_ATTEMPTS = 3;

const NOISE = ["squad orchestrator nudge", "squad pr guard"];
const PROMOTE = "Squad deliverable promoted from PR";

const SUBISSUE_PREFIXES = ["[Developer]", "[QA]", "[Security]", "[DevOps]", "[Tech Writer]", "Architect:"];

function isOrchestratorNoise(body: string): boolean {
  const l = body.toLowerCase();
  return NOISE.some((n) => l.includes(n));
}

function hasHeadingMarker(body: string, marker: string): boolean {
  // (?m)^<marker>\s — marker at the start of a line, followed by whitespace.
  const re = new RegExp("(^|\\n)" + marker.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "\\s");
  return re.test(body);
}

function hasDeliverable(comments: RawComment[], agent: string): boolean {
  const marker = DELIVERABLE_MARKERS[agent];
  if (!marker) return false;
  for (const c of comments) {
    const body = c.body || "";
    if (isOrchestratorNoise(body)) continue;
    if (body.includes(PROMOTE)) continue;
    if (hasHeadingMarker(body, marker)) return true;
  }
  return false;
}

function latestDeliverableIndex(comments: RawComment[], agent: string): number | null {
  const marker = DELIVERABLE_MARKERS[agent];
  if (!marker) return null;
  let idx: number | null = null;
  comments.forEach((c, i) => {
    const body = c.body || "";
    if (isOrchestratorNoise(body)) return;
    if (hasHeadingMarker(body, marker)) idx = i;
  });
  return idx;
}

function directorRejectedAfter(comments: RawComment[], afterIndex: number): boolean {
  for (let i = afterIndex + 1; i < comments.length; i++) {
    if ((comments[i].body || "").toLowerCase().includes(DIRECTOR_DELIVERY_REJECT)) return true;
  }
  return false;
}

function validateQaReport(body: string): "pass" | "fail" | null {
  const text = body || "";
  if (!/#\s*QA Report\b/i.test(text)) return null;
  const lower = text.toLowerCase();
  if (!lower.includes(QA_PASS) && !lower.includes(QA_FAIL)) return null;
  const verdictLine = new RegExp(`^\\s*(${QA_PASS}|${QA_FAIL})\\s*$`, "m");
  if (!verdictLine.test(text)) return null;
  const verdict = lower.includes(QA_FAIL) ? "fail" : "pass";
  if (verdict === "fail") {
    if (!lower.includes("## fixes required")) return null;
    if (!/^\s*\d+\.\s*\[(BLOCKER|REQUIRED|NICE)\]\s*.+/im.test(text)) return null;
  }
  return verdict;
}

function latestQaVerdict(comments: RawComment[]): { idx: number | null; verdict: "pass" | "fail" | null } {
  for (let i = comments.length - 1; i >= 0; i--) {
    const body = comments[i].body || "";
    const lower = body.toLowerCase();
    if (!lower.includes(QA_FAIL) && !lower.includes(QA_PASS)) continue;
    const verdict = validateQaReport(body);
    if (verdict) return { idx: i, verdict };
  }
  return { idx: null, verdict: null };
}

const RUN_MODEL = "squad-v2-model:";

/** QA failures since the latest model-escalation marker — the current model's
 *  round count. Mirrors squad_v2.qa_fails_since_escalation so the QA row and the
 *  stuck classification reset when the developer model escalates. */
function qaFailRounds(comments: RawComment[]): number {
  let mkIdx = -1;
  comments.forEach((c, i) => {
    if ((c.body || "").toLowerCase().includes(RUN_MODEL)) mkIdx = i;
  });
  return comments.filter((c, i) => i > mkIdx && (c.body || "").toLowerCase().includes(QA_FAIL)).length;
}

function runFailures(comments: RawComment[], agent: string): number {
  const fail = `${RUN_FAILED}${agent}`;
  const resetAgent = `${RUN_RESET}${agent}`;
  const resetAll = `${RUN_RESET}all`;
  let resetIdx = -1;
  comments.forEach((c, i) => {
    const b = (c.body || "").toLowerCase();
    if (b.includes(resetAgent) || b.includes(resetAll)) resetIdx = i;
  });
  return comments.filter((c, i) => i > resetIdx && (c.body || "").toLowerCase().includes(fail)).length;
}

function currentLifecycle(labels: Set<string>): string | null {
  for (const l of LIFECYCLE_LABELS_V2) if (labels.has(l)) return l;
  return null;
}

const RUN_IN_PROGRESS = "squad-v2-run:in_progress:";

function latestMarkerIndex(comments: RawComment[], needle: string): number | null {
  let idx: number | null = null;
  comments.forEach((c, i) => {
    if ((c.body || "").toLowerCase().includes(needle)) idx = i;
  });
  return idx;
}

/** Agent with a live run: an in_progress marker not followed by a deliverable,
 *  a failure, or a result comment. Mirrors squad_v2.run_in_progress. */
function runInProgress(comments: RawComment[]): string | null {
  for (const agent of AGENTS_V2) {
    const progIdx = latestMarkerIndex(comments, `${RUN_IN_PROGRESS}${agent}`);
    if (progIdx === null) continue;
    if (hasDeliverable(comments, agent)) continue;
    const failIdx = latestMarkerIndex(comments, `${RUN_FAILED}${agent}`);
    if (failIdx !== null && failIdx > progIdx) continue;
    const slug = agent.replace(/-/g, " ");
    let completed = false;
    for (let i = progIdx + 1; i < comments.length; i++) {
      const b = (comments[i].body || "").toLowerCase();
      if ((b.includes("squad actions agent result") || b.includes("squad hf agent result")) && b.includes(slug)) {
        completed = true;
        break;
      }
    }
    if (completed) continue;
    return agent;
  }
  return null;
}

function parentRef(body: string): boolean {
  return /Parent\s+Issue\s*\|\s*#\d+|Parent\s+issue:\s*#\d+|issues\/\d+/i.test(body);
}

// Strip the HTML-table wrapper + markdown from a Squad notice comment down to a
// plain-text summary for the dashboard card.
function noticeSummary(body: string | null | undefined): string {
  if (!body) return "";
  const text = body
    .replace(/<[^>]+>/g, " ") // HTML tags
    .replace(/[#>*_`]/g, " ") // markdown emphasis/heading marks
    .replace(/🚫|👉/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  return text.length > 320 ? text.slice(0, 320) + "…" : text;
}

function isParentJob(title: string, body: string): boolean {
  if (parentRef(body)) return false;
  const t = title.trim();
  return !SUBISSUE_PREFIXES.some((p) => t.startsWith(p));
}

function extractTargetRepo(body: string): string | null {
  const text = body || "";
  const re = /https:\/\/github\.com\/([\w.-]+\/[\w.-]+)/g;
  for (const line of text.split("\n")) {
    if (!line.toLowerCase().includes("target")) continue;
    for (const m of line.matchAll(re)) if (!m[1].toLowerCase().includes("ai-alpha-squad")) return m[1];
  }
  for (const m of text.matchAll(re)) if (!m[1].toLowerCase().includes("ai-alpha-squad")) return m[1];
  return null;
}

function devPrUrl(comments: RawComment[]): string | null {
  let found: string | null = null;
  const re = /https:\/\/github\.com\/([\w.-]+\/[\w.-]+)\/pull\/\d+/g;
  for (const c of comments) {
    for (const m of (c.body || "").matchAll(re)) {
      if (!m[1].toLowerCase().includes("ai-alpha-squad")) found = m[0];
    }
  }
  return found;
}

const TIMELINE_PHASES_V2: [string, string, string][] = [
  ["new", "Request triaged", "business-owner"],
  ["awaiting-approval", "Business analysis ready", "Director"],
  ["implementation", "Implementation — PR on target repo", "developer"],
  ["qa", "QA review", "qa"],
  ["release-candidate", "Delivery review", "Director"],
  ["released", "Released", "Done"],
];

const PHASE_ORDER = ["new", "awaiting-approval", "director-approved", "release-candidate", "released"];

interface ModelUse {
  model: string;
  at: string;
  kind: "result" | "escalation";
}
interface AgentRow {
  role: string;
  status: string;
  issue_number: number | null;
  issue_url: string | null;
  detail: string;
  model?: string | null;
  model_history?: ModelUse[];
}

// Squad result comments render as an HTML card: the posting agent is identified
// by its avatar (assets/agents/<role>.svg) and the model is printed as
// "Model: `org/Name`". A "squad-v2-model:X" marker records a developer
// escalation. Mirrors director_dashboard._v2_agent_model_history.
const RESULT_ROLE_RE = /\/agents\/([a-z-]+)\.svg/;
const MODEL_RE = /\bmodel:?\**\s*`([^`]+)`/i;
const ESCALATION_RE = /squad-v2-model:(\S+)/;

function resultRole(body: string): string | null {
  const m = body.match(RESULT_ROLE_RE);
  return m ? m[1] : null;
}

/** Chronological models an agent used on this issue (oldest→newest), with
 *  consecutive duplicates collapsed so it reads as distinct hand-offs. */
function agentModelHistory(comments: RawComment[], role: string): ModelUse[] {
  const raw: ModelUse[] = [];
  for (const c of comments) {
    const body = c.body || "";
    const at = c.createdAt || "";
    if (role === "developer") {
      const m = body.match(ESCALATION_RE);
      if (m) {
        raw.push({ model: m[1], at, kind: "escalation" });
        continue;
      }
    }
    const low = body.toLowerCase();
    const isResult = low.includes("squad hf agent result") || low.includes("squad actions agent result");
    if (isResult && resultRole(body) === role) {
      const m = body.match(MODEL_RE);
      if (m) raw.push({ model: m[1], at, kind: "result" });
    }
  }
  const history: ModelUse[] = [];
  for (const e of raw) {
    if (history.length && history[history.length - 1].model === e.model) continue;
    history.push(e);
  }
  return history;
}

/** Latest model an agent used (back-compat single value). */
function agentModel(comments: RawComment[], role: string): string | null {
  const h = agentModelHistory(comments, role);
  return h.length ? h[h.length - 1].model : null;
}
interface EventRow {
  key: string;
  title: string;
  owner: string;
  status: string;
  detail: string;
  action?: { label: string; url: string; message: string };
  pr_url?: string;
  at?: string;
}

function commentAt(comments: RawComment[], idx: number | null): string {
  if (idx === null || idx < 0 || idx >= comments.length) return "";
  return comments[idx].createdAt || "";
}
function firstMarkerAt(comments: RawComment[], needle: string): string {
  for (const c of comments) if ((c.body || "").toLowerCase().includes(needle)) return c.createdAt || "";
  return "";
}
function releasedAt(comments: RawComment[]): string {
  let at = "";
  for (const c of comments) if ((c.body || "").trimStart().toLowerCase().startsWith("released")) at = c.createdAt || "";
  return at;
}

function directorAction(bucket: string, lc: string | null): string {
  if (bucket !== "needs_you") return "";
  if (lc === "awaiting-approval") return "Open the issue and reply APPROVE (or REQUEST CHANGES).";
  if (lc === "release-candidate") {
    return "Accept delivery to complete the job, or Reject to send developer and QA for another round.";
  }
  return "Open the issue and follow the Director gate instructions.";
}

/** Headline when no agent run marker is live but work is queued for dispatch. */
function pendingHeadline(comments: RawComment[], lc: string | null): string {
  if (runInProgress(comments)) return "";
  const devIdx = latestDeliverableIndex(comments, "developer");
  const { idx: qaIdx, verdict } = latestQaVerdict(comments);
  if (lc === "director-approved" && devIdx === null) return "Queued — implement on target repo";
  if (devIdx !== null && (verdict === null || (qaIdx ?? 0) < devIdx))
    return "Queued — QA review of the developer deliverable";
  if (devIdx !== null && verdict === "fail" && (qaIdx ?? 0) > devIdx)
    return "Queued — developer rework after QA rejection";
  return "";
}

function buildAgents(
  parentUrl: string,
  number: number,
  comments: RawComment[],
  lc: string | null,
  prUrl: string | null,
): AgentRow[] {
  const devIdx = latestDeliverableIndex(comments, "developer");
  const { idx: qaIdx, verdict } = latestQaVerdict(comments);
  const donePhase = lc === "release-candidate" || lc === "released";
  const rounds = qaFailRounds(comments);
  const active = runInProgress(comments);
  const row = (role: string, status: string, detail: string): AgentRow => ({
    role,
    status,
    issue_number: number,
    issue_url: parentUrl,
    detail,
    model: agentModel(comments, role),
    model_history: agentModelHistory(comments, role),
  });

  let bo: [string, string];
  if (hasDeliverable(comments, "business-owner")) bo = ["done", "Business analysis posted"];
  else if (lc === "new") bo = ["active", "Writing business analysis"];
  else bo = ["done", "Complete"];

  const prSuffix = prUrl ? ` — ${prUrl}` : "";
  const pendingQa =
    devIdx !== null &&
    (verdict === null || (qaIdx ?? 0) < devIdx) &&
    active !== "qa";
  const pendingDev =
    devIdx !== null &&
    verdict === "fail" &&
    (qaIdx ?? 0) > devIdx &&
    active !== "developer";

  let dev: [string, string];
  if (donePhase) dev = ["done", `Delivered${prSuffix}`];
  else if (devIdx !== null && verdict === "fail" && (qaIdx ?? 0) > devIdx)
    dev = pendingDev
      ? ["waiting", `Queued — rework after QA (round ${rounds})${prSuffix}`]
      : ["waiting", `QA requested changes — awaiting developer${prSuffix}`];
  else if (
    devIdx !== null &&
    verdict === "pass" &&
    (qaIdx ?? 0) > devIdx &&
    directorRejectedAfter(comments, qaIdx ?? 0)
  )
    dev = ["waiting", `Director rejected delivery — awaiting rework${prSuffix}`];
  else if (devIdx !== null) dev = ["done", `Deliverable posted${prSuffix}`];
  else if (lc === "director-approved")
    dev =
      active !== "developer"
        ? ["waiting", "Awaiting developer implementation"]
        : ["waiting", "Queued — implementing on the target repo"];
  else dev = ["waiting", "After Director approves the analysis"];

  let qa: [string, string];
  if (donePhase) qa = ["done", "Passed"];
  else if (
    devIdx !== null &&
    verdict === "pass" &&
    (qaIdx ?? 0) > devIdx &&
    directorRejectedAfter(comments, qaIdx ?? 0)
  )
    qa = ["waiting", "Awaiting re-review after developer rework"];
  else if (devIdx !== null && verdict === "pass" && (qaIdx ?? 0) > devIdx) qa = ["done", "Passed"];
  else if (devIdx !== null && verdict === "fail" && (qaIdx ?? 0) > devIdx)
    qa = [rounds >= MAX_QA_ROUNDS ? "blocked" : "done", `Requested changes (round ${rounds}/${MAX_QA_ROUNDS})`];
  else if (devIdx !== null)
    qa = pendingQa
      ? ["waiting", "Queued — QA review of deliverable"]
      : ["waiting", "Awaiting QA review"];
  else qa = ["waiting", "After the developer delivers"];

  const rows = [
    row("business-owner", bo[0], bo[1]),
    row("developer", dev[0], dev[1]),
    row("qa", qa[0], qa[1]),
  ];
  if (active) {
    const r = rows.find((x) => x.role === active);
    if (r) {
      r.status = "running";
      r.detail = `Running now — ${r.detail}`;
    }
  }
  return rows;
}

function buildEvents(
  lc: string | null,
  comments: RawComment[],
  action: string,
  issueUrl: string,
  prUrl: string | null,
): EventRow[] {
  const devIdx = latestDeliverableIndex(comments, "developer");
  const { idx: qaIdx, verdict } = latestQaVerdict(comments);
  const rounds = qaFailRounds(comments);
  const cur = lc && PHASE_ORDER.includes(lc) ? PHASE_ORDER.indexOf(lc) : -1;
  const atOrPast = (label: string) => cur >= PHASE_ORDER.indexOf(label);

  // Best-available timestamp per phase, from the comment that marks it.
  const baAt = commentAt(comments, latestDeliverableIndex(comments, "business-owner"));
  const phaseAt: Record<string, string> = {
    new: firstMarkerAt(comments, "squad-v2-run:in_progress:business-owner") || baAt,
    "awaiting-approval": baAt,
    implementation: commentAt(comments, devIdx),
    qa: commentAt(comments, qaIdx),
    released: releasedAt(comments),
  };

  return TIMELINE_PHASES_V2.map(([key, title, owner]) => {
    let status = "pending";
    let detail = "";
    if (key === "new") {
      status = cur > 0 || hasDeliverable(comments, "business-owner") ? "done" : lc === "new" ? "current" : "pending";
    } else if (key === "awaiting-approval") {
      status = atOrPast("director-approved") ? "done" : lc === "awaiting-approval" ? "director" : "pending";
    } else if (key === "implementation") {
      if (atOrPast("release-candidate")) {
        status = "done";
        if (prUrl) detail = "PR merged";
      } else if (devIdx !== null) {
        const dirReject =
          verdict === "pass" && (qaIdx ?? 0) > devIdx && directorRejectedAfter(comments, qaIdx ?? 0);
        status = dirReject || (verdict === "fail" && (qaIdx ?? 0) > devIdx) ? "current" : "done";
        if (prUrl) detail = dirReject ? "Director rejected — reworking" : "PR open";
      } else if (lc === "director-approved") {
        status = "current";
        detail = "Developer implementing on the target repo";
      }
    } else if (key === "qa") {
      if (atOrPast("release-candidate")) status = "done";
      else if (devIdx === null) status = "pending";
      else if (verdict === "pass" && (qaIdx ?? 0) > devIdx) {
        status = directorRejectedAfter(comments, qaIdx ?? 0) ? "current" : "done";
        if (directorRejectedAfter(comments, qaIdx ?? 0)) {
          detail = "Director rejected — waiting for developer rework";
        }
      }
      else if (verdict === "fail" && (qaIdx ?? 0) > devIdx) {
        status = rounds >= MAX_QA_ROUNDS ? "blocked" : "current";
        detail = `QA requested changes — developer reworking (${rounds}/${MAX_QA_ROUNDS})`;
      } else {
        status = "current";
        detail = "Reviewing the developer deliverable";
      }
    } else if (key === "release-candidate") {
      status = lc === "released" ? "done" : lc === "release-candidate" ? "director" : "pending";
    } else if (key === "released") {
      status = lc === "released" ? "done" : "pending";
    }

    const ev: EventRow = { key, title, owner, status, detail };
    if (status === "director") {
      ev.detail = action || "Director decision required.";
      ev.action = { label: "Open issue & respond", url: issueUrl, message: ev.detail };
    }
    if (key === "implementation" && prUrl) ev.pr_url = prUrl;
    const at = phaseAt[key] || "";
    if (at && status !== "pending") ev.at = at;
    return ev;
  });
}

function buildCard(repo: string, issue: RawIssue): Record<string, unknown> | null {
  const title = issue.title || "";
  const body = issue.body || "";
  if (!isParentJob(title, body)) return null;

  const number = issue.number;
  const labels = issue.labels || [];
  const labelSet = new Set(labels);
  const state = (issue.state || "OPEN").toUpperCase();
  const comments = issue.comments || [];
  const blocked = labelSet.has("blocked");
  // needs-human: the squad exhausted every model + retry and gave up — a stronger
  // signal than a plain block. Always implies blocked.
  const needsHuman = labelSet.has("needs-human");
  // `blocked`/`needs-human` are overlays, not phases — compute the real phase from
  // the other labels so the timeline/agents still reflect progress (the Blocked tab
  // + flags convey the state).
  const lc = currentLifecycle(
    blocked || needsHuman
      ? new Set([...labelSet].filter((l) => l !== "blocked" && l !== "needs-human"))
      : labelSet,
  );
  const prUrl = devPrUrl(comments);
  const issueUrl = `https://github.com/${repo}/issues/${number}`;

  const failed =
    qaFailRounds(comments) >= MAX_QA_ROUNDS ||
    AGENTS_V2.some((a) => runFailures(comments, a) >= MAX_RUN_ATTEMPTS);

  // Priority: released is done; an active agent run shows In progress even if the
  // issue is closed; `blocked` outranks closed (Blocked tab); then closed → Done.
  const activeRun = runInProgress(comments) !== null;
  let bucket: string;
  if (lc === "released") bucket = "completed";
  else if (activeRun && !blocked) bucket = "in_progress";
  else if (blocked) bucket = "stuck";
  else if (state === "CLOSED") bucket = "completed";
  else if (lc && GATE_LABELS.has(lc)) bucket = "needs_you";
  else if (failed) bucket = "stuck";
  else bucket = "in_progress";

  const action = directorAction(bucket, lc);
  let headline: string;
  if (bucket === "completed") headline = "This job is done.";
  else if (bucket === "needs_you")
    headline =
      lc === "awaiting-approval"
        ? "Approve the Business Analysis."
        : lc === "release-candidate"
          ? "Accept or reject the developer + QA delivery."
          : "Your approval is required.";
  else if (bucket === "stuck")
    headline = needsHuman
      ? "Needs human assistance — the AI squad exhausted all attempts."
      : blocked
        ? "This job is blocked."
        : "This job needs attention.";
  else headline = pendingHeadline(comments, lc) || "Squad is working — nothing needed from you.";

  // Surface the human-assistance message the squad posted, so the dashboard shows
  // why it gave up without opening the issue.
  const stuckReasons: string[] = [];
  if (needsHuman) {
    const notice = [...comments]
      .reverse()
      .find((c) => /needs \*\*?human/i.test(c.body || "") || /needs human assistance/i.test(c.body || ""));
    stuckReasons.push(
      noticeSummary(notice?.body) ||
        "The AI squad tried every available model and exhausted its retries without passing QA. A human should review the PR and take over.",
    );
  }

  return {
    number,
    title,
    url: issueUrl,
    lifecycle: lc,
    active_agent: "",
    bucket,
    blocked,
    updated_at: issue.updatedAt || "",
    target_repo: extractTargetRepo(body),
    target_pr_url: prUrl,
    target_pr_merged: (lc === "release-candidate" || lc === "released") && prUrl !== null,
    summary: headline,
    headline,
    director_action: action,
    labels,
    needs_human: needsHuman,
    stuck_reasons: stuckReasons,
    suggested_action: "",
    agents: buildAgents(issueUrl, number, comments, lc, prUrl),
    events: buildEvents(lc, comments, action, issueUrl, prUrl),
  };
}

export function computeDashboard(repo: string, issues: RawIssue[], generatedAt: string): Record<string, unknown> {
  const buckets: Record<string, Record<string, unknown>[]> = {
    needs_you: [],
    in_progress: [],
    stuck: [],
    completed: [],
  };
  for (const issue of issues) {
    const card = buildCard(repo, issue);
    if (card) buckets[card.bucket as string].push(card);
  }
  for (const k of Object.keys(buckets)) {
    buckets[k].sort((a, b) => String(b.updated_at).localeCompare(String(a.updated_at)));
  }
  // Bound the Done tab to the most-recent closed/released jobs (matches the
  // Python builder's include_closed cap).
  buckets.completed = buckets.completed.slice(0, 15);
  return {
    generated_at: generatedAt,
    repo,
    counts: {
      needs_you: buckets.needs_you.length,
      in_progress: buckets.in_progress.length,
      stuck: buckets.stuck.length,
      completed: buckets.completed.length,
    },
    ...buckets,
  };
}
