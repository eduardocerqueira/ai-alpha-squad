// Shape of site/public/director/jobs.json, produced by
// src/ai_alpha_squad/director_dashboard.py :: DirectorDashboard.to_json().

export type AgentRole =
  | "business-owner"
  | "architect"
  | "developer"
  | "qa"
  | "security"
  | "devops"
  | "tech-writer"
  | "release-manager";

export type AgentStatus =
  | "done"
  | "active"
  | "working"
  | "running"
  | "waiting"
  | "idle"
  | "stuck"
  | "blocked";

export interface Agent {
  role: string;
  status: AgentStatus;
  issue_number: number | null;
  issue_url: string | null;
  detail: string;
  model?: string | null;
}

export type EventStatus = "done" | "current" | "director" | "blocked" | "pending";

export interface EventAction {
  label: string;
  url: string;
  message: string;
}

export interface TimelineEvent {
  key: string;
  title: string;
  owner: string;
  status: EventStatus;
  detail: string;
  action?: EventAction;
  pr_url?: string;
}

export type Bucket = "needs_you" | "in_progress" | "stuck" | "completed";

export interface JobCard {
  number: number;
  title: string;
  url: string;
  lifecycle: string | null;
  active_agent: string;
  bucket: Bucket;
  blocked: boolean;
  updated_at: string;
  target_repo: string | null;
  target_pr_url: string | null;
  target_pr_merged: boolean;
  summary: string;
  headline: string;
  director_action: string;
  labels: string[];
  stuck_reasons: string[];
  suggested_action: string;
  agents: Agent[];
  events: TimelineEvent[];
}

export interface Dashboard {
  generated_at: string;
  repo: string;
  counts: Record<Bucket, number>;
  needs_you: JobCard[];
  in_progress: JobCard[];
  stuck: JobCard[];
  completed: JobCard[];
  stale?: boolean;
  fetch_error?: string;
}
