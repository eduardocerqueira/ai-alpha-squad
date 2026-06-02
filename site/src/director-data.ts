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

function latestQaVerdict(comments: RawComment[]): { idx: number | null; verdict: "pass" | "fail" | null } {
  let idx: number | null = null;
  let verdict: "pass" | "fail" | null = null;
  comments.forEach((c, i) => {
    const body = (c.body || "").toLowerCase();
    if (body.includes(QA_FAIL)) {
      idx = i;
      verdict = "fail";
    } else if (body.includes(QA_PASS)) {
      idx = i;
      verdict = "pass";
    }
  });
  return { idx, verdict };
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
  ["release-candidate", "Release candidate", "Director"],
  ["released", "Released", "Done"],
];

const PHASE_ORDER = ["new", "awaiting-approval", "director-approved", "release-candidate", "released"];

interface AgentRow {
  role: string;
  status: string;
  issue_number: number | null;
  issue_url: string | null;
  detail: string;
  model?: string | null;
}

/** The AI model an agent used: the developer's escalation marker wins, else the
 *  model embedded in the agent's latest result comment ("· model `X`"). */
function agentModel(comments: RawComment[], role: string): string | null {
  if (role === "developer") {
    let escalated: string | null = null;
    for (const c of comments) {
      const m = (c.body || "").match(/squad-v2-model:(\S+)/);
      if (m) escalated = m[1];
    }
    if (escalated) return escalated;
  }
  let model: string | null = null;
  for (const c of comments) {
    const b = c.body || "";
    const low = b.toLowerCase();
    const isResult = low.includes("squad hf agent result") || low.includes("squad actions agent result");
    if (isResult && low.includes("`" + role + "`")) {
      const m = b.match(/· model `([^`]+)`/);
      if (m) model = m[1];
    }
  }
  return model;
}
interface EventRow {
  key: string;
  title: string;
  owner: string;
  status: string;
  detail: string;
  action?: { label: string; url: string; message: string };
  pr_url?: string;
}

function directorAction(bucket: string, lc: string | null): string {
  if (bucket !== "needs_you") return "";
  if (lc === "awaiting-approval") return "Open the issue and reply APPROVE (or REQUEST CHANGES).";
  if (lc === "release-candidate") return "Open the issue and reply APPROVE or REJECT.";
  return "Open the issue and follow the Director gate instructions.";
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
  const row = (role: string, status: string, detail: string): AgentRow => ({
    role,
    status,
    issue_number: number,
    issue_url: parentUrl,
    detail,
    model: agentModel(comments, role),
  });

  let bo: [string, string];
  if (hasDeliverable(comments, "business-owner")) bo = ["done", "Business analysis posted"];
  else if (lc === "new") bo = ["active", "Writing business analysis"];
  else bo = ["done", "Complete"];

  const prSuffix = prUrl ? ` — ${prUrl}` : "";
  let dev: [string, string];
  if (donePhase) dev = ["done", `Delivered${prSuffix}`];
  else if (devIdx !== null && verdict === "fail" && (qaIdx ?? 0) > devIdx)
    dev = ["active", `QA requested changes — reworking${prSuffix}`];
  else if (devIdx !== null) dev = ["done", `Deliverable posted${prSuffix}`];
  else if (lc === "director-approved") dev = ["active", "Implementing on the target repo"];
  else dev = ["waiting", "After Director approves the analysis"];

  let qa: [string, string];
  if (donePhase) qa = ["done", "Passed"];
  else if (devIdx !== null && verdict === "pass" && (qaIdx ?? 0) > devIdx) qa = ["done", "Passed"];
  else if (devIdx !== null && verdict === "fail" && (qaIdx ?? 0) > devIdx)
    qa = [rounds >= MAX_QA_ROUNDS ? "blocked" : "active", `Requested changes (round ${rounds}/${MAX_QA_ROUNDS})`];
  else if (devIdx !== null) qa = ["active", "Reviewing the deliverable"];
  else qa = ["waiting", "After the developer delivers"];

  const rows = [
    row("business-owner", bo[0], bo[1]),
    row("developer", dev[0], dev[1]),
    row("qa", qa[0], qa[1]),
  ];
  // A live run marker (no terminal yet) means this agent is executing *now* —
  // surface it as "running" so the squad column lights up via the webhook.
  const active = runInProgress(comments);
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
        status = verdict === "fail" && (qaIdx ?? 0) > devIdx ? "current" : "done";
        if (prUrl) detail = "PR open";
      } else if (lc === "director-approved") {
        status = "current";
        detail = "Developer implementing on the target repo";
      }
    } else if (key === "qa") {
      if (atOrPast("release-candidate")) status = "done";
      else if (devIdx === null) status = "pending";
      else if (verdict === "pass" && (qaIdx ?? 0) > devIdx) status = "done";
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
  // `blocked` is an overlay, not a phase — compute the real phase from the other
  // labels so the timeline/agents still reflect progress (Blocked tab + flag
  // convey the blocked state).
  const lc = currentLifecycle(blocked ? new Set([...labelSet].filter((l) => l !== "blocked")) : labelSet);
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
    headline = lc === "awaiting-approval" ? "Approve the Business Analysis." : lc === "release-candidate" ? "Approve or reject the release." : "Your approval is required.";
  else if (bucket === "stuck") headline = blocked ? "This job is blocked." : "This job needs attention.";
  else headline = "Squad is working — nothing needed from you.";

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
    stuck_reasons: [] as string[],
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
