(function () {
  const JOBS_URL = "/director/jobs.json";

  const els = {
    lead: document.getElementById("lead"),
    error: document.getElementById("error"),
    sectionMove: document.getElementById("section-move"),
    sectionAttention: document.getElementById("section-attention"),
    listMove: document.getElementById("list-move"),
    listAttention: document.getElementById("list-attention"),
  };

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function normalize(data) {
    return {
      yourMove: data.your_move || data.needs_you || [],
      attention: data.attention || data.blocked || data.stuck || data.running || data.in_progress || [],
    };
  }

  function itemRow(job, move) {
    const li = document.createElement("li");
    li.className = "director-item" + (move ? " director-item--move" : " director-item--attention");
    const title = job.title || `Issue #${job.number}`;
    const line = move
      ? job.action || job.director_action || "Reply on GitHub (APPROVE / REQUEST CHANGES)."
      : job.headline || job.summary || "Open issue — squad should be working.";
    li.innerHTML = `
      <a class="title" href="${escapeHtml(job.url)}" target="_blank" rel="noopener">
        #${job.number} ${escapeHtml(title)}
      </a>
      <p class="line">${escapeHtml(line)}</p>
    `;
    return li;
  }

  function fillList(el, jobs, move) {
    el.innerHTML = "";
    jobs.forEach((j) => el.appendChild(itemRow(j, move)));
  }

  function show(data) {
    els.error.classList.add("hidden");
    const { yourMove, attention } = normalize(data);

    if (yourMove.length) {
      els.lead.textContent = `${yourMove.length} approval(s) waiting on you.`;
    } else if (attention.length) {
      els.lead.textContent = `No approval needed — but ${attention.length} job(s) may be stuck.`;
    } else {
      els.lead.textContent = "All clear — no open squad jobs need you.";
    }

    els.sectionMove.hidden = yourMove.length === 0;
    if (yourMove.length) fillList(els.listMove, yourMove, true);

    els.sectionAttention.hidden = attention.length === 0;
    if (attention.length) fillList(els.listAttention, attention, false);
  }

  function showError(msg) {
    els.lead.textContent = "Could not load snapshot.";
    els.error.classList.remove("hidden");
    els.error.textContent = msg + " Use: ./scripts/squad-director-now.sh";
  }

  async function load() {
    try {
      const res = await fetch(JOBS_URL, { cache: "no-store" });
      if (!res.ok) throw new Error("missing jobs.json — git pull or wait for CI");
      show(await res.json());
    } catch (e) {
      showError(String(e.message || e));
    }
  }

  load();
})();
