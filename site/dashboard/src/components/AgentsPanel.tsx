import { Cpu, ExternalLink, GitPullRequest } from "lucide-react";
import type { Agent } from "@/types";
import { cn } from "@/lib/utils";
import { AgentStatusIcon, normalizeAgentStatus, type NormStatus } from "@/components/AgentStatusIcon";
import { currentModelUse, ModelChip } from "@/components/ModelHistory";

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
  running: "text-brand-amber",
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

function AgentModelLine({ agent, isActive }: { agent: Agent; isActive: boolean }) {
  const current = currentModelUse(agent);
  if (!current) {
    if (!isActive) return null;
    return (
      <p className="mt-1.5 flex items-center gap-1.5 text-[11px] text-muted-foreground">
        <Cpu className="h-3 w-3 shrink-0 opacity-70" />
        Model not reported yet
      </p>
    );
  }
  return (
    <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
      <span className="flex items-center gap-1 text-[11px] text-muted-foreground">
        <Cpu className="h-3 w-3 shrink-0 opacity-70" />
        {isActive ? "Running on" : "Model"}
      </span>
      <ModelChip use={current} escalated={current.kind === "escalation"} />
    </div>
  );
}

function AgentRow({ agent, isActive }: { agent: Agent; isActive: boolean }) {
  const norm = normalizeAgentStatus(agent.status, agent.detail);
  const label = ROLE_LABELS[agent.role] ?? agent.role;
  return (
    <li
      className={cn(
        "flex items-start gap-3 rounded-lg border bg-card px-3 py-2.5",
        isActive ? "border-brand-amber/50 ring-1 ring-brand-amber/20" : "border-border",
      )}
    >
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
        <AgentModelLine agent={agent} isActive={isActive} />
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

export function AgentsPanel({
  agents,
  activeAgent,
}: {
  agents: Agent[];
  /** Role slug of the agent currently executing (from job.active_agent). */
  activeAgent?: string | null;
}) {
  const active = (activeAgent || "").trim();
  return (
    <ul className="flex flex-col gap-2">
      {agents.map((a) => (
        <AgentRow key={a.role} agent={a} isActive={!!active && a.role === active} />
      ))}
      {agents.length === 0 && (
        <li className="rounded-lg border border-border bg-card px-3 py-4 text-sm text-muted-foreground">
          No agents assigned yet.
        </li>
      )}
    </ul>
  );
}
