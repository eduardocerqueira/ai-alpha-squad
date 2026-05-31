import { agentIconImg, formatSquadComment } from "./squad-comment";

export type DirectorReplyIntent = "approve" | "reject" | "changes" | "ambiguous";

const APPROVE_PHRASES = [
  "approved",
  "approve",
  "yes",
  "lgtm",
  "go",
  "ship it",
  "ok to release",
  "release",
];

const REJECT_PHRASES = ["reject", "rejected", "no", "hold", "stop", "not approved"];

const CHANGES_PHRASES = ["changes", "revise", "questions", "need more", "clarify"];

const APPROVE_EMOJI = new Set(["👍", "✅", "✔", "✔️"]);

function hasPhrase(normalized: string, phrase: string): boolean {
  if (phrase.includes(" ")) return normalized.includes(phrase);
  return new RegExp(`\\b${phrase.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`).test(
    normalized,
  );
}

export function classifyDirectorReply(text: string): DirectorReplyIntent {
  const raw = (text ?? "").trim();
  if (!raw) return "ambiguous";

  if (APPROVE_EMOJI.has(raw)) return "approve";

  const upper = raw.toUpperCase();
  if (upper.startsWith("REJECT:") || upper.startsWith("REJECT ")) return "reject";
  if (upper.startsWith("CHANGES:") || upper.startsWith("CHANGES ")) return "changes";
  if (upper.startsWith("APPROVE")) return "approve";

  const normalized = raw.toLowerCase().replace(/\s+/g, " ");

  if (REJECT_PHRASES.some((p) => hasPhrase(normalized, p))) return "reject";
  if (CHANGES_PHRASES.some((p) => hasPhrase(normalized, p))) return "changes";
  if (APPROVE_PHRASES.some((p) => hasPhrase(normalized, p))) return "approve";

  return "ambiguous";
}

export function formatAuditComment(opts: {
  receivedAt: string;
  classification: DirectorReplyIntent;
  message: string;
  agent: string;
}): string {
  const agentIcon = agentIconImg(opts.agent);
  const body = [
    "## Director response (WhatsApp)",
    "",
    `**Received:** ${opts.receivedAt}`,
    `**Classification:** ${opts.classification}`,
    `**Message:** ${opts.message.trim()}`,
    `**Agent:** ${agentIcon} \`${opts.agent}\``,
    "",
    "_Posted automatically by Cloudflare Worker `whatsapp-webhook`._",
  ].join("\n");
  return formatSquadComment(body, "director");
}

export function normalizePhone(phone: string): string {
  return phone.replace(/\D/g, "");
}
