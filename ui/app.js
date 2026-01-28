const state = {
  runs: [],
  timeline: [],
  activeRun: null,
};

const timelineEl = document.getElementById("timeline");
const timelineMetaEl = document.getElementById("timeline-meta");
const runsEl = document.getElementById("runs");
const runsMetaEl = document.getElementById("runs-meta");

function setText(el, value) {
  if (el) {
    el.textContent = value;
  }
}

function summarize(rows) {
  const counts = {};
  for (const row of rows) {
    const key = row.event_type || "unknown";
    counts[key] = (counts[key] || 0) + 1;
  }
  document.querySelectorAll("[data-summary]").forEach((node) => {
    const key = node.getAttribute("data-summary");
    const value = counts[key] || 0;
    node.textContent = String(value);
  });
}

function formatRunTitle(run) {
  return run.kind === "job" ? run.job_id : run.session_id;
}

function formatRunMeta(run) {
  if (run.kind === "job") {
    return `${run.status || "unknown"} | exit ${run.exit_code ?? "--"}`;
  }
  return `${run.mode || "tui"} | exit ${run.exit_code ?? "--"}`;
}

function renderRuns(runs) {
  runsEl.innerHTML = "";
  if (!runs.length) {
    runsEl.innerHTML = `<div class="empty-state">[ NO RUNS FOUND ]</div>`;
    setText(runsMetaEl, "0 items");
    return;
  }
  runs.forEach((run) => {
    const item = document.createElement("div");
    item.className = "run-item";
    if (state.activeRun && run.key === state.activeRun.key) {
      item.classList.add("is-active");
    }
    item.innerHTML = `
      <div class="run-title">${formatRunTitle(run)}</div>
      <div class="run-meta">${formatRunMeta(run)}</div>
      <div class="run-meta">${run.started_at || "--"}${run.ended_at ? ` - ${run.ended_at}` : ""}</div>
    `;
    item.addEventListener("click", () => {
      state.activeRun = run;
      renderRuns(state.runs);
      loadTimeline();
    });
    runsEl.appendChild(item);
  });
  setText(runsMetaEl, `${runs.length} items`);
}

function renderTimeline(rows) {
  timelineEl.innerHTML = "";
  if (!rows.length) {
    timelineEl.innerHTML = `<div class="empty-state">[ NO EVENTS FOUND ]</div>`;
    setText(timelineMetaEl, "0 events");
    summarize([]);
    return;
  }
  const ordered = rows.slice().reverse();
  ordered.forEach((row) => {
    const div = document.createElement("div");
    div.className = "timeline-row";
    const target = deriveTarget(row);
    div.innerHTML = `
      <div class="timeline-meta">${row.ts || "--"} | ${row.source || "--"} | ${row.event_type || "--"}</div>
      <div class="timeline-main">${target}</div>
      <div class="timeline-meta">${row.comm || "--"} (pid ${row.pid ?? "--"})</div>
    `;
    timelineEl.appendChild(div);
  });
  setText(timelineMetaEl, `${rows.length} events`);
  summarize(rows);
}

function deriveTarget(row) {
  const details = row.details || {};
  switch (row.event_type) {
    case "exec":
      return details.cmd || details.cwd || "--";
    case "fs_create":
    case "fs_unlink":
    case "fs_meta":
      return details.path || details.cmd || "--";
    case "net_connect":
    case "net_send":
      if (details.net) {
        return `${details.net.dst_ip || "--"}:${details.net.dst_port || "--"}`;
      }
      return "--";
    case "dns_query":
    case "dns_response":
      if (details.dns) {
        return `${details.dns.query_name || "--"} ${details.dns.query_type || ""}`.trim();
      }
      return "--";
    case "unix_connect":
      if (details.unix) {
        return details.unix.path || "--";
      }
      return "--";
    default:
      return "--";
  }
}

async function fetchJson(path) {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

async function loadRuns() {
  const [sessionsData, jobsData] = await Promise.all([
    fetchJson("/api/sessions"),
    fetchJson("/api/jobs"),
  ]);
  const sessions = (sessionsData.sessions || []).map((item) => ({
    ...item,
    kind: "session",
    key: `session:${item.session_id}`,
  }));
  const jobs = (jobsData.jobs || []).map((item) => ({
    ...item,
    kind: "job",
    key: `job:${item.job_id}`,
  }));
  const runs = [...sessions, ...jobs].sort((a, b) =>
    String(a.started_at || "").localeCompare(String(b.started_at || ""))
  );
  state.runs = runs;
  renderRuns(runs);
}

async function loadTimeline() {
  const params = new URLSearchParams();
  params.set("limit", "500");
  if (state.activeRun) {
    if (state.activeRun.kind === "session") {
      params.set("session_id", state.activeRun.session_id);
    } else if (state.activeRun.kind === "job") {
      params.set("job_id", state.activeRun.job_id);
    }
  }
  const data = await fetchJson(`/api/timeline?${params.toString()}`);
  state.timeline = data.rows || [];
  renderTimeline(state.timeline);
}

async function boot() {
  try {
    await loadRuns();
    await loadTimeline();
  } catch (err) {
    timelineEl.innerHTML = `<div class="empty-state">[ FAILED TO LOAD ]</div>`;
    runsEl.innerHTML = `<div class="empty-state">[ FAILED TO LOAD ]</div>`;
  }
}

boot();
