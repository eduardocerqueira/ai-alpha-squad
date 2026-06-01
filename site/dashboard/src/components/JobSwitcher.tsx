import type { Bucket, JobCard } from "@/types";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

const BUCKET_META: Record<Bucket, { label: string; variant: "green" | "amber" | "danger" | "default" }> = {
  needs_you: { label: "Needs you", variant: "amber" },
  stuck: { label: "Stuck", variant: "danger" },
  in_progress: { label: "In progress", variant: "green" },
  completed: { label: "Done", variant: "default" },
};

export function JobSwitcher({
  jobs,
  selected,
  onSelect,
}: {
  jobs: JobCard[];
  selected: number;
  onSelect: (n: number) => void;
}) {
  return (
    <div className="flex gap-2 overflow-x-auto pb-1">
      {jobs.map((job) => {
        const meta = BUCKET_META[job.bucket];
        const active = job.number === selected;
        return (
          <button
            key={job.number}
            onClick={() => onSelect(job.number)}
            className={cn(
              "group flex min-w-[200px] max-w-[260px] shrink-0 flex-col gap-1.5 rounded-lg border px-3 py-2.5 text-left transition-colors",
              active
                ? "border-green bg-surface"
                : "border-border bg-surface/60 hover:border-muted",
            )}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="font-mono text-xs text-muted">#{job.number}</span>
              <span className="flex items-center gap-1">
                {job.blocked && <Badge variant="danger">blocked</Badge>}
                <Badge variant={meta.variant}>{meta.label}</Badge>
              </span>
            </div>
            <span
              className={cn(
                "line-clamp-2 text-sm font-medium leading-snug",
                active ? "text-text" : "text-muted group-hover:text-text",
              )}
            >
              {job.title}
            </span>
          </button>
        );
      })}
    </div>
  );
}
