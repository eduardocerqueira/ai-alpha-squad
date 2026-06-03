import {
  clearSessionCookie,
  createMagicToken,
  createSessionCookie,
  isAllowed,
  MAGIC_TTL_MINUTES,
  sessionEmail,
  verifyMagicToken,
} from "./auth";

export { DashboardHub } from "./dashboard-hub";
import { computeDashboard, runInProgress } from "./director-data";
import { fetchIssues, fetchLiveAgentRuns } from "./github";

export interface Env {
  EMAIL: SendEmail;
  ASSETS: Fetcher;
  TURNSTILE_SECRET_KEY: string;
  TURNSTILE_SITE_KEY: string;
  CONTACT_TO_EMAIL: string;
  CONTACT_FROM_EMAIL: string;
  CONTACT_DELIVERY_EMAIL: string;
  CLOUDFLARE_ACCOUNT_ID: string;
  CLOUDFLARE_EMAIL_SEND_TOKEN: string;
  // Director dashboard auth
  AUTH_SECRET: string;
  DIRECTOR_ALLOWED_EMAILS: string;
  // Real-time push (CI → browsers)
  NOTIFY_SECRET: string;
  DASHBOARD_HUB: DurableObjectNamespace;
  // Real-time compute (GitHub webhook → Worker → KV)
  DASHBOARD_KV?: KVNamespace;
  GITHUB_READ_TOKEN?: string;
  WEBHOOK_SECRET?: string;
  // Developer model ladder for the dashboard "re-run with model" dropdown.
  SQUAD_DEV_MODEL_LADDER?: string;
}

const DASHBOARD_HUB_NAME = "global";
const DASHBOARD_REPO = "eduardocerqueira/ai-alpha-squad";
const KV_SNAPSHOT_KEY = "snapshot";

interface ContactPayload {
  name?: string;
  email?: string;
  message?: string;
  turnstileToken?: string;
}

interface TurnstileResult {
  success: boolean;
  "error-codes"?: string[];
}

const MAX_NAME = 120;
const MAX_EMAIL = 254;
const MAX_MESSAGE = 4000;

// CI (director-dashboard.yml) refreshes jobs.json on this branch; the deployed
// dashboard reads it live so it tracks GitHub without a redeploy.
const DIRECTOR_JOBS_BRANCH_URL =
  "https://raw.githubusercontent.com/eduardocerqueira/ai-alpha-squad/director-jobs-json/site/public/director/jobs.json";
const DIRECTOR_JOBS_TTL_SEC = 20;

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);

    // GitHub webhook → recompute the dashboard now → KV → push to open tabs.
    if (url.pathname === "/api/director/webhook" && request.method === "POST") {
      return handleWebhook(request, env, ctx);
    }

    // CI reconciler posts the Python-computed snapshot to keep KV fresh.
    if (url.pathname === "/api/director/ingest" && request.method === "POST") {
      const auth = request.headers.get("Authorization") || "";
      if (!env.NOTIFY_SECRET || auth !== `Bearer ${env.NOTIFY_SECRET}`) {
        return json({ error: "unauthorized" }, 401);
      }
      const body = await request.text();
      if (env.DASHBOARD_KV && body.trimStart().startsWith("{")) {
        await env.DASHBOARD_KV.put(KV_SNAPSHOT_KEY, body);
      }
      await broadcastRefresh(env);
      return json({ ok: true });
    }

    if (url.pathname === "/api/contact") {
      if (request.method === "POST") {
        return handleContact(request, env);
      }
      return json({ error: "Method not allowed" }, 405);
    }

    if (url.pathname === "/api/health" && request.method === "GET") {
      return json({ ok: true });
    }

    if (url.pathname === "/api/config" && request.method === "GET") {
      const ladder = (env.SQUAD_DEV_MODEL_LADDER || "")
        .split(/[,\s]+/)
        .map((m) => m.trim())
        .filter(Boolean);
      return json({ turnstileSiteKey: env.TURNSTILE_SITE_KEY, modelLadder: ladder });
    }

    if (url.pathname === "/api/director/auth/request" && request.method === "POST") {
      return handleAuthRequest(request, env, url);
    }

    if (url.pathname === "/api/director/auth/verify" && request.method === "GET") {
      return handleAuthVerify(request, env, url);
    }

    if (url.pathname === "/api/director/auth/me" && request.method === "GET") {
      const email = await sessionEmail(env, request);
      return email ? json({ email }) : json({ error: "unauthorized" }, 401);
    }

    if (url.pathname === "/api/director/auth/logout" && request.method === "POST") {
      return new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json", "Set-Cookie": clearSessionCookie() },
      });
    }

    if (url.pathname === "/api/director/jobs" && request.method === "GET") {
      const email = await sessionEmail(env, request);
      if (!email) return json({ error: "unauthorized" }, 401);
      const force = url.searchParams.get("refresh") === "1" || url.searchParams.get("live") === "1";
      return serveJobs(env, force);
    }

    // Director retries a stuck/blocked job: dispatch the v2 orchestrator
    // (auto-clears the failure count + removes `blocked`, then re-runs the agent).
    if (url.pathname === "/api/director/retry" && request.method === "POST") {
      const email = await sessionEmail(env, request);
      if (!email) return json({ error: "unauthorized" }, 401);
      return handleRetry(request, env);
    }

    // Director stops a running job: cancel its in-flight Actions run(s), clear
    // the in-progress marker, and set `blocked` so it stays halted (Retry
    // clears `blocked` and resumes).
    if (url.pathname === "/api/director/stop" && request.method === "POST") {
      const email = await sessionEmail(env, request);
      if (!email) return json({ error: "unauthorized" }, 401);
      return handleStop(request, env);
    }

    // Director accepts or rejects dev+QA delivery (release-candidate gate).
    if (url.pathname === "/api/director/delivery-gate" && request.method === "POST") {
      const email = await sessionEmail(env, request);
      if (!email) return json({ error: "unauthorized" }, 401);
      return handleDeliveryGate(request, env, ctx);
    }

    // Director marks a finished job Done (released) when work shipped outside the
    // release-candidate gate — e.g. PR merged but lifecycle labels were never cleared.
    if (url.pathname === "/api/director/mark-done" && request.method === "POST") {
      const email = await sessionEmail(env, request);
      if (!email) return json({ error: "unauthorized" }, 401);
      return handleMarkDone(request, env, ctx);
    }

    // Authenticated dashboards open a WebSocket here; the hub pushes "refresh"
    // when CI publishes new data, so the UI updates without polling.
    if (url.pathname === "/api/director/live") {
      if (request.headers.get("Upgrade")?.toLowerCase() !== "websocket") {
        return json({ error: "expected websocket" }, 426);
      }
      const email = await sessionEmail(env, request);
      if (!email) return json({ error: "unauthorized" }, 401);
      const stub = env.DASHBOARD_HUB.get(env.DASHBOARD_HUB.idFromName(DASHBOARD_HUB_NAME));
      return stub.fetch(request);
    }

    // CI (director-dashboard.yml) calls this after publishing the data branch.
    if (url.pathname === "/api/director/notify" && request.method === "POST") {
      const auth = request.headers.get("Authorization") || "";
      if (!env.NOTIFY_SECRET || auth !== `Bearer ${env.NOTIFY_SECRET}`) {
        return json({ error: "unauthorized" }, 401);
      }
      await broadcastRefresh(env);
      return json({ ok: true });
    }

    return env.ASSETS.fetch(request);
  },
};

/** Tell every open dashboard to refetch (via the WebSocket hub). */
async function broadcastRefresh(env: Env): Promise<void> {
  try {
    const stub = env.DASHBOARD_HUB.get(env.DASHBOARD_HUB.idFromName(DASHBOARD_HUB_NAME));
    await stub.fetch("https://hub.local/notify", { method: "POST" });
  } catch (err) {
    console.error("broadcastRefresh failed:", err);
  }
}

/** Recompute the dashboard live from GitHub and cache it in KV. */
async function recomputeDashboard(env: Env): Promise<string> {
  const token = env.GITHUB_READ_TOKEN!;
  const [issues, liveRuns] = await Promise.all([
    fetchIssues(DASHBOARD_REPO, token),
    fetchLiveAgentRuns(DASHBOARD_REPO, token),
  ]);
  const snapshot = computeDashboard(DASHBOARD_REPO, issues, new Date().toISOString(), liveRuns);
  const body = JSON.stringify(snapshot);
  if (env.DASHBOARD_KV) await env.DASHBOARD_KV.put(KV_SNAPSHOT_KEY, body);
  return body;
}

/** Serve the dashboard: KV snapshot (instant) → live recompute → branch/bundled. */
async function serveJobs(env: Env, force: boolean): Promise<Response> {
  const headers = { "Content-Type": "application/json", "Cache-Control": "no-store" };
  if (env.GITHUB_READ_TOKEN && env.DASHBOARD_KV) {
    try {
      if (!force) {
        const cached = await env.DASHBOARD_KV.get(KV_SNAPSHOT_KEY);
        if (cached) return new Response(cached, { headers: { ...headers, "X-Data-Source": "kv" } });
      }
      const body = await recomputeDashboard(env);
      return new Response(body, { headers: { ...headers, "X-Data-Source": "live" } });
    } catch (err) {
      console.error("serveJobs live/KV path failed, falling back:", err);
    }
  }
  return handleDirectorJobs(env, force); // legacy branch/bundled fallback
}

/** GitHub webhook: verify signature, recompute on relevant events, push. */
async function handleWebhook(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
  const raw = await request.text();
  if (!env.WEBHOOK_SECRET || !(await verifyWebhookSignature(raw, request, env.WEBHOOK_SECRET))) {
    return json({ error: "invalid signature" }, 401);
  }
  const event = request.headers.get("X-GitHub-Event") || "";
  if (event === "ping") return json({ ok: true, pong: true });
  if (!["issues", "issue_comment", "pull_request"].includes(event)) {
    return json({ ok: true, ignored: event });
  }
  // Recompute + push after responding, so GitHub gets a fast 200.
  ctx.waitUntil(
    (async () => {
      try {
        await recomputeDashboard(env);
        await broadcastRefresh(env);
      } catch (err) {
        console.error("webhook recompute failed:", err);
      }
    })(),
  );
  return json({ ok: true });
}

const ORCHESTRATOR_WORKFLOW = "squad-v2-orchestrator.yml";
// Workflows whose in-flight runs a Stop should cancel. Both carry the issue
// number in their run-name (see .github/workflows/*) so we cancel only the
// runs that belong to the job being stopped.
const STOPPABLE_WORKFLOWS = ["squad-v2-orchestrator.yml", "squad-actions-agent.yml"];
const RUN_AGENTS_V2 = ["business-owner", "developer", "qa"];

/** Re-run a stuck/blocked job via the v2 orchestrator's workflow_dispatch. */
async function handleRetry(request: Request, env: Env): Promise<Response> {
  if (!env.GITHUB_READ_TOKEN) return json({ error: "GitHub token not configured" }, 503);
  let body: { number?: number; model?: string };
  try {
    body = (await request.json()) as { number?: number; model?: string };
  } catch {
    return json({ error: "Invalid JSON body" }, 400);
  }
  const number = Number(body.number);
  if (!Number.isInteger(number) || number <= 0) return json({ error: "Invalid issue number" }, 400);
  const developerModel = typeof body.model === "string" ? body.model.trim() : "";

  const headers = {
    Authorization: `Bearer ${env.GITHUB_READ_TOKEN}`,
    Accept: "application/vnd.github+json",
    "User-Agent": "ai-alpha-squad-dashboard",
    "Content-Type": "application/json",
  };

  // Resume at the phase the orchestrator understands (new | director-approved),
  // derived from the issue's live labels (ignoring the `blocked` overlay).
  let lifecycleLabel = "director-approved";
  let closed = false;
  try {
    const res = await fetch(`https://api.github.com/repos/${DASHBOARD_REPO}/issues/${number}`, { headers });
    if (res.ok) {
      const issue = (await res.json()) as { labels?: { name: string }[]; state?: string };
      const labels = (issue.labels ?? []).map((l) => l.name);
      if (labels.includes("release-candidate")) {
        lifecycleLabel = "director-approved";
      } else {
        lifecycleLabel = labels.includes("director-approved")
          ? "director-approved"
          : labels.includes("new")
            ? "new"
            : "director-approved";
      }
      closed = (issue.state || "").toLowerCase() === "closed";
    }
  } catch {
    /* fall back to director-approved */
  }

  const issueApi = `https://api.github.com/repos/${DASHBOARD_REPO}/issues/${number}`;

  // Retrying / re-opening means working it again — reopen a closed issue so it
  // isn't stuck under Done while the agent runs.
  if (closed) {
    await fetch(issueApi, { method: "PATCH", headers, body: JSON.stringify({ state: "open" }) }).catch(
      () => {},
    );
  }

  // Clear terminal/overlay labels and ensure the resume phase is set, so the
  // orchestrator (which reads the issue's live labels) actually re-runs it —
  // a `released` or `blocked` label would otherwise short-circuit to "done".
  for (const label of ["released", "blocked", "release-candidate"]) {
    await fetch(`${issueApi}/labels/${label}`, { method: "DELETE", headers }).catch(() => {});
  }
  await fetch(`${issueApi}/labels`, {
    method: "POST",
    headers,
    body: JSON.stringify({ labels: [lifecycleLabel] }),
  }).catch(() => {});

  const dispatch = await fetch(
    `https://api.github.com/repos/${DASHBOARD_REPO}/actions/workflows/${ORCHESTRATOR_WORKFLOW}/dispatches`,
    {
      method: "POST",
      headers,
      body: JSON.stringify({
        ref: "main",
        inputs: {
          issue_number: String(number),
          lifecycle_label: lifecycleLabel,
          ...(developerModel ? { developer_model: developerModel } : {}),
        },
      }),
    },
  );
  if (dispatch.status === 204) {
    return json({ ok: true, lifecycle_label: lifecycleLabel });
  }
  const detail = await dispatch.text();
  console.error("retry dispatch failed:", dispatch.status, detail);
  return json(
    { error: `Could not start the re-run (GitHub ${dispatch.status}).`, status: dispatch.status },
    502,
  );
}

const DIRECTOR_DELIVERY_REJECT_MARKER = "squad-v2-director:delivery-reject";
const DIRECTOR_DELIVERY_ACCEPT_MARKER = "squad-v2-director:delivery-accept";
const SQUAD_JOB_ARCHIVED_MARKER = "squad-v2-job:archived";
const LIFECYCLE_LABELS_TO_CLEAR = [
  "new",
  "awaiting-approval",
  "director-approved",
  "release-candidate",
  "blocked",
  "needs-human",
];

/** Mark a job Done: `released` label, clear active lifecycle labels, close issue. */
async function handleMarkDone(
  request: Request,
  env: Env,
  ctx: ExecutionContext,
): Promise<Response> {
  if (!env.GITHUB_READ_TOKEN) return json({ error: "GitHub token not configured" }, 503);
  let body: { number?: number; note?: string };
  try {
    body = (await request.json()) as { number?: number; note?: string };
  } catch {
    return json({ error: "Invalid JSON body" }, 400);
  }
  const number = Number(body.number);
  const note = typeof body.note === "string" ? body.note.trim() : "";
  if (!Number.isInteger(number) || number <= 0) return json({ error: "Invalid issue number" }, 400);

  const headers = {
    Authorization: `Bearer ${env.GITHUB_READ_TOKEN}`,
    Accept: "application/vnd.github+json",
    "User-Agent": "ai-alpha-squad-dashboard",
    "Content-Type": "application/json",
  };
  const issueApi = `https://api.github.com/repos/${DASHBOARD_REPO}/issues/${number}`;

  const issueRes = await fetch(`${issueApi}?labels=1`, { headers });
  if (!issueRes.ok) return json({ error: "Could not load issue" }, 502);
  const issue = (await issueRes.json()) as { labels?: { name: string }[]; state?: string };
  const labels = (issue.labels ?? []).map((l) => l.name);
  if (labels.includes("released")) {
    return json({ error: "Issue is already marked released" }, 409);
  }

  for (const label of LIFECYCLE_LABELS_TO_CLEAR) {
    if (labels.includes(label)) {
      await fetch(`${issueApi}/labels/${encodeURIComponent(label)}`, {
        method: "DELETE",
        headers,
      }).catch(() => {});
    }
  }

  await fetch(`${issueApi}/labels`, {
    method: "POST",
    headers,
    body: JSON.stringify({ labels: ["released"] }),
  }).catch(() => {});

  const comment = [
    "Released — job marked done by Director.",
    note ? `\n${note}` : "",
    "",
    "**Director:** Job complete — removed from the active queue.",
    "",
    DIRECTOR_DELIVERY_ACCEPT_MARKER,
    SQUAD_JOB_ARCHIVED_MARKER,
  ].join("\n");
  await fetch(`${issueApi}/comments`, {
    method: "POST",
    headers,
    body: JSON.stringify({ body: comment }),
  });

  if ((issue.state || "").toLowerCase() !== "closed") {
    const closeRes = await fetch(issueApi, {
      method: "PATCH",
      headers,
      body: JSON.stringify({ state: "closed", state_reason: "completed" }),
    });
    if (!closeRes.ok) {
      const detail = await closeRes.text();
      console.error("mark-done close issue failed:", closeRes.status, detail);
      return json(
        { error: "Marked released, but could not close the issue." },
        502,
      );
    }
  }

  ctx.waitUntil(
    (async () => {
      try {
        await recomputeDashboard(env);
        await broadcastRefresh(env);
      } catch {
        /* ignore */
      }
    })(),
  );
  return json({ ok: true });
}

/** Accept or reject dev+QA delivery when the issue is at release-candidate. */
async function handleDeliveryGate(
  request: Request,
  env: Env,
  ctx: ExecutionContext,
): Promise<Response> {
  if (!env.GITHUB_READ_TOKEN) return json({ error: "GitHub token not configured" }, 503);
  let body: { number?: number; action?: string; reason?: string };
  try {
    body = (await request.json()) as { number?: number; action?: string; reason?: string };
  } catch {
    return json({ error: "Invalid JSON body" }, 400);
  }
  const number = Number(body.number);
  const action = (body.action || "").trim().toLowerCase();
  const reason = typeof body.reason === "string" ? body.reason.trim() : "";
  if (!Number.isInteger(number) || number <= 0) return json({ error: "Invalid issue number" }, 400);
  if (action !== "accept" && action !== "reject") {
    return json({ error: 'action must be "accept" or "reject"' }, 400);
  }

  const headers = {
    Authorization: `Bearer ${env.GITHUB_READ_TOKEN}`,
    Accept: "application/vnd.github+json",
    "User-Agent": "ai-alpha-squad-dashboard",
    "Content-Type": "application/json",
  };
  const issueApi = `https://api.github.com/repos/${DASHBOARD_REPO}/issues/${number}`;

  const issueRes = await fetch(`${issueApi}?labels=1`, { headers });
  if (!issueRes.ok) return json({ error: "Could not load issue" }, 502);
  const issue = (await issueRes.json()) as { labels?: { name: string }[]; state?: string };
  const labels = (issue.labels ?? []).map((l) => l.name);
  if (!labels.includes("release-candidate")) {
    return json({ error: "Issue is not awaiting delivery approval (release-candidate)" }, 409);
  }

  const postComment = async (text: string) => {
    await fetch(`${issueApi}/comments`, {
      method: "POST",
      headers,
      body: JSON.stringify({ body: text }),
    });
  };

  if (action === "accept") {
    await fetch(`${issueApi}/labels/release-candidate`, { method: "DELETE", headers }).catch(() => {});
    await fetch(`${issueApi}/labels`, {
      method: "POST",
      headers,
      body: JSON.stringify({ labels: ["released"] }),
    }).catch(() => {});
    const acceptComment = [
      "Released — job accepted by Director.",
      "",
      "**Director:** Delivery accepted. Job complete.",
      "",
      DIRECTOR_DELIVERY_ACCEPT_MARKER,
    ].join("\n");
    await postComment(acceptComment);
    const closeRes = await fetch(issueApi, {
      method: "PATCH",
      headers,
      body: JSON.stringify({ state: "closed", state_reason: "completed" }),
    });
    if (!closeRes.ok) {
      const detail = await closeRes.text();
      console.error("delivery-gate close issue failed:", closeRes.status, detail);
      return json(
        { error: "Delivery accepted and labeled released, but could not close the issue." },
        502,
      );
    }
    ctx.waitUntil(
      (async () => {
        try {
          await recomputeDashboard(env);
          await broadcastRefresh(env);
        } catch {
          /* ignore */
        }
      })(),
    );
    return json({ ok: true, action: "accept" });
  }

  // reject — rework dev + QA
  const rejectBody = [
    "**Director:** Job rejected by director.",
    reason ? `\n${reason}` : "",
    `\n${DIRECTOR_DELIVERY_REJECT_MARKER}`,
  ].join("");
  await postComment(rejectBody);
  await fetch(`${issueApi}/labels/release-candidate`, { method: "DELETE", headers }).catch(() => {});
  await fetch(`${issueApi}/labels`, {
    method: "POST",
    headers,
    body: JSON.stringify({ labels: ["director-approved"] }),
  }).catch(() => {});
  // A closed issue blocks the orchestrator (next_action → done). Reopen on reject.
  if ((issue.state || "").toLowerCase() === "closed") {
    await fetch(issueApi, {
      method: "PATCH",
      headers,
      body: JSON.stringify({ state: "open" }),
    });
  }
  await postComment("squad-v2-run:reset:developer — failure count cleared; agent gets a fresh set of retry attempts.");
  await postComment("squad-v2-run:reset:qa — failure count cleared; agent gets a fresh set of retry attempts.");
  await postComment(
    "**Squad orchestrator:** Director rejected delivery — developer and QA will rework.",
  );

  const dispatch = await fetch(
    `https://api.github.com/repos/${DASHBOARD_REPO}/actions/workflows/${ORCHESTRATOR_WORKFLOW}/dispatches`,
    {
      method: "POST",
      headers,
      body: JSON.stringify({
        ref: "main",
        inputs: { issue_number: String(number), lifecycle_label: "director-approved" },
      }),
    },
  );
  if (dispatch.status !== 204) {
    const detail = await dispatch.text();
    console.error("delivery-gate reject dispatch failed:", dispatch.status, detail);
    return json(
      { error: `Rejected on issue, but orchestrator dispatch failed (${dispatch.status}).` },
      502,
    );
  }
  ctx.waitUntil(
    (async () => {
      try {
        await recomputeDashboard(env);
        await broadcastRefresh(env);
      } catch {
        /* ignore */
      }
    })(),
  );
  return json({ ok: true, action: "reject" });
}

interface GhComment {
  body?: string;
}
interface GhRun {
  id: number;
  name?: string;
  display_title?: string;
  status?: string;
}

/** The agent whose run is currently in progress on the issue (comment markers). */
function activeRunAgent(comments: GhComment[]): string | null {
  return runInProgress(comments as { body?: string | null; createdAt?: string | null }[]);
}

/** Stop a running job: cancel its in-flight Actions runs, clear the in-progress
 *  marker (no failure penalty), and set `blocked` so it stays halted. */
async function handleStop(request: Request, env: Env): Promise<Response> {
  if (!env.GITHUB_READ_TOKEN) return json({ error: "GitHub token not configured" }, 503);
  let body: { number?: number };
  try {
    body = (await request.json()) as { number?: number };
  } catch {
    return json({ error: "Invalid JSON body" }, 400);
  }
  const number = Number(body.number);
  if (!Number.isInteger(number) || number <= 0) return json({ error: "Invalid issue number" }, 400);

  const headers = {
    Authorization: `Bearer ${env.GITHUB_READ_TOKEN}`,
    Accept: "application/vnd.github+json",
    "User-Agent": "ai-alpha-squad-dashboard",
    "Content-Type": "application/json",
  };
  const issueApi = `https://api.github.com/repos/${DASHBOARD_REPO}/issues/${number}`;

  // Cancel in-flight runs whose run-name carries this issue number (matches
  // "#<n>" not followed by another digit, so #14 ≠ #140).
  const tag = new RegExp(`#${number}(?!\\d)`);
  let cancelled = 0;
  for (const wf of STOPPABLE_WORKFLOWS) {
    try {
      const res = await fetch(
        `https://api.github.com/repos/${DASHBOARD_REPO}/actions/workflows/${wf}/runs?per_page=30`,
        { headers },
      );
      if (!res.ok) continue;
      const { workflow_runs = [] } = (await res.json()) as { workflow_runs?: GhRun[] };
      for (const run of workflow_runs) {
        const live = run.status === "in_progress" || run.status === "queued";
        const title = `${run.display_title || ""} ${run.name || ""}`;
        if (!live || !tag.test(title)) continue;
        const c = await fetch(
          `https://api.github.com/repos/${DASHBOARD_REPO}/actions/runs/${run.id}/cancel`,
          { method: "POST", headers },
        );
        if (c.ok || c.status === 202) cancelled++;
      }
    } catch {
      /* best-effort */
    }
  }

  // Clear the in-progress marker so the dashboard reflects the stop immediately.
  // failed+reset in one comment clears in-progress with a net-zero failure count.
  let agent: string | null = null;
  try {
    const res = await fetch(`${issueApi}/comments?per_page=100`, { headers });
    if (res.ok) agent = activeRunAgent((await res.json()) as GhComment[]);
  } catch {
    /* ignore */
  }
  if (agent) {
    const marker =
      `squad-v2-run:failed:${agent} squad-v2-run:reset:${agent}\n\n` +
      "⏹ **Stopped by the Director** from the dashboard. The in-flight run was cancelled; " +
      "use **Retry** to resume.";
    await fetch(`${issueApi}/comments`, {
      method: "POST",
      headers,
      body: JSON.stringify({ body: marker }),
    }).catch(() => {});
  }

  // Hold it in the Blocked tab so schedulers don't auto-resume it.
  await fetch(`${issueApi}/labels`, {
    method: "POST",
    headers,
    body: JSON.stringify({ labels: ["blocked"] }),
  }).catch(() => {});

  return json({ ok: true, cancelled, agent });
}

async function verifyWebhookSignature(raw: string, request: Request, secret: string): Promise<boolean> {
  const sig = request.headers.get("X-Hub-Signature-256") || "";
  if (!sig.startsWith("sha256=")) return false;
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const mac = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(raw));
  const expected = "sha256=" + [...new Uint8Array(mac)].map((b) => b.toString(16).padStart(2, "0")).join("");
  // constant-time-ish compare
  if (expected.length !== sig.length) return false;
  let diff = 0;
  for (let i = 0; i < expected.length; i++) diff |= expected.charCodeAt(i) ^ sig.charCodeAt(i);
  return diff === 0;
}

/**
 * Serve the Director dashboard snapshot from the CI-refreshed
 * `director-jobs-json` branch (edge-cached ~60s) so it tracks GitHub without a
 * redeploy; falls back to the asset bundled at deploy time. When `force` (the
 * Refresh button sends `?refresh=1`), bypass both the edge cache and the raw
 * CDN cache with a cache-busting URL so the very latest is fetched.
 */
async function handleDirectorJobs(env: Env, force: boolean): Promise<Response> {
  try {
    const target = force ? `${DIRECTOR_JOBS_BRANCH_URL}?t=${Date.now()}` : DIRECTOR_JOBS_BRANCH_URL;
    const live = await fetch(target, {
      cf: force
        ? { cacheTtl: 0, cacheEverything: false }
        : { cacheTtl: DIRECTOR_JOBS_TTL_SEC, cacheEverything: true },
    });
    if (live.ok) {
      const body = await live.text();
      if (body.trimStart().startsWith("{")) {
        return new Response(body, {
          status: 200,
          headers: {
            // Never let the browser/edge cache the API response — clients must
            // always get the Worker's current view. (The ~60s cache lives only
            // on the Worker's subrequest to the data branch, above.)
            "Content-Type": "application/json",
            "Cache-Control": "no-store",
            "X-Data-Source": "live",
          },
        });
      }
    }
  } catch (err) {
    console.error("Live jobs.json fetch failed, using bundled asset:", err);
  }

  const staticRes = await env.ASSETS.fetch("https://assets.local/director/jobs.json");
  if (staticRes.ok) {
    return new Response(staticRes.body, {
      status: 200,
      headers: {
        "Content-Type": "application/json",
        "Cache-Control": "no-store",
        "X-Data-Source": "bundled",
      },
    });
  }
  return json(
    {
      error:
        "Dashboard not published yet. Run the Director dashboard workflow or ./scripts/squad-director-dashboard.py --serve locally.",
    },
    503,
  );
}

// ---- Director dashboard auth ------------------------------------------------

interface AuthRequestPayload {
  email?: string;
}

/** Email a magic link to an allow-listed address. Always returns a generic ok
 *  so the endpoint does not reveal who is on the allowlist. */
async function handleAuthRequest(request: Request, env: Env, url: URL): Promise<Response> {
  let body: AuthRequestPayload;
  try {
    body = await request.json();
  } catch {
    return json({ error: "Invalid JSON body" }, 400);
  }
  const email = trim(body.email, MAX_EMAIL).toLowerCase();
  const generic = json({
    ok: true,
    message: "If that email is authorized, a sign-in link is on its way.",
  });

  if (!isValidEmail(email) || !env.AUTH_SECRET || !isAllowed(env, email)) {
    return generic; // do not disclose allowlist / config state
  }

  try {
    const token = await createMagicToken(env, email);
    const link = `${url.origin}/api/director/auth/verify?token=${encodeURIComponent(token)}`;
    await sendMagicLinkEmail(env, email, link);
  } catch (err) {
    console.error("Magic link send failed:", err);
    return json({ error: "Unable to send sign-in link. Try again shortly." }, 502);
  }
  return generic;
}

/** Validate a magic token, set the session cookie, and bounce to the dashboard. */
async function handleAuthVerify(request: Request, env: Env, url: URL): Promise<Response> {
  const token = url.searchParams.get("token") || "";
  const email = token ? await verifyMagicToken(env, token) : null;
  if (!email) {
    return new Response(loginRedirectHtml("This sign-in link is invalid or expired."), {
      status: 401,
      headers: { "Content-Type": "text/html; charset=utf-8" },
    });
  }
  const cookie = await createSessionCookie(env, email);
  return new Response(null, {
    status: 302,
    headers: { Location: "/director/", "Set-Cookie": cookie },
  });
}

function loginRedirectHtml(message: string): string {
  return `<!DOCTYPE html><html><head><meta charset="utf-8"><meta http-equiv="refresh" content="3;url=/director/"><title>Director</title><style>body{background:#050505;color:#f0f0f0;font-family:Inter,system-ui,sans-serif;display:grid;place-items:center;height:100vh;margin:0}a{color:#22c55e}</style></head><body><div><p>${escapeHtml(message)}</p><p><a href="/director/">Back to sign in</a></p></div></body></html>`;
}

async function sendMagicLinkEmail(env: Env, to: string, link: string): Promise<void> {
  const subject = "Your Director dashboard sign-in link";
  const text = [
    "Sign in to the AI Alpha Squad Director dashboard:",
    "",
    link,
    "",
    `This link expires in ${MAGIC_TTL_MINUTES} minutes and can only be used by ${to}.`,
    "If you did not request it, ignore this email.",
  ].join("\n");
  const html = `
    <p>Sign in to the <strong>AI Alpha Squad Director dashboard</strong>:</p>
    <p><a href="${escapeHtml(link)}" style="display:inline-block;background:#22c55e;color:#000;padding:10px 18px;border-radius:6px;text-decoration:none;font-weight:600">Open the dashboard</a></p>
    <p style="color:#888;font-size:13px">Or paste this URL: <br>${escapeHtml(link)}</p>
    <p style="color:#888;font-size:12px">This link expires in ${MAGIC_TTL_MINUTES} minutes and only works for ${escapeHtml(to)}. If you did not request it, ignore this email.</p>
  `;
  await deliverEmail(env, { to, subject, text, html });
}

/** Send via the account REST API when configured (works to any recipient),
 *  else the Workers Email Routing binding. */
async function deliverEmail(
  env: Env,
  msg: { to: string; subject: string; text: string; html: string },
): Promise<void> {
  const from = { address: env.CONTACT_FROM_EMAIL, name: "AI Alpha Squad" };
  if (env.CLOUDFLARE_EMAIL_SEND_TOKEN && env.CLOUDFLARE_ACCOUNT_ID) {
    const res = await fetch(
      `https://api.cloudflare.com/client/v4/accounts/${env.CLOUDFLARE_ACCOUNT_ID}/email/sending/send`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${env.CLOUDFLARE_EMAIL_SEND_TOKEN}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ to: msg.to, from, subject: msg.subject, text: msg.text, html: msg.html }),
      },
    );
    const data = (await res.json()) as { success?: boolean; errors?: { message?: string }[] };
    if (data.success) return;
    throw new Error(data.errors?.[0]?.message ?? `Email API HTTP ${res.status}`);
  }
  await env.EMAIL.send({
    to: msg.to,
    from: { email: from.address, name: from.name },
    subject: msg.subject,
    text: msg.text,
    html: msg.html,
  });
}

async function handleContact(request: Request, env: Env): Promise<Response> {
  let body: ContactPayload;
  try {
    body = await request.json();
  } catch {
    return json({ error: "Invalid JSON body" }, 400);
  }

  const name = trim(body.name, MAX_NAME);
  const email = trim(body.email, MAX_EMAIL);
  const message = trim(body.message, MAX_MESSAGE);
  const turnstileToken = body.turnstileToken?.trim();

  if (!name || !email || !message || !turnstileToken) {
    return json({ error: "Name, email, message, and verification are required." }, 400);
  }

  if (!isValidEmail(email)) {
    return json({ error: "Invalid email address." }, 400);
  }

  const verified = await verifyTurnstile(turnstileToken, env.TURNSTILE_SECRET_KEY, request);
  if (!verified.success) {
    return json({ error: "Verification failed. Please try again." }, 403);
  }

  const subject = `[AI Alpha Squad] Contact from ${name}`;
  const text = [
    `Name: ${name}`,
    `Email: ${email}`,
    "",
    message,
    "",
    `— Sent via aialphasquad.com contact form`,
  ].join("\n");

  const html = `
    <p><strong>Name:</strong> ${escapeHtml(name)}</p>
    <p><strong>Email:</strong> <a href="mailto:${escapeHtml(email)}">${escapeHtml(email)}</a></p>
    <hr>
    <p>${escapeHtml(message).replace(/\n/g, "<br>")}</p>
    <p style="color:#888;font-size:12px">Sent via aialphasquad.com contact form</p>
  `;

  try {
    await sendContactEmail(env, { name, email, subject, text, html });
  } catch (err) {
    console.error("Email send failed:", err);
    return json({ error: "Unable to send message. Please email us directly." }, 502);
  }

  return json({ ok: true, message: "Message sent. We will respond soon." });
}

interface OutboundEmail {
  name: string;
  email: string;
  subject: string;
  text: string;
  html: string;
}

/** Workers EMAIL binding fails when zone sending isn't enabled; account REST API works. */
async function sendContactEmail(env: Env, msg: OutboundEmail): Promise<void> {
  const to = env.CONTACT_DELIVERY_EMAIL || env.CONTACT_TO_EMAIL;
  const from = { address: env.CONTACT_FROM_EMAIL, name: "AI Alpha Squad" };

  if (env.CLOUDFLARE_EMAIL_SEND_TOKEN && env.CLOUDFLARE_ACCOUNT_ID) {
    const res = await fetch(
      `https://api.cloudflare.com/client/v4/accounts/${env.CLOUDFLARE_ACCOUNT_ID}/email/sending/send`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${env.CLOUDFLARE_EMAIL_SEND_TOKEN}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          to,
          from,
          reply_to: { address: msg.email, name: msg.name },
          subject: msg.subject,
          text: msg.text,
          html: msg.html,
        }),
      },
    );
    const data = (await res.json()) as {
      success?: boolean;
      errors?: { message?: string }[];
    };
    if (data.success) return;
    throw new Error(data.errors?.[0]?.message ?? `Email API HTTP ${res.status}`);
  }

  await env.EMAIL.send({
    to,
    from: { email: from.address, name: from.name },
    replyTo: { email: msg.email, name: msg.name },
    subject: msg.subject,
    text: msg.text,
    html: msg.html,
  });
}

async function verifyTurnstile(
  token: string,
  secret: string,
  request: Request,
): Promise<TurnstileResult> {
  const form = new FormData();
  form.append("secret", secret);
  form.append("response", token);
  const ip = request.headers.get("CF-Connecting-IP");
  if (ip) form.append("remoteip", ip);

  const res = await fetch("https://challenges.cloudflare.com/turnstile/v0/siteverify", {
    method: "POST",
    body: form,
  });
  return res.json() as Promise<TurnstileResult>;
}

function trim(value: string | undefined, max: number): string {
  return (value ?? "").trim().slice(0, max);
}

function isValidEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) && email.length <= MAX_EMAIL;
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
