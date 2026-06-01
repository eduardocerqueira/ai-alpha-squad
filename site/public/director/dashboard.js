(function () {
  const API_PATHS = ["/api/director/jobs", "/director/jobs.json"];

  const els = {
    loading: document.getElementById("loading"),
    error: document.getElementById("error"),
    stats: document.getElementById("stats"),
    columns: document.getElementById("columns"),
    generated: document.getElementById("generated-at"),
    lists: {
      needs_you: document.getElementById("list-needs"),
      in_progress: document.getElementById("list-progress"),
      stuck: document.getElementById("list-stuck"),
      completed: document.getElementById("list-done"),
    },
  };

  function renderCard(job) {
    const li = document.createElement("li");
    li.className = "job-card";
    const pr = job.target_pr_url
      ? `<a href="${escapeAttr(job.target_pr_url)}" target="_blank" rel="noopener">Target PR</a>`
      : "";
    const target = job.target_repo
      ? `<span>${escapeHtml(job.target_repo)}</span>`
      : "";
    li.innerHTML = `
      <a class="job-title" href="${escapeAttr(job.url)}" target="_blank" rel="noopener">
        #${job.number} ${escapeHtml(job.title)}
      </a>
      <div class="job-meta">
        <span class="lifecycle">${escapeHtml(job.lifecycle || "—")}</span>
        · ${escapeHtml(job.active_agent)}
        ${target ? ` · ${target}` : ""}
      </div>
      <p class="job-summary">${escapeHtml(job.summary)}</p>
      <div class="job-links">${pr}</div>
    `;
    return li;
  }

  function renderList(container, jobs) {
    container.innerHTML = "";
    if (!jobs || jobs.length === 0) {
      const empty = document.createElement("li");
      empty.className = "job-empty";
      empty.textContent = "None";
      container.appendChild(empty);
      return;
    }
    jobs.forEach((job) => container.appendChild(renderCard(job)));
  }

  function renderStats(counts) {
    const pills = [
      ["Needs you", counts.needs_you, "needs"],
      ["In progress", counts.in_progress, "progress"],
      ["Stuck", counts.stuck, "stuck"],
      ["Completed", counts.completed, "done"],
    ];
    els.stats.innerHTML = pills
      .map(
        ([label, n]) =>
          `<span class="stat-pill"><strong>${n}</strong>${label}</span>`,
      )
      .join("");
  }

  function showData(data) {
    els.loading.classList.add("hidden");
    els.error.classList.add("hidden");
    els.stats.classList.remove("hidden");
    els.columns.classList.remove("hidden");
    renderStats(data.counts);
    renderList(els.lists.needs_you, data.needs_you);
    renderList(els.lists.in_progress, data.in_progress);
    renderList(els.lists.stuck, data.stuck);
    renderList(els.lists.completed, data.completed);
    const at = data.generated_at ? new Date(data.generated_at) : null;
    els.generated.textContent = at
      ? `Updated ${at.toLocaleString()}`
      : "";
  }

  function showError(msg) {
    els.loading.classList.add("hidden");
    els.error.classList.remove("hidden");
    els.error.textContent = msg;
  }

  async function fetchJson(url) {
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) throw new Error(`${url} → ${res.status}`);
    return res.json();
  }

  async function load() {
    els.error.classList.add("hidden");
    for (const path of API_PATHS) {
      try {
        const data = await fetchJson(path);
        showData(data);
        return;
      } catch (e) {
        console.warn(path, e);
      }
    }
    showError(
      "Could not load job data. Run locally: ./scripts/squad-director-dashboard.py --serve then open http://127.0.0.1:8788/",
    );
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function escapeAttr(s) {
    return escapeHtml(s).replace(/'/g, "&#39;");
  }

  document.getElementById("btn-refresh").addEventListener("click", () => {
    els.loading.classList.remove("hidden");
    load();
  });

  load();
  setInterval(load, 60_000);
})();
