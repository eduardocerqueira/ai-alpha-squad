// Fetch issues + comments for the dashboard via one GitHub GraphQL call.
import type { RawIssue } from "./director-data";

const QUERY = `
query($owner:String!, $repo:String!) {
  repository(owner:$owner, name:$repo) {
    issues(first:100, orderBy:{field:UPDATED_AT, direction:DESC}, states:[OPEN, CLOSED]) {
      nodes {
        number title body state updatedAt
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
    updatedAt: n.updatedAt,
    labels: (n.labels?.nodes ?? []).map((l) => l.name),
    comments: (n.comments?.nodes ?? []).map((c) => ({ body: c.body, createdAt: c.createdAt })),
  }));
}
