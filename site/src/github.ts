// Fetch issues + comments for the dashboard via one GitHub GraphQL call.
import type { RawIssue } from "./director-data";

const QUERY = `
query($owner:String!, $repo:String!) {
  repository(owner:$owner, name:$repo) {
    issues(first:100, orderBy:{field:UPDATED_AT, direction:DESC}, states:[OPEN, CLOSED]) {
      nodes {
        number title body state stateReason updatedAt closedAt
        labels(first:20) { nodes { name } }
        comments(first:100) { nodes { body createdAt } }
      }
    }
  }
}`;

interface GqlNode {
  number: number;
  title: string | null;
  body: string | null;
  state: string | null;
  stateReason?: string | null;
  updatedAt: string | null;
  labels: { nodes: { name: string }[] };
  comments: { nodes: { body: string | null; createdAt: string | null }[] };
}

export async function fetchIssues(repo: string, token: string): Promise<RawIssue[]> {
  const [owner, name] = repo.split("/");
  const res = await fetch("https://api.github.com/graphql", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      "User-Agent": "ai-alpha-squad-dashboard",
    },
    body: JSON.stringify({ query: QUERY, variables: { owner, repo: name } }),
  });
  if (!res.ok) throw new Error(`GitHub GraphQL HTTP ${res.status}`);
  const data = (await res.json()) as {
    data?: { repository?: { issues?: { nodes?: GqlNode[] } } };
    errors?: { message?: string }[];
  };
  if (data.errors?.length) throw new Error(`GraphQL: ${data.errors[0].message}`);
  const nodes = data.data?.repository?.issues?.nodes ?? [];
  return nodes.map((n) => ({
    number: n.number,
    title: n.title,
    body: n.body,
    state: n.state,
    stateReason: n.stateReason,
    updatedAt: n.updatedAt,
    labels: (n.labels?.nodes ?? []).map((l) => l.name),
    comments: (n.comments?.nodes ?? []).map((c) => ({ body: c.body, createdAt: c.createdAt })),
  }));
}

const LIVE_AGENT_WORKFLOWS = ["squad-actions-agent.yml"];
const LIVE_AGENT_SLUGS = ["business-owner", "developer", "qa", "devops"];

/** In-flight Squad Actions runs keyed by queue issue number → agent slug. */
export async function fetchLiveAgentRuns(repo: string, token: string): Promise<Map<number, string>> {
  const map = new Map<number, string>();
  const headers = {
    Authorization: `Bearer ${token}`,
    Accept: "application/vnd.github+json",
    "User-Agent": "ai-alpha-squad-dashboard",
  };
  for (const wf of LIVE_AGENT_WORKFLOWS) {
    for (const status of ["in_progress", "queued"] as const) {
      const res = await fetch(
        `https://api.github.com/repos/${repo}/actions/workflows/${wf}/runs?status=${status}&per_page=30`,
        { headers },
      );
      if (!res.ok) continue;
      const data = (await res.json()) as { workflow_runs?: { name?: string; display_title?: string }[] };
      for (const run of data.workflow_runs ?? []) {
        const title = `${run.display_title || ""} ${run.name || ""}`;
        const issueMatch = title.match(/issue\s*#(\d+)/i);
        if (!issueMatch) continue;
        const issue = Number(issueMatch[1]);
        let agent: string | null = null;
        for (const slug of LIVE_AGENT_SLUGS) {
          if (title.toLowerCase().includes(`· ${slug} ·`) || title.toLowerCase().includes(` ${slug} ·`)) {
            agent = slug;
            break;
          }
        }
        if (agent) map.set(issue, agent);
      }
    }
  }
  return map;
}
