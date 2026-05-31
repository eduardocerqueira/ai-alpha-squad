import {
  classifyDirectorReply,
  formatAuditComment,
  normalizePhone,
} from "./classify";
import {
  addIssueLabel,
  getIssueLabels,
  postIssueComment,
  removeIssueLabel,
} from "./github";

export function verifyMetaWebhook(
  mode: string | null,
  verifyToken: string | null,
  challenge: string | null,
  expected: string,
): string | null {
  if (mode !== "subscribe" || !verifyToken || !challenge) return null;
  if (verifyToken !== expected) return null;
  return challenge;
}

export async function verifySignature(
  request: Request,
  appSecret: string,
  rawBody: string,
): Promise<boolean> {
  const header = request.headers.get("x-hub-signature-256");
  if (!header?.startsWith("sha256=")) return false;
  const expectedHex = header.slice(7);
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(appSecret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(rawBody));
  const hex = [...new Uint8Array(sig)].map((b) => b.toString(16).padStart(2, "0")).join("");
  return timingSafeEqual(hex, expectedHex);
}

function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let out = 0;
  for (let i = 0; i < a.length; i++) out |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return out === 0;
}

type WaTextMessage = { from: string; type: string; text?: { body?: string } };

export function extractInboundTexts(payload: unknown): WaTextMessage[] {
  const messages: WaTextMessage[] = [];
  if (!payload || typeof payload !== "object") return messages;
  const obj = payload as { entry?: Array<{ changes?: Array<{ value?: { messages?: WaTextMessage[] } }> }> };
  for (const entry of obj.entry ?? []) {
    for (const change of entry.changes ?? []) {
      for (const msg of change.value?.messages ?? []) {
        if (msg.type === "text" && msg.text?.body) messages.push(msg);
      }
    }
  }
  return messages;
}

export async function handleInboundMessage(
  env: Env,
  from: string,
  body: string,
): Promise<void> {
  const director = normalizePhone(env.WHATSAPP_DIRECTOR_PHONE);
  if (normalizePhone(from) !== director) {
    console.warn("Ignored WhatsApp message from non-Director number");
    return;
  }

  const issueNumber = parseInt(env.WHATSAPP_DEFAULT_ISSUE_NUMBER, 10);
  if (!Number.isFinite(issueNumber) || issueNumber < 1) {
    throw new Error("WHATSAPP_DEFAULT_ISSUE_NUMBER must be a positive integer");
  }

  const classification = classifyDirectorReply(body);
  const agent =
    classification === "approve" && (await getIssueLabels(env, issueNumber)).includes("release-candidate")
      ? "release-manager"
      : "business-owner";

  const comment = formatAuditComment({
    receivedAt: new Date().toISOString(),
    classification,
    message: body,
    agent,
  });
  await postIssueComment(env, issueNumber, comment);

  const labels = await getIssueLabels(env, issueNumber);
  if (classification === "approve" && labels.includes("awaiting-approval")) {
    await addIssueLabel(env, issueNumber, "director-approved");
    await removeIssueLabel(env, issueNumber, "awaiting-approval");
    await removeIssueLabel(env, issueNumber, "approved");
  }
}
