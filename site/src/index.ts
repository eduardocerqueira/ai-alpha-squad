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
}

const DASHBOARD_HUB_NAME = "global";

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
const DIRECTOR_JOBS_TTL_SEC = 60;

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

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
      return json({ turnstileSiteKey: env.TURNSTILE_SITE_KEY });
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
      return handleDirectorJobs(env, force);
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
      const token = auth.startsWith("Bearer ") ? auth.slice(7) : "";
      if (!env.NOTIFY_SECRET || token !== env.NOTIFY_SECRET) {
        return json({ error: "unauthorized" }, 401);
      }
      const stub = env.DASHBOARD_HUB.get(env.DASHBOARD_HUB.idFromName(DASHBOARD_HUB_NAME));
      return stub.fetch("https://hub.local/notify", { method: "POST" });
    }

    return env.ASSETS.fetch(request);
  },
};

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
