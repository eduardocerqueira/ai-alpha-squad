/** Short Director WhatsApp lifecycle messages (mirrors src/ai_alpha_squad/whatsapp/lifecycle.py). */

type Step = { headline: string; status: string; next: string };

const STEPS: Record<string, Step> = {
  "inbound-approve": {
    headline: "APPROVE received",
    status: "Your WhatsApp reply was recorded on GitHub.",
    next: "Architect is starting (director-approved).",
  },
  "inbound-reject": {
    headline: "REJECT received",
    status: "Your WhatsApp reply was recorded on GitHub.",
    next: "Business Owner will revise the analysis.",
  },
  "inbound-changes": {
    headline: "CHANGES received",
    status: "Your WhatsApp reply was recorded on GitHub.",
    next: "Business Owner will clarify on the issue.",
  },
};

export function formatLifecycleMessage(
  step: string,
  issueNumber: number,
  title: string,
  repo: string,
): string | null {
  const cfg = STEPS[step];
  if (!cfg) return null;
  const shortTitle = title.length <= 72 ? title : `${title.slice(0, 69)}...`;
  const url = `https://github.com/${repo}/issues/${issueNumber}`;
  return [
    `[AI Alpha Squad] ${cfg.headline}`,
    "",
    `#${issueNumber} — ${shortTitle}`,
    `Now: ${cfg.status}`,
    `Next: ${cfg.next}`,
    "",
    url,
  ].join("\n");
}
