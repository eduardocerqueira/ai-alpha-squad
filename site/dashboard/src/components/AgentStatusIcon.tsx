import type { AgentStatus } from "@/types";

// Honest role-states derived from issue artifacts (not live run state):
//  done · review (PR open, awaiting merge) · progress (its turn / in flight) ·
//  idle (waiting for an earlier phase) · blocked.
export type NormStatus = "done" | "running" | "review" | "progress" | "idle" | "blocked";

export function normalizeAgentStatus(status: AgentStatus | string, detail = ""): NormStatus {
  switch (status) {
    case "done":
      return "done";
    case "running":
      return "running";
    case "active":
    case "working":
      return /pr open|merge when ready|review/i.test(detail) ? "review" : "progress";
    case "stuck":
    case "blocked":
      return "blocked";
    default:
      return "idle";
  }
}

const COLORS: Record<NormStatus, string> = {
  done: "hsl(var(--brand-green))",
  running: "hsl(var(--brand-green))",
  review: "hsl(var(--brand-amber))",
  progress: "hsl(var(--brand-amber))",
  idle: "hsl(var(--muted-foreground))",
  blocked: "hsl(var(--brand-danger))",
};

/** Static SVG status indicator for an agent — no spinner (the dashboard can't
 *  see live Action runs, so it never implies one). */
export function AgentStatusIcon({ status }: { status: NormStatus }) {
  const color = COLORS[status];
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" role="img" aria-label={status}>
      {status === "idle" && (
        <circle cx="12" cy="12" r="6" stroke={color} strokeWidth="2" opacity="0.7" />
      )}

      {status === "progress" && (
        <g>
          <circle cx="12" cy="12" r="8" stroke={color} strokeWidth="2" opacity="0.35" />
          <circle cx="12" cy="12" r="3.5" fill={color} />
        </g>
      )}

      {status === "running" && (
        <g>
          <circle cx="12" cy="12" r="8" stroke={color} strokeWidth="2" opacity="0.25" />
          <path d="M12 4 a8 8 0 0 1 8 8" stroke={color} strokeWidth="2" strokeLinecap="round" fill="none">
            <animateTransform
              attributeName="transform"
              type="rotate"
              from="0 12 12"
              to="360 12 12"
              dur="1s"
              repeatCount="indefinite"
            />
          </path>
        </g>
      )}

      {status === "review" && (
        <g stroke={color} strokeWidth="2" fill="none" strokeLinecap="round">
          {/* git-pull-request glyph */}
          <circle cx="7" cy="6" r="2.2" />
          <circle cx="7" cy="18" r="2.2" />
          <line x1="7" y1="8.2" x2="7" y2="15.8" />
          <circle cx="17" cy="18" r="2.2" />
          <path d="M17 15.8 V11 a3 3 0 0 0-3-3 H10.5" />
        </g>
      )}

      {status === "blocked" && (
        <g>
          <path d="M12 3 L22 20 H2 Z" fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" />
          <line x1="12" y1="9" x2="12" y2="14" stroke={color} strokeWidth="2" strokeLinecap="round" />
          <circle cx="12" cy="17" r="1.1" fill={color} />
        </g>
      )}

      {status === "done" && (
        <g>
          <circle cx="12" cy="12" r="9" fill={color} opacity="0.18" />
          <circle cx="12" cy="12" r="9" stroke={color} strokeWidth="1.5" />
          <path
            d="M8 12.5 L11 15.5 L16.5 9"
            fill="none"
            stroke={color}
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </g>
      )}
    </svg>
  );
}
