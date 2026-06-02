import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AlertCircle, ExternalLink, GitPullRequest, LogOut, RefreshCw, RotateCcw } from "lucide-react";
import type { Bucket, Dashboard, JobCard } from "@/types";
import { cn, prNumber, relativeTime } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Timeline } from "@/components/Timeline";
import { AgentsPanel } from "@/components/AgentsPanel";
import { JobSwitcher } from "@/components/JobSwitcher";
import { StatusTabs, type TabDef, type TabKey } from "@/components/StatusTabs";
import { Login } from "@/components/Login";

// Live endpoint (Worker fetches fresh data); static jobs.json is the fallback
// when served without the Worker (plain static host).
const JOBS_URL = "/api/director/jobs";
const JOBS_FALLBACK_URL = "/director/jobs.json";
const REFRESH_MS = 30_000;

class UnauthorizedError extends Error {}

async function fetchDashboard(live = false): Promise<Dashboard> {
  // `live` asks the backend to rebuild from GitHub now (manual Refresh).
  // Supported by `squad-director-dashboard.py --serve --live`; harmless elsewhere.
  const primary = live ? `${JOBS_URL}?live=1&refresh=1` : JOBS_URL;
  for (const u of [primary, JOBS_URL, JOBS_FALLBACK_URL]) {
    const res = await fetch(u, { cache: "no-store" });
    if (res.status === 401) throw new UnauthorizedError();
    if (!res.ok) continue;
    const text = await res.text();
    if (text.trimStart().startsWith("{")) return JSON.parse(text) as Dashboard;
  }
  throw new Error(
    "dashboard data not available — run ./scripts/squad-director-dashboard.py --write, or git pull for a fresh snapshot.",
  );
}

// Job tabs: Open (needs you) · In progress · Blocked · Done (released/closed).
const GROUPS: { key: TabKey; label: string; buckets: Bucket[]; empty: string }[] = [
  { key: "open", label: "Open", buckets: ["needs_you"], empty: "Nothing needs your approval right now." },
  { key: "in_progress", label: "In progress", buckets: ["in_progress"], empty: "No jobs in progress right now." },
  { key: "blocked", label: "Blocked", buckets: ["stuck"], empty: "No blocked jobs — nice." },
  { key: "done", label: "Done", buckets: ["completed"], empty: "No completed jobs yet." },
];

function jobsInGroup(data: Dashboard | null, key: TabKey): JobCard[] {
  if (!data) return [];
  const group = GROUPS.find((g) => g.key === key)!;
  return group.buckets.flatMap((b) => data[b] ?? []);
}

export default function App() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  // null = checking, "" = not signed in, email = signed in
  const [authEmail, setAuthEmail] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabKey>(() => {
    const t = new URLSearchParams(window.location.search).get("tab");
    return t === "in_progress" || t === "blocked" || t === "done" ? t : "open";
  });
  const [selected, setSelected] = useState<number | null>(null);

  const load = useCallback(async (live = false) => {
    setLoading(true);
    try {
      setData(await fetchDashboard(live));
      setError(null);
    } catch (e) {
      if (e instanceof UnauthorizedError) {
        setAuthEmail("");
        return;
      }
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  // Check session, then load + auto-refresh while signed in.
  useEffect(() => {
    let timer: ReturnType<typeof setInterval> | undefined;
    (async () => {
      try {
        const res = await fetch("/api/director/auth/me", { cache: "no-store" });
        if (res.ok) {
          const me = (await res.json()) as { email?: string };
          setAuthEmail(me.email || "signed-in");
          load();
          timer = setInterval(() => load(), REFRESH_MS);
        } else {
          setAuthEmail("");
        }
      } catch {
        setAuthEmail("");
      }
    })();
    // Background tabs throttle setInterval — refetch when the tab regains focus
    // so returning to it (e.g. after approving on GitHub) shows current data.
    const onVisible = () => {
      if (document.visibilityState === "visible") load();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      if (timer) clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [load]);

  // Real-time push: when signed in, hold a WebSocket to the hub. CI pushes a
  // "refresh" the moment new data is published, so we refetch instantly instead
  // of waiting for the poll. Polling (above) stays as a fallback.
  useEffect(() => {
    if (!authEmail || import.meta.env.DEV) return; // dev has no WS endpoint
    let closed = false;
    let ws: WebSocket | undefined;
    let ping: ReturnType<typeof setInterval> | undefined;
    let retry: ReturnType<typeof setTimeout> | undefined;
    const connect = () => {
      if (closed) return;
      const proto = location.protocol === "https:" ? "wss" : "ws";
      ws = new WebSocket(`${proto}://${location.host}/api/director/live`);
      ws.onopen = () => {
        ping = setInterval(() => {
          try {
            ws?.send("ping");
          } catch {
            /* ignore */
          }
        }, 50_000);
      };
      ws.onmessage = (e) => {
        try {
          if (typeof e.data === "string" && e.data.includes("refresh")) load(true);
        } catch {
          /* ignore */
        }
      };
      ws.onclose = () => {
        if (ping) clearInterval(ping);
        if (!closed) retry = setTimeout(connect, 5_000);
      };
      ws.onerror = () => {
        try {
          ws?.close();
        } catch {
          /* ignore */
        }
      };
    };
    connect();
    return () => {
      closed = true;
      if (ping) clearInterval(ping);
      if (retry) clearTimeout(retry);
      try {
        ws?.close();
      } catch {
        /* ignore */
      }
    };
  }, [authEmail, load]);

  async function logout() {
    await fetch("/api/director/auth/logout", { method: "POST" }).catch(() => {});
    setAuthEmail("");
    setData(null);
  }

  const [retrying, setRetrying] = useState(false);
  const [retryNote, setRetryNote] = useState<{ ok: boolean; text: string } | null>(null);
  useEffect(() => setRetryNote(null), [selected]);

  async function retryJob(n: number) {
    setRetrying(true);
    setRetryNote(null);
    try {
      const res = await fetch("/api/director/retry", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ number: n }),
      });
      const body = (await res.json().catch(() => ({}))) as { error?: string };
      if (!res.ok) throw new Error(body.error || "Could not start the re-run.");
      setRetryNote({ ok: true, text: "Re-run started — the squad is picking it up." });
    } catch (e) {
      setRetryNote({ ok: false, text: e instanceof Error ? e.message : "Retry failed." });
    } finally {
      setRetrying(false);
    }
  }

  const tabs: TabDef[] = useMemo(
    () =>
      GROUPS.map((g) => ({
        key: g.key,
        label: g.label,
        count: jobsInGroup(data, g.key).length,
        alert:
          (g.key === "open" && (data?.counts.needs_you ?? 0) > 0) ||
          (g.key === "blocked" && (data?.counts.stuck ?? 0) > 0),
      })),
    [data],
  );

  // On first data load only, default to the first non-empty tab (unless the URL
  // pinned one). After that, never auto-switch — the user can freely open any
  // tab, including empty ones (which show an empty state).
  const didDefaultTab = useRef(false);
  useEffect(() => {
    if (!data || didDefaultTab.current) return;
    didDefaultTab.current = true;
    const urlTab = new URLSearchParams(window.location.search).get("tab");
    if (!urlTab && jobsInGroup(data, activeTab).length === 0) {
      const firstWithJobs = GROUPS.find((g) => jobsInGroup(data, g.key).length > 0);
      if (firstWithJobs) setActiveTab(firstWithJobs.key);
    }
  }, [data, activeTab]);

  const tabJobs = useMemo(() => jobsInGroup(data, activeTab), [data, activeTab]);

  // Keep the selected job valid within the active tab.
  useEffect(() => {
    if (tabJobs.length === 0) {
      setSelected(null);
    } else if (selected === null || !tabJobs.some((j) => j.number === selected)) {
      setSelected(tabJobs[0].number);
    }
  }, [tabJobs, selected]);

  const job = tabJobs.find((j) => j.number === selected) ?? null;
  const needsYou = data?.counts.needs_you ?? 0;
  const totalJobs = useMemo(
    () => GROUPS.reduce((n, g) => n + jobsInGroup(data, g.key).length, 0),
    [data],
  );

  // Conditional rendering only AFTER all hooks have run (rules of hooks).
  if (authEmail === null) {
    return (
      <div className="grid min-h-[60vh] place-items-center text-muted">
        <RefreshCw className="h-5 w-5 animate-spin" />
      </div>
    );
  }
  if (authEmail === "") return <Login />;

  return (
    <div className="mx-auto flex min-h-full max-w-7xl flex-col gap-5 px-5 py-6 lg:px-8">
      <header className="flex flex-wrap items-end justify-between gap-3 border-b border-border pb-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Director</h1>
          <p className="mt-1 text-sm text-muted">
            {data?.repo ?? "AI Alpha Squad"}
            {data && (
              <>
                {" · "}updated {relativeTime(data.generated_at)}
                {data.stale && <span className="text-amber"> · stale snapshot</span>}
              </>
            )}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {needsYou > 0 && (
            <Badge variant="amber">{needsYou} need{needsYou === 1 ? "s" : ""} you</Badge>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => load(true)}
            disabled={loading}
            title="Reload the latest status from GitHub"
          >
            <RefreshCw className={loading ? "h-4 w-4 animate-spin" : "h-4 w-4"} />
            Refresh
          </Button>
          <Button variant="ghost" size="sm" onClick={logout} title={authEmail || undefined}>
            <LogOut className="h-4 w-4" />
            Sign out
          </Button>
        </div>
      </header>

      {error && (
        <div className="flex items-start gap-2 rounded-lg border border-danger/50 bg-[color:rgba(248,113,113,0.08)] p-4 text-sm text-danger">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <div>
            <p>{error}</p>
            <p className="mt-1 text-muted">
              Terminal fallback: <code className="font-mono text-xs">./scripts/squad-director-now.sh</code>
            </p>
          </div>
        </div>
      )}

      {!error && totalJobs === 0 && !loading && (
        <div className="rounded-lg border border-border bg-surface p-8 text-center text-muted">
          No squad jobs found.
        </div>
      )}

      {totalJobs > 0 && (
        <>
          <StatusTabs tabs={tabs} active={activeTab} onChange={setActiveTab} />
          {tabJobs.length > 0 ? (
            <JobSwitcher jobs={tabJobs} selected={selected ?? tabJobs[0].number} onSelect={setSelected} />
          ) : (
            <div className="rounded-lg border border-dashed border-border bg-surface/40 p-10 text-center text-sm text-muted">
              {GROUPS.find((g) => g.key === activeTab)?.empty ?? "No jobs in this tab."}
            </div>
          )}
        </>
      )}

      {job && (
        <div className="grid gap-6 lg:grid-cols-[80%_20%]">
          {/* 80% — timeline for the selected job */}
          <section className="min-w-0">
            <div className="mb-4 flex flex-wrap items-start justify-between gap-2">
              <div className="min-w-0">
                <a
                  href={job.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group inline-flex items-center gap-1.5 text-lg font-semibold text-text hover:text-green"
                >
                  <span className="font-mono text-sm text-muted">#{job.number}</span>
                  <span className="truncate">{job.title}</span>
                  <ExternalLink className="h-4 w-4 shrink-0 opacity-0 transition-opacity group-hover:opacity-100" />
                </a>
                <p className="mt-1 text-sm text-muted">{job.headline || job.summary}</p>
                {job.blocked && (
                  <p className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-danger/50 bg-[color:rgba(248,113,113,0.08)] px-2 py-1 text-xs text-danger">
                    <AlertCircle className="h-3.5 w-3.5" />
                    <span><code className="font-mono">blocked</code> label set on the issue — clear it if the squad has moved on.</span>
                  </p>
                )}
                {retryNote && (
                  <p className={cn("mt-2 text-xs", retryNote.ok ? "text-green" : "text-danger")}>{retryNote.text}</p>
                )}
              </div>
              <div className="flex shrink-0 items-center gap-2">
                {(job.bucket === "stuck" || job.blocked || job.bucket === "completed") && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      if (
                        job.bucket === "completed" &&
                        !window.confirm(
                          `Re-open and re-run #${job.number}? It will reopen the issue, reset it to director-approved, and re-run the developer → QA flow.`,
                        )
                      )
                        return;
                      retryJob(job.number);
                    }}
                    disabled={retrying}
                    title={
                      job.bucket === "completed"
                        ? "Reopen this issue and re-run the squad"
                        : "Re-run the orchestrator (clears the failure count + removes the blocked label)"
                    }
                  >
                    <RotateCcw className={retrying ? "h-3.5 w-3.5 animate-spin" : "h-3.5 w-3.5"} />
                    {retrying
                      ? job.bucket === "completed"
                        ? "Re-opening…"
                        : "Retrying…"
                      : job.bucket === "completed"
                        ? "Re-open & re-run"
                        : "Retry job"}
                  </Button>
                )}
                {job.target_pr_url && (
                  <a
                    href={job.target_pr_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    title={job.target_pr_url}
                    className={cn(
                      "inline-flex shrink-0 items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-medium transition-colors",
                      job.target_pr_merged
                        ? "border-[var(--green-dim)] bg-[color:rgba(34,197,94,0.12)] text-green hover:border-green"
                        : "border-border bg-surface text-text hover:border-green hover:text-green",
                    )}
                  >
                    <GitPullRequest className="h-3.5 w-3.5" />
                    PR{prNumber(job.target_pr_url)} {job.target_pr_merged ? "merged" : "open"}
                    <ExternalLink className="h-3 w-3 opacity-70" />
                  </a>
                )}
              </div>
            </div>
            <Timeline events={job.events} />
          </section>

          {/* 20% — agents assigned to the work */}
          <AgentsPanel agents={job.agents} />
        </div>
      )}
    </div>
  );
}
