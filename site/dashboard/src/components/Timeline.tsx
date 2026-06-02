import {
  ArrowUpRight,
  Check,
  CircleDashed,
  GitPullRequest,
  Loader2,
  TriangleAlert,
  UserCheck,
} from "lucide-react";
import type { EventStatus, TimelineEvent } from "@/types";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

const NODE: Record<
  EventStatus,
  { icon: typeof Check; ring: string; bg: string; fg: string }
> = {
  done: {
    icon: Check,
    ring: "border-brand-green-dim",
    bg: "bg-brand-green/15",
    fg: "text-brand-green",
  },
  current: {
    icon: Loader2,
    ring: "border-brand-green",
    bg: "bg-brand-green/12",
    fg: "text-brand-green",
  },
  director: {
    icon: UserCheck,
    ring: "border-brand-amber",
    bg: "bg-brand-amber/15",
    fg: "text-brand-amber",
  },
  blocked: {
    icon: TriangleAlert,
    ring: "border-brand-danger",
    bg: "bg-brand-danger/15",
    fg: "text-brand-danger",
  },
  pending: {
    icon: CircleDashed,
    ring: "border-border",
    bg: "bg-secondary",
    fg: "text-muted-foreground",
  },
};

function TimelineNode({ status }: { status: EventStatus }) {
  const conf = NODE[status];
  const Icon = conf.icon;
  return (
    <span
      className={cn(
        "relative z-10 flex h-9 w-9 shrink-0 items-center justify-center rounded-full border",
        conf.ring,
        conf.bg,
      )}
    >
      <Icon
        className={cn(
          "h-4 w-4",
          conf.fg,
          status === "current" && "animate-spin [animation-duration:2.4s]",
        )}
      />
    </span>
  );
}

function DirectorRequest({ event }: { event: TimelineEvent }) {
  if (!event.action) return null;
  return (
    <div className="mt-2 rounded-lg border border-brand-amber/60 bg-brand-amber/[0.07] p-3">
      <p className="text-sm text-foreground">{event.action.message}</p>
      <a href={event.action.url} target="_blank" rel="noopener noreferrer">
        <Button size="sm" className="mt-3">
          {event.action.label}
          <ArrowUpRight className="h-3.5 w-3.5" />
        </Button>
      </a>
    </div>
  );
}

export function Timeline({ events }: { events: TimelineEvent[] }) {
  return (
    <ol className="relative">
      {events.map((event, i) => {
        const isLast = i === events.length - 1;
        const isDirector = event.status === "director";
        const dimmed = event.status === "pending";
        return (
          <li key={event.key} className="relative flex gap-4 pb-6 last:pb-0">
            {!isLast && (
              <span className="absolute left-[18px] top-9 -bottom-0 w-px bg-border" aria-hidden />
            )}
            <TimelineNode status={event.status} />
            <div
              className={cn(
                "flex-1 pt-1",
                isDirector && "-mt-1 rounded-xl border border-brand-amber/40 bg-card p-3",
              )}
            >
              <div className="flex flex-wrap items-center gap-2">
                <h3 className={cn("text-sm font-semibold", dimmed ? "text-muted-foreground" : "text-foreground")}>
                  {event.title}
                </h3>
                <Badge
                  variant={
                    event.status === "director"
                      ? "amber"
                      : event.status === "blocked"
                        ? "danger"
                        : event.status === "done" || event.status === "current"
                          ? "green"
                          : "default"
                  }
                >
                  {event.owner}
                </Badge>
              </div>
              {event.detail && !isDirector && (
                <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{event.detail}</p>
              )}
              {event.pr_url && (
                <a
                  href={event.pr_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-1 inline-flex items-center gap-1 text-xs text-brand-green hover:underline"
                >
                  <GitPullRequest className="h-3.5 w-3.5" />
                  View pull request
                </a>
              )}
              {isDirector && <DirectorRequest event={event} />}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
