const DEFAULT_ICON_REPO = "eduardocerqueira/ai-alpha-squad";
const DEFAULT_ICON_REF = "main";
const ICON_SIZE_INLINE = 22;
const ICON_SIZE_AVATAR = 40;

const AGENT_SLUGS = new Set([
  "orchestrator",
  "business-owner",
  "architect",
  "developer",
  "qa",
  "security",
  "devops",
  "release-manager",
  "tech-writer",
  "director",
]);

const ALIAS: Record<string, string> = {
  business_owner: "business-owner",
  release_manager: "release-manager",
  tech_writer: "tech-writer",
  "squad-orchestrator": "orchestrator",
};

export function normalizeAgentSlug(slug: string): string {
  const key = ALIAS[slug.trim().toLowerCase()] ?? slug.trim().toLowerCase().replace(/\s+/g, "-");
  if (!AGENT_SLUGS.has(key)) {
    throw new Error(`Unknown agent slug: ${slug}`);
  }
  return key;
}

export function iconUrl(
  slug: string,
  opts?: { repo?: string; ref?: string },
): string {
  const agent = normalizeAgentSlug(slug);
  const repo = opts?.repo ?? DEFAULT_ICON_REPO;
  const ref = opts?.ref ?? DEFAULT_ICON_REF;
  const [owner, name] = repo.split("/");
  return `https://raw.githubusercontent.com/${owner}/${name}/${ref}/assets/agents/${agent}.svg`;
}

export function agentIconImg(slug: string, size = ICON_SIZE_INLINE, opts?: { repo?: string; ref?: string }): string {
  const agent = normalizeAgentSlug(slug);
  const url = iconUrl(agent, opts);
  const title = agent.replace(/-/g, " ");
  return `<img src="${url}" width="${size}" height="${size}" alt="${agent}" title="${title}" style="vertical-align:middle" />`;
}

export function formatSquadComment(
  messageMd: string,
  avatar: string,
  opts?: { repo?: string; ref?: string },
): string {
  const url = iconUrl(avatar, opts);
  const agent = normalizeAgentSlug(avatar);
  const alt = agent.replace(/-/g, " ");
  const body = messageMd.trim();
  return [
    "<table>",
    "<tr>",
    `<td width="48" valign="top"><img src="${url}" width="${ICON_SIZE_AVATAR}" height="${ICON_SIZE_AVATAR}" alt="${alt}" title="${alt}" /></td>`,
    `<td valign="top">\n\n${body}\n\n</td>`,
    "</tr>",
    "</table>",
  ].join("\n");
}
