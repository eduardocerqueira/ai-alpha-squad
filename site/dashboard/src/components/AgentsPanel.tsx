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
  done: "text-brand-green",
  running: "text-brand-green",
  review: "text-brand-amber",
  progress: "text-brand-amber",
  blocked: "text-brand-danger",
  idle: "text-muted-foreground",
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
      <p className="mt-0.5 truncate text-xs text-muted-foreground" title={detail}>
        {detail}
      </p>
    );
  }
  const url = match[1];
  const text = detail.slice(0, match.index).replace(/[\s:—-]+$/, "").trim();
  const isPr = /\/pull\/(\d+)/.test(url);
  const prNum = url.match(/\/pull\/(\d+)/);
  return (
    <p className="mt-0.5 text-xs text-muted-foreground">
      {text && <span>{text} · </span>}
      <a
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-1 text-brand-green hover:underline"
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
    <li className="flex items-start gap-3 rounded-lg border border-border bg-card px-3 py-2.5">
      <span className="mt-0.5 shrink-0">
        <AgentStatusIcon status={norm} />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <span className="truncate text-sm font-medium text-foreground">{label}</span>
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
            className="mt-1 inline-flex items-center gap-1 text-[11px] text-muted-foreground hover:text-brand-green"
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
    <ul className="flex flex-col gap-2">
      {agents.map((a) => (
        <AgentRow key={a.role} agent={a} />
      ))}
      {agents.length === 0 && (
        <li className="rounded-lg border border-border bg-card px-3 py-4 text-sm text-muted-foreground">
          No agents assigned yet.
        </li>
      )}
    </ul>
  );
}
