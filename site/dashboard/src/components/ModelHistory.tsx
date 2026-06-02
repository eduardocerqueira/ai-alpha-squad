import { ArrowUp, Cpu } from "lucide-react";
import type { Agent, ModelUse } from "@/types";
import { cn, modelShort, relativeTime } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from "@/components/ui/hover-card";

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

/** Back-compat: older snapshots only carry the latest `model`. */
function historyOf(agent: Agent): ModelUse[] {
  if (agent.model_history && agent.model_history.length) return agent.model_history;
  return agent.model ? [{ model: agent.model, at: "", kind: "result" }] : [];
}

function ModelChip({ use, escalated }: { use: ModelUse; escalated: boolean }) {
  return (
    <HoverCard openDelay={120} closeDelay={60}>
      <HoverCardTrigger asChild>
        <span
          className={cn(
            "inline-flex max-w-full items-center gap-1 rounded-md border px-1.5 py-0.5 font-mono text-[11px]",
            escalated
              ? "border-brand-amber/40 bg-brand-amber/10 text-brand-amber"
              : "border-border bg-secondary text-foreground",
          )}
        >
          {escalated && <ArrowUp className="h-3 w-3 shrink-0" />}
          <span className="truncate">{modelShort(use.model)}</span>
        </span>
      </HoverCardTrigger>
      <HoverCardContent className="w-auto max-w-xs">
        <p className="break-all font-mono text-xs text-foreground">{use.model}</p>
        <p className="mt-1 text-xs text-muted-foreground">
          {use.kind === "escalation" ? "Escalated to this model" : "Posted a result on this model"}
          {use.at ? ` · ${relativeTime(use.at)}` : ""}
        </p>
      </HoverCardContent>
    </HoverCard>
  );
}

/**
 * Per-agent model timeline. Agents announce the AI model they ran on via issue
 * comments; this shows the full sequence (hand-offs + escalations) rather than
 * only the latest, so the Director can see e.g. a developer bumped from a flash
 * model up to a stronger coder after QA pushed back.
 */
export function ModelHistory({ agents }: { agents: Agent[] }) {
  const rows = agents
    .map((a) => ({ agent: a, history: historyOf(a) }))
    .filter((r) => r.history.length > 0);

  if (rows.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-border px-3 py-4 text-xs text-muted-foreground">
        No model activity reported yet.
      </p>
    );
  }

  return (
    <ul className="flex flex-col gap-3">
      {rows.map(({ agent, history }) => {
        const label = ROLE_LABELS[agent.role] ?? agent.role;
        return (
          <li key={agent.role} className="rounded-lg border border-border bg-card p-3">
            <div className="flex items-center gap-1.5 text-xs font-medium text-foreground">
              <Cpu className="h-3.5 w-3.5 text-muted-foreground" />
              {label}
              {history.length > 1 && (
                <Badge variant="amber" className="ml-auto">
                  {history.length} models
                </Badge>
              )}
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              {history.map((use, i) => (
                <div key={`${use.model}-${i}`} className="flex items-center gap-1.5">
                  {i > 0 && <span className="text-muted-foreground">→</span>}
                  <ModelChip use={use} escalated={i > 0 || use.kind === "escalation"} />
                </div>
              ))}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
