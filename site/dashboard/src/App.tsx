import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import {
  AlertCircle,
  BadgeCheck,
  Check,
  ExternalLink,
  GitPullRequest,
  RefreshCw,
  RotateCcw,
  Square,
  X,
} from "lucide-react";
import type { Dashboard, JobCard } from "@/types";
import { GROUPS, isTabKey, jobsInGroup, type TabKey } from "@/lib/jobs";
import { cn, prNumber, relativeTime } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/AppSidebar";
import { JobList } from "@/components/JobList";
import { Timeline } from "@/components/Timeline";
import { AgentsPanel } from "@/components/AgentsPanel";
import { ModelHistory } from "@/components/ModelHistory";
import { Login } from "@/components/Login";
import { ConfirmDialog, PromptDialog } from "@/components/DirectorDialog";

// Live endpoint (Worker fetches fresh data); static jobs.json is the fallback
// when served without the Worker (plain static host).
const JOBS_URL = "/api/director/jobs";
const JOBS_FALLBACK_URL = "/director/jobs.json";
const REFRESH_MS = 30_000;
// Baked at build time from site/VERSION; matches the marketing-site footer.
const BUILD_VERSION = typeof __APP_VERSION__ === "string" ? __APP_VERSION__ : "0.0.0";

class UnauthorizedError extends Error {}

async function fetchDashboard(live = false): Promise<Dashboard> {
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

export default function App() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  // null = checking, "" = not signed in, email = signed in
  const [authEmail, setAuthEmail] = useState<string | null>(null);
  const [version, setVersion] = useState(BUILD_VERSION);
  const [activeTab, setActiveTab] = useState<TabKey>(() => {
    const t = new URLSearchParams(window.location.search).get("tab");
    return isTabKey(t) ? t : "open";
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
  // "refresh" the moment new data is published.
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
  const [modelLadder, setModelLadder] = useState<string[]>([]);
  const [chosenModel, setChosenModel] = useState("default");
  useEffect(() => {
    fetch("/api/config", { cache: "no-store" })
      .then((r) => r.json())
      .then((c: { modelLadder?: string[]; version?: string }) => {
        setModelLadder(c.modelLadder ?? []);
        if (c.version) setVersion(c.version);
      })
      .catch(() => {});
  }, []);

  async function retryJob(n: number, model?: string) {
    setRetrying(true);
    try {
      const res = await fetch("/api/director/retry", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ number: n, ...(model ? { model } : {}) }),
      });
      const body = (await res.json().catch(() => ({}))) as { error?: string };
      if (!res.ok) throw new Error(body.error || "Could not start the re-run.");
      toast.success("Re-run started — the squad is picking it up.");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Retry failed.");
    } finally {
      setRetrying(false);
    }
  }

  const [stopping, setStopping] = useState(false);
  async function stopJob(n: number) {
    setStopping(true);
    try {
      const res = await fetch("/api/director/stop", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ number: n }),
      });
      const body = (await res.json().catch(() => ({}))) as { error?: string; cancelled?: number };
      if (!res.ok) throw new Error(body.error || "Could not stop the job.");
      toast.success(
        body.cancelled
          ? `Stopped — cancelled ${body.cancelled} run${body.cancelled === 1 ? "" : "s"}. Use Retry to resume.`
          : "Stopped — the job is held in Blocked. Use Retry to resume.",
      );
      load(true);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Stop failed.");
    } finally {
      setStopping(false);
    }
  }

  // On first data load only, default to the first non-empty tab (unless the URL
  // pinned one). After that, never auto-switch.
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

  const job: JobCard | null = tabJobs.find((j) => j.number === selected) ?? null;
  const totalJobs = useMemo(
    () => GROUPS.reduce((n, g) => n + jobsInGroup(data, g.key).length, 0),
    [data],
  );
  const groupLabel = GROUPS.find((g) => g.key === activeTab)?.label ?? "Jobs";
  const canRetry = !!job && (job.bucket === "stuck" || job.blocked || job.bucket === "completed");
  const canStop = !!job && job.bucket === "in_progress";
  const canDeliveryGate = !!job && job.lifecycle === "release-candidate" && job.bucket === "needs_you";
  const canMarkDone =
    !!job && job.lifecycle !== "released" && job.bucket !== "completed";

  const [deliveryBusy, setDeliveryBusy] = useState(false);
  const [markDoneBusy, setMarkDoneBusy] = useState(false);
  const [acceptOpen, setAcceptOpen] = useState(false);
  const [rejectOpen, setRejectOpen] = useState(false);
  const [markDoneOpen, setMarkDoneOpen] = useState(false);
  const [stopOpen, setStopOpen] = useState(false);
  const [rerunOpen, setRerunOpen] = useState(false);

  async function deliveryGate(n: number, action: "accept" | "reject", reason?: string) {
    setDeliveryBusy(true);
    try {
      const res = await fetch("/api/director/delivery-gate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ number: n, action, ...(reason ? { reason } : {}) }),
      });
      const payload = (await res.json().catch(() => ({}))) as { error?: string };
      if (!res.ok) throw new Error(payload.error || "Could not update delivery gate.");
      toast.success(
        action === "accept"
          ? "Job accepted by Director — issue closed and marked released."
          : "Delivery rejected — developer and QA will rework.",
      );
      load(true);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Delivery gate failed.");
    } finally {
      setDeliveryBusy(false);
    }
  }

  async function markDone(n: number, note?: string) {
    setMarkDoneBusy(true);
    try {
      const res = await fetch("/api/director/mark-done", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ number: n, ...(note ? { note } : {}) }),
      });
      const payload = (await res.json().catch(() => ({}))) as { error?: string };
      if (!res.ok) throw new Error(payload.error || "Could not mark job done.");
      toast.success("Job marked done — moved to Done tab.");
      load(true);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Mark done failed.");
    } finally {
      setMarkDoneBusy(false);
    }
  }

  if (authEmail === null) {
    return (
      <div className="grid min-h-svh place-items-center text-muted-foreground">
        <RefreshCw className="h-5 w-5 animate-spin" />
      </div>
    );
  }
  if (authEmail === "") return <Login version={version} />;

  return (
    <SidebarProvider>
      <AppSidebar
        data={data}
        active={activeTab}
        onSelect={setActiveTab}
        email={authEmail}
        repo={data?.repo ?? "AI Alpha Squad"}
        onSignOut={logout}
      />
      <SidebarInset>
        <header className="sticky top-0 z-20 flex h-14 shrink-0 items-center gap-2 border-b border-border bg-background/80 px-4 backdrop-blur">
          <SidebarTrigger className="-ml-1" />
          <Separator orientation="vertical" className="mr-1 h-5" />
          <div className="flex min-w-0 flex-col">
            <h1 className="truncate text-sm font-semibold leading-tight">{groupLabel}</h1>
            <p className="truncate text-xs text-muted-foreground">
              {data ? (
                <>
                  updated {relativeTime(data.generated_at)}
                  {data.stale && <span className="text-brand-amber"> · stale snapshot</span>}
                </>
              ) : (
                "loading…"
              )}
            </p>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <Badge variant="outline" className="hidden font-mono sm:inline-flex">
              v{version}
            </Badge>
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
          </div>
        </header>

        <div className="mx-auto flex w-full max-w-[1400px] flex-1 flex-col gap-5 p-4 lg:p-6">
          {error && (
            <div className="flex items-start gap-2 rounded-lg border border-brand-danger/50 bg-brand-danger/[0.08] p-4 text-sm text-brand-danger">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <div>
                <p>{error}</p>
                <p className="mt-1 text-muted-foreground">
                  Terminal fallback:{" "}
                  <code className="font-mono text-xs">./scripts/squad-director-now.sh</code>
                </p>
              </div>
            </div>
          )}

          {!error && totalJobs === 0 && !loading && (
            <div className="rounded-lg border border-border bg-card p-8 text-center text-muted-foreground">
              No squad jobs found.
            </div>
          )}

          {totalJobs > 0 &&
            (tabJobs.length > 0 ? (
              <JobList jobs={tabJobs} selected={selected ?? tabJobs[0].number} onSelect={setSelected} />
            ) : (
              <div className="rounded-lg border border-dashed border-border bg-card/40 p-10 text-center text-sm text-muted-foreground">
                {GROUPS.find((g) => g.key === activeTab)?.empty ?? "No jobs in this tab."}
              </div>
            ))}

          {job && (
            <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
              {/* Selected job — header + timeline */}
              <section className="min-w-0">
                <div className="mb-10 flex flex-col gap-3">
                  <div className="min-w-0">
                    <a
                      href={job.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="group inline-flex items-center gap-1.5 text-lg font-semibold hover:text-brand-green"
                    >
                      <span className="font-mono text-sm text-muted-foreground">#{job.number}</span>
                      <span className="truncate">{job.title}</span>
                      <ExternalLink className="h-4 w-4 shrink-0 opacity-0 transition-opacity group-hover:opacity-100" />
                    </a>
                    <p className="mt-1 text-sm text-muted-foreground">{job.headline || job.summary}</p>
                    {job.needs_human ? (
                      <div className="mt-2 rounded-md border border-brand-danger/50 bg-brand-danger/[0.08] px-2.5 py-2 text-xs text-brand-danger">
                        <p className="inline-flex items-center gap-1.5 font-medium">
                          <AlertCircle className="h-3.5 w-3.5" />
                          Needs human assistance — the AI squad exhausted all attempts.
                        </p>
                        {job.stuck_reasons.length > 0 && (
                          <p className="mt-1 text-brand-danger/90">{job.stuck_reasons[0]}</p>
                        )}
                        <p className="mt-1 text-brand-danger/80">
                          Review the PR and take over, then Retry (optionally with a stronger model).
                        </p>
                      </div>
                    ) : (
                      job.blocked && (
                        <p className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-brand-danger/50 bg-brand-danger/[0.08] px-2 py-1 text-xs text-brand-danger">
                          <AlertCircle className="h-3.5 w-3.5" />
                          <span>
                            <code className="font-mono">blocked</code> label set on the issue — clear
                            it if the squad has moved on.
                          </span>
                        </p>
                      )
                    )}
                  </div>

                  {(canDeliveryGate || canMarkDone || canRetry || canStop || job.target_pr_url) && (
                  <div className="flex flex-wrap items-center gap-2">
                    {canMarkDone && (
                      <>
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={markDoneBusy}
                          onClick={() => setMarkDoneOpen(true)}
                          title="Mark this job done and remove it from In progress"
                        >
                          <BadgeCheck className="h-3.5 w-3.5" />
                          {markDoneBusy ? "Working…" : "Mark done"}
                        </Button>
                        <PromptDialog
                          open={markDoneOpen}
                          onOpenChange={setMarkDoneOpen}
                          title={`Mark #${job.number} done?`}
                          description="Adds the released label, clears active lifecycle labels, and closes the issue. Use when the PR is merged or work finished outside the normal delivery gate."
                          confirmLabel="Mark done"
                          fieldLabel="Note (optional)"
                          placeholder="e.g. PR merged manually"
                          loading={markDoneBusy}
                          onConfirm={(note) => markDone(job.number, note || undefined)}
                        />
                      </>
                    )}
                    {canDeliveryGate && (
                      <>
                        <Button
                          size="sm"
                          disabled={deliveryBusy}
                          onClick={() => setAcceptOpen(true)}
                          title="Accept developer + QA delivery"
                        >
                          <Check className="h-3.5 w-3.5" />
                          {deliveryBusy ? "Working…" : "Accept delivery"}
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={deliveryBusy}
                          className="border-brand-danger/50 text-brand-danger hover:bg-brand-danger/10"
                          onClick={() => setRejectOpen(true)}
                          title="Reject delivery and send developer + QA for another round"
                        >
                          <X className="h-3.5 w-3.5" />
                          Reject delivery
                        </Button>
                        <ConfirmDialog
                          open={acceptOpen}
                          onOpenChange={setAcceptOpen}
                          title={`Accept delivery for #${job.number}?`}
                          description="The job will be marked released and the issue will be closed."
                          confirmLabel="Accept delivery"
                          loading={deliveryBusy}
                          onConfirm={() => deliveryGate(job.number, "accept")}
                        />
                        <PromptDialog
                          open={rejectOpen}
                          onOpenChange={setRejectOpen}
                          title={`Reject delivery for #${job.number}?`}
                          description="Developer and QA will rework. Add an optional note for the squad (quality, not working, etc.)."
                          confirmLabel="Reject delivery"
                          fieldLabel="Note for the squad"
                          placeholder="What should developer and QA fix?"
                          loading={deliveryBusy}
                          onConfirm={(reason) =>
                            deliveryGate(job.number, "reject", reason || undefined)
                          }
                        />
                      </>
                    )}
                    {canStop && (
                      <>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setStopOpen(true)}
                          disabled={stopping}
                          title="Cancel the running Actions run and halt this job"
                        >
                          <Square
                            className={cn("h-3.5 w-3.5 text-brand-danger", stopping && "animate-pulse")}
                          />
                          {stopping ? "Stopping…" : "Stop execution"}
                        </Button>
                        <ConfirmDialog
                          open={stopOpen}
                          onOpenChange={setStopOpen}
                          title={`Stop #${job.number}?`}
                          description="This cancels the in-flight Actions run and holds the job in Blocked. Use Retry to resume."
                          confirmLabel="Stop execution"
                          variant="destructive"
                          loading={stopping}
                          onConfirm={() => stopJob(job.number)}
                        />
                      </>
                    )}
                    {canRetry && modelLadder.length > 0 && (
                      <Select value={chosenModel} onValueChange={setChosenModel} disabled={retrying}>
                        <SelectTrigger className="h-8 w-[12rem] text-xs">
                          <SelectValue placeholder="Model: default" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="default">Model: default</SelectItem>
                          {modelLadder.map((m) => (
                            <SelectItem key={m} value={m}>
                              {m.includes("/") ? m.split("/").pop() : m}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                    {canRetry && (
                      <>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            if (job.bucket === "completed") setRerunOpen(true);
                            else
                              retryJob(
                                job.number,
                                chosenModel === "default" ? undefined : chosenModel,
                              );
                          }}
                          disabled={retrying}
                          title={
                            job.bucket === "completed"
                              ? "Reopen this issue and re-run the squad"
                              : "Re-run the orchestrator (clears the failure count + removes the blocked label)"
                          }
                        >
                          <RotateCcw
                            className={retrying ? "h-3.5 w-3.5 animate-spin" : "h-3.5 w-3.5"}
                          />
                          {retrying
                            ? job.bucket === "completed"
                              ? "Re-opening…"
                              : "Retrying…"
                            : job.bucket === "completed"
                              ? "Re-open & re-run"
                              : "Retry job"}
                        </Button>
                        {job.bucket === "completed" && (
                          <ConfirmDialog
                            open={rerunOpen}
                            onOpenChange={setRerunOpen}
                            title={`Re-open and re-run #${job.number}?`}
                            description="The issue will reopen, reset to director-approved, and re-run the developer → QA flow."
                            confirmLabel="Re-open & re-run"
                            loading={retrying}
                            onConfirm={() =>
                              retryJob(
                                job.number,
                                chosenModel === "default" ? undefined : chosenModel,
                              )
                            }
                          />
                        )}
                      </>
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
                            ? "border-brand-green-dim bg-brand-green/12 text-brand-green hover:border-brand-green"
                            : "border-border bg-card hover:border-brand-green hover:text-brand-green",
                        )}
                      >
                        <GitPullRequest className="h-3.5 w-3.5" />
                        PR{prNumber(job.target_pr_url)} {job.target_pr_merged ? "merged" : "open"}
                        <ExternalLink className="h-3 w-3 opacity-70" />
                      </a>
                    )}
                  </div>
                  )}
                </div>
                <Timeline events={job.events} />
              </section>

              {/* Right rail — squad + model history */}
              <aside className="flex min-w-0 flex-col gap-6">
                <div>
                  <h2 className="mb-3 text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                    Squad ({job.agents.length})
                  </h2>
                  <AgentsPanel agents={job.agents} activeAgent={job.active_agent} />
                </div>
                <div>
                  <h2 className="mb-3 text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                    Model history
                  </h2>
                  <ModelHistory agents={job.agents} />
                </div>
              </aside>
            </div>
          )}
        </div>
      </SidebarInset>
    </SidebarProvider>
  );
}
