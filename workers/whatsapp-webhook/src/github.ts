export async function postIssueComment(env: Env, issueNumber: number, body: string): Promise<void> {
  const owner = env.GITHUB_OWNER;
  const repo = env.SQUAD_WORK_QUEUE_REPO;
  const res = await fetch(
    `https://api.github.com/repos/${owner}/${repo}/issues/${issueNumber}/comments`,
    {
      method: "POST",
      headers: githubHeaders(env),
      body: JSON.stringify({ body }),
    },
  );
  if (!res.ok) {
    throw new Error(`GitHub comment failed ${res.status}: ${await res.text()}`);
  }
}

export async function getIssueTitle(env: Env, issueNumber: number): Promise<string> {
  const owner = env.GITHUB_OWNER;
  const repo = env.SQUAD_WORK_QUEUE_REPO;
  const res = await fetch(
    `https://api.github.com/repos/${owner}/${repo}/issues/${issueNumber}`,
    { headers: githubHeaders(env) },
  );
  if (!res.ok) {
    return `Issue #${issueNumber}`;
  }
  const data = (await res.json()) as { title?: string };
  return data.title ?? `Issue #${issueNumber}`;
}

export async function getIssueLabels(env: Env, issueNumber: number): Promise<string[]> {
  const owner = env.GITHUB_OWNER;
  const repo = env.SQUAD_WORK_QUEUE_REPO;
  const res = await fetch(
    `https://api.github.com/repos/${owner}/${repo}/issues/${issueNumber}`,
    { headers: githubHeaders(env) },
  );
  if (!res.ok) {
    throw new Error(`GitHub issue fetch failed ${res.status}`);
  }
  const data = (await res.json()) as { labels: Array<{ name: string }> };
  return data.labels.map((l) => l.name);
}

export async function addIssueLabel(
  env: Env,
  issueNumber: number,
  label: string,
): Promise<void> {
  const owner = env.GITHUB_OWNER;
  const repo = env.SQUAD_WORK_QUEUE_REPO;
  const res = await fetch(
    `https://api.github.com/repos/${owner}/${repo}/issues/${issueNumber}/labels`,
    {
      method: "POST",
      headers: githubHeaders(env),
      body: JSON.stringify({ labels: [label] }),
    },
  );
  if (!res.ok) {
    throw new Error(`GitHub add label failed ${res.status}: ${await res.text()}`);
  }
}

export async function removeIssueLabel(
  env: Env,
  issueNumber: number,
  label: string,
): Promise<void> {
  const owner = env.GITHUB_OWNER;
  const repo = env.SQUAD_WORK_QUEUE_REPO;
  const res = await fetch(
    `https://api.github.com/repos/${owner}/${repo}/issues/${issueNumber}/labels/${encodeURIComponent(label)}`,
    { method: "DELETE", headers: githubHeaders(env) },
  );
  if (res.status !== 204 && !res.ok) {
    throw new Error(`GitHub remove label failed ${res.status}: ${await res.text()}`);
  }
}

function githubHeaders(env: Env): Record<string, string> {
  return {
    Authorization: `Bearer ${env.GITHUB_TOKEN}`,
    Accept: "application/vnd.github+json",
    "Content-Type": "application/json",
    "User-Agent": "ai-alpha-squad-whatsapp-webhook",
  };
}
