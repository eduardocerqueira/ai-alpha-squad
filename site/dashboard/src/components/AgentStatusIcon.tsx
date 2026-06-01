import type { AgentStatus } from "@/types";

export type NormStatus = "done" | "working" | "blocked" | "idle";

export function normalizeAgentStatus(status: AgentStatus | string): NormStatus {
  switch (status) {
    case "done":
      return "done";
    case "active":
    case "working":
      return "working";
    case "stuck":
    case "blocked":
      return "blocked";
    default:
      return "idle";
  }
}

const COLORS: Record<NormStatus, string> = {
  done: "var(--green)",
  working: "var(--green)",
  blocked: "var(--danger)",
  idle: "var(--muted)",
};

/** Hand-drawn SVG status indicator for an agent (idle / working / blocked / done). */
export function AgentStatusIcon({ status }: { status: NormStatus }) {
  const color = COLORS[status];
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      role="img"
      aria-label={status}
    >
      {status === "idle" && (
        <circle cx="12" cy="12" r="6" stroke={color} strokeWidth="2" opacity="0.7" />
      )}

      {status === "working" && (
        <g>
          <circle
            cx="12"
            cy="12"
            r="9"
            stroke={color}
            strokeWidth="2"
            strokeLinecap="round"
            strokeDasharray="14 40"
            opacity="0.9"
          >
            <animateTransform
              attributeName="transform"
              type="rotate"
              from="0 12 12"
              to="360 12 12"
              dur="1.4s"
              repeatCount="indefinite"
            />
          </circle>
          <circle cx="12" cy="12" r="3.5" fill={color}>
            <animate
              attributeName="opacity"
              values="1;0.4;1"
              dur="1.4s"
              repeatCount="indefinite"
            />
          </circle>
        </g>
      )}

      {status === "blocked" && (
        <g>
          <path
            d="M12 3 L22 20 H2 Z"
            fill="none"
            stroke={color}
            strokeWidth="2"
            strokeLinejoin="round"
          />
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
