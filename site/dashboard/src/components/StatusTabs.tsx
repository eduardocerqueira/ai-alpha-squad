import { cn } from "@/lib/utils";

export type TabKey = "open" | "in_progress" | "blocked" | "done";

export interface TabDef {
  key: TabKey;
  label: string;
  count: number;
  /** highlight (amber) when this tab holds jobs that need the Director. */
  alert?: boolean;
}

export function StatusTabs({
  tabs,
  active,
  onChange,
}: {
  tabs: TabDef[];
  active: TabKey;
  onChange: (key: TabKey) => void;
}) {
  return (
    <div role="tablist" className="flex items-center gap-1 border-b border-border">
      {tabs.map((tab) => {
        const isActive = tab.key === active;
        return (
          <button
            key={tab.key}
            role="tab"
            aria-selected={isActive}
            onClick={() => onChange(tab.key)}
            className={cn(
              "relative -mb-px flex items-center gap-2 border-b-2 px-3 py-2 text-sm font-medium transition-colors",
              isActive
                ? "border-green text-text"
                : "border-transparent text-muted hover:text-text",
            )}
          >
            {tab.label}
            <span
              className={cn(
                "inline-flex min-w-5 items-center justify-center rounded-full px-1.5 py-0.5 text-xs font-semibold",
                tab.alert
                  ? "bg-[color:rgba(251,191,36,0.18)] text-amber"
                  : isActive
                    ? "bg-surface-2 text-text"
                    : "bg-surface-2 text-muted",
              )}
            >
              {tab.count}
            </span>
          </button>
        );
      })}
    </div>
  );
}
