export interface Env {
  EMAIL: SendEmail;
  ASSETS: Fetcher;
  TURNSTILE_SECRET_KEY: string;
  TURNSTILE_SITE_KEY: string;
  CONTACT_TO_EMAIL: string;
  CONTACT_FROM_EMAIL: string;
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

    return env.ASSETS.fetch(request);
  },
};

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
    await env.EMAIL.send({
      to: env.CONTACT_TO_EMAIL,
      from: { email: env.CONTACT_FROM_EMAIL, name: "AI Alpha Squad" },
      replyTo: { email, name },
      subject,
      text,
      html,
    });
  } catch (err) {
    console.error("Email send failed:", err);
    return json({ error: "Unable to send message. Please email us directly." }, 502);
  }

  return json({ ok: true, message: "Message sent. We will respond soon." });
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
