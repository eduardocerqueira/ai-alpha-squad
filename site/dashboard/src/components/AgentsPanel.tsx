import { ExternalLink, GitPullRequest } from "lucide-react";
import type { Agent } from "@/types";
import { cn } from "@/lib/utils";
import { AgentStatusIcon, normalizeAgentStatus, type NormStatus } from "@/components/AgentStatusIcon";

const ROLE_LABELS: Record<string, string> = {
  "business-owner": "Business Owner",
  architect: "Architect",
  developer: "Developer",
  qa: "QA",
  security: "Security",
  devops: "DevOps",
  "tech-writer": "Tech Writer",
  "release-manager": "Release Manager",
};

const STATUS_TEXT: Record<NormStatus, string> = {
  done: "text-green",
  running: "text-green",
  review: "text-amber",
  progress: "text-amber",
  blocked: "text-danger",
  idle: "text-muted",
};

const STATUS_LABEL: Record<NormStatus, string> = {
  done: "Done",
  running: "Running",
  review: "In review",
  progress: "In progress",
  blocked: "Blocked",
  idle: "Idle",
};

/** Render an agent's detail, turning any embedded PR/issue URL into a link. */
function AgentDetail({ detail }: { detail: string }) {
  const match = detail.match(/(https?:\/\/\S+)/);
  if (!match) {
    return (
      <p className="mt-0.5 truncate text-xs text-muted" title={detail}>
        {detail}
      </p>
    );
  }
  const url = match[1];
  const text = detail.slice(0, match.index).replace(/[\s:—-]+$/, "").trim();
  const isPr = /\/pull\/(\d+)/.test(url);
  const prNum = url.match(/\/pull\/(\d+)/);
  return (
    <p className="mt-0.5 text-xs text-muted">
      {text && <span>{text} · </span>}
      <a
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-1 text-green hover:underline"
      >
        <GitPullRequest className="h-3 w-3" />
        {isPr ? `PR #${prNum![1]}` : "View"}
      </a>
    </p>
  );
}

function AgentRow({ agent }: { agent: Agent }) {
  const norm = normalizeAgentStatus(agent.status, agent.detail);
  const label = ROLE_LABELS[agent.role] ?? agent.role;
  return (
    <li className="flex items-start gap-3 rounded-lg border border-border bg-surface px-3 py-2.5">
      <span className="mt-0.5 shrink-0">
        <AgentStatusIcon status={norm} />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <span className="truncate text-sm font-medium text-text">{label}</span>
          <span className={cn("shrink-0 text-[11px] font-medium uppercase tracking-wide", STATUS_TEXT[norm])}>
            {STATUS_LABEL[norm]}
          </span>
        </div>
        {agent.detail && <AgentDetail detail={agent.detail} />}
        {agent.issue_url && agent.issue_number && (
          <a
            href={agent.issue_url}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-1 inline-flex items-center gap-1 text-[11px] text-muted hover:text-green"
          >
            #{agent.issue_number}
            <ExternalLink className="h-3 w-3" />
          </a>
        )}
      </div>
    </li>
  );
}

export function AgentsPanel({ agents }: { agents: Agent[] }) {
  return (
    <aside className="flex flex-col gap-3">
      <h2 className="text-xs font-semibold uppercase tracking-[0.08em] text-muted">
        Squad ({agents.length})
      </h2>
      <ul className="flex flex-col gap-2">
        {agents.map((a) => (
          <AgentRow key={a.role} agent={a} />
        ))}
        {agents.length === 0 && (
          <li className="rounded-lg border border-border bg-surface px-3 py-4 text-sm text-muted">
            No agents assigned yet.
          </li>
        )}
      </ul>
    </aside>
  );
}
