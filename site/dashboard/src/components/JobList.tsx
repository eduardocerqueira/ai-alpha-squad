import type { Bucket, JobCard } from "@/types";
import { cn, relativeTime } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area";

const BUCKET_META: Record<Bucket, { label: string; variant: "green" | "amber" | "danger" | "default" }> = {
  needs_you: { label: "Needs you", variant: "amber" },
  stuck: { label: "Stuck", variant: "danger" },
  in_progress: { label: "In progress", variant: "green" },
  completed: { label: "Done", variant: "default" },
};

export function JobList({
  jobs,
  selected,
  onSelect,
}: {
  jobs: JobCard[];
  selected: number;
  onSelect: (n: number) => void;
}) {
  return (
    <ScrollArea className="w-full whitespace-nowrap">
      <div className="flex gap-3 pb-3">
        {jobs.map((job) => {
          const meta = BUCKET_META[job.bucket];
          const active = job.number === selected;
          return (
            <Card
              key={job.number}
              role="button"
              tabIndex={0}
              onClick={() => onSelect(job.number)}
              onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && onSelect(job.number)}
              className={cn(
                "flex min-w-[230px] max-w-[280px] shrink-0 cursor-pointer flex-col gap-2 p-3 transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
                active ? "border-primary bg-card" : "bg-card/60 hover:border-foreground/30",
              )}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-mono text-xs text-muted-foreground">#{job.number}</span>
                <span className="flex items-center gap-1">
                  {job.blocked && <Badge variant="danger">blocked</Badge>}
                  <Badge variant={meta.variant}>{meta.label}</Badge>
                </span>
              </div>
              <span
                className={cn(
                  "line-clamp-2 whitespace-normal text-sm font-medium leading-snug",
                  active ? "text-foreground" : "text-muted-foreground",
                )}
              >
                {job.title}
              </span>
              <span className="text-[11px] text-muted-foreground">updated {relativeTime(job.updated_at)}</span>
            </Card>
          );
        })}
      </div>
      <ScrollBar orientation="horizontal" />
    </ScrollArea>
  );
}
