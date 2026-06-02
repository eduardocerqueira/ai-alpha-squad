import type { Bucket, Dashboard, JobCard } from "@/types";

export type TabKey = "open" | "in_progress" | "blocked" | "done";

export interface Group {
  key: TabKey;
  label: string;
  buckets: Bucket[];
  empty: string;
}

// Job tabs: Open (needs you) · In progress · Blocked · Done (released/closed).
export const GROUPS: Group[] = [
  { key: "open", label: "Open", buckets: ["needs_you"], empty: "Nothing needs your approval right now." },
  { key: "in_progress", label: "In progress", buckets: ["in_progress"], empty: "No jobs in progress right now." },
  { key: "blocked", label: "Blocked", buckets: ["stuck"], empty: "No blocked jobs — nice." },
  { key: "done", label: "Done", buckets: ["completed"], empty: "No completed jobs yet." },
];

export function jobsInGroup(data: Dashboard | null, key: TabKey): JobCard[] {
  if (!data) return [];
  const group = GROUPS.find((g) => g.key === key)!;
  return group.buckets.flatMap((b) => data[b] ?? []);
}

export function isTabKey(v: string | null): v is TabKey {
  return v === "open" || v === "in_progress" || v === "blocked" || v === "done";
}
