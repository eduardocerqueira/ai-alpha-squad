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
}

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

    if (url.pathname === "/api/director/jobs" && request.method === "GET") {
      return handleDirectorJobs(env, url);
    }

    return env.ASSETS.fetch(request);
  },
};

/**
 * Serve the Director dashboard snapshot. Prefers the live CI-refreshed copy on
 * the `director-jobs-json` branch (edge-cached ~60s) so the dashboard tracks
 * GitHub without a redeploy; falls back to the asset bundled at deploy time.
 */
async function handleDirectorJobs(env: Env, url: URL): Promise<Response> {
  try {
    const live = await fetch(DIRECTOR_JOBS_BRANCH_URL, {
      cf: { cacheTtl: DIRECTOR_JOBS_TTL_SEC, cacheEverything: true },
    });
    if (live.ok) {
      const body = await live.text();
      if (body.trimStart().startsWith("{")) {
        return new Response(body, {
          status: 200,
          headers: {
            "Content-Type": "application/json",
            "Cache-Control": `public, max-age=${DIRECTOR_JOBS_TTL_SEC}`,
            "X-Data-Source": "live",
          },
        });
      }
    }
  } catch (err) {
    console.error("Live jobs.json fetch failed, using bundled asset:", err);
  }

  const staticRes = await env.ASSETS.fetch(new URL("/director/jobs.json", url.origin).toString());
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
