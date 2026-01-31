const state = {
  runs: [],
  timeline: [],
  activeRun: null,
  loadingTimeline: false,
  filters: {
    sources: new Set(),
    range: "1h",
  },
};

const timelineEl = document.getElementById("timeline");
const timelineMetaEl = document.getElementById("timeline-meta");
const runsEl = document.getElementById("runs");
const runsMetaEl = document.getElementById("runs-meta");
const timestampFormatter = new Intl.DateTimeFormat("en-US", {
  timeZone: "America/New_York",
  year: "numeric",
  month: "short",
  day: "2-digit",
  hour: "numeric",
  minute: "2-digit",
  second: "2-digit",
  hour12: true,
  timeZoneName: "short",
});

function setText(el, value) {
  if (el) {
    el.textContent = value;
  }
}

function summarize(rows) {
  let processes = 0;
  let fileChanges = 0;
  let networkCalls = 0;
  for (const row of rows) {
    switch (row.event_type) {
      case "exec":
        processes += 1;
        break;
      case "fs_create":
      case "fs_unlink":
      case "fs_meta":
        fileChanges += 1;
        break;
      case "net_summary":
        networkCalls += 1;
        break;
      default:
        break;
    }
  }
  const counts = {
    processes,
    file_changes: fileChanges,
    network_calls: networkCalls,
  };
  document.querySelectorAll("[data-summary]").forEach((node) => {
    const key = node.getAttribute("data-summary");
    const value = counts[key] || 0;
    node.textContent = String(value);
  });
}

function initFilters() {
  const sourceButtons = document.querySelectorAll(".filter-button[data-source]");
  sourceButtons.forEach((btn) => {
    if (btn.classList.contains("is-active")) {
      state.filters.sources.add(btn.dataset.source);
    }
    btn.addEventListener("click", () => {
      const source = btn.dataset.source;
      if (state.filters.sources.has(source)) {
        state.filters.sources.delete(source);
        btn.classList.remove("is-active");
      } else {
        state.filters.sources.add(source);
        btn.classList.add("is-active");
      }
      loadTimeline();
    });
  });

  const rangeButtons = document.querySelectorAll(".filter-button[data-range]");
  rangeButtons.forEach((btn) => {
    if (btn.classList.contains("is-active")) {
      state.filters.range = btn.dataset.range;
    }
    btn.addEventListener("click", () => {
      rangeButtons.forEach((node) => node.classList.remove("is-active"));
      btn.classList.add("is-active");
      state.filters.range = btn.dataset.range;
      loadTimeline();
    });
  });
}

function rangeToMs(range) {
  switch (range) {
    case "15m":
      return 15 * 60 * 1000;
    case "1h":
      return 60 * 60 * 1000;
    case "24h":
      return 24 * 60 * 60 * 1000;
    case "7d":
      return 7 * 24 * 60 * 60 * 1000;
    default:
      return null;
  }
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

function formatRunTimeRange(run) {
  const start = formatTimestamp(run.started_at);
  const end = formatTimestamp(run.ended_at);
  if (start === "--" && end === "--") {
    return "--";
  }
  if (start !== "--" && end !== "--") {
    return `${start} - ${end}`;
  }
  if (start !== "--") {
    return start;
  }
  return end;
}

function renderRuns(runs) {
  runsEl.innerHTML = "";
  if (!runs.length) {
    runsEl.innerHTML = `<div class="empty-state">[ NO AGENTS FOUND ]</div>`;
    setText(runsMetaEl, "0 agents");
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
      <div class="run-meta">${formatRunTimeRange(run)}</div>
    `;
    item.addEventListener("click", () => {
      state.activeRun = run;
      renderRuns(state.runs);
      loadTimeline();
    });
    runsEl.appendChild(item);
  });
  setText(runsMetaEl, `${runs.length} agents`);
}

function formatTimestamp(ts) {
  if (!ts) {
    return "--";
  }
  const date = new Date(ts);
  if (Number.isNaN(date.getTime())) {
    return "--";
  }
  return timestampFormatter.format(date);
}

function formatSourceLabel(source) {
  if (!source) {
    return "--";
  }
  const normalized = String(source).toLowerCase();
  if (normalized === "audit") {
    return "Files";
  }
  if (normalized === "ebpf") {
    return "Searches";
  }
  return source;
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
    const sourceLabel = formatSourceLabel(row.source);
    const timestamp = formatTimestamp(row.ts);
    div.innerHTML = `
      <div class="timeline-meta">${timestamp} | ${sourceLabel}</div>
      <div class="timeline-main">${target}</div>
      <div class="timeline-meta">Program: ${row.comm || "--"} (PID ${row.pid ?? "--"})</div>
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
    case "net_summary": {
      const ip = details.dst_ip || "--";
      const port = details.dst_port || "--";
      const names = Array.isArray(details.dns_names) ? details.dns_names : [];
      if (names.length) {
        const mainName = names.join(", ");
        return `${mainName} (IP: ${ip}:${port})`;
      }
      return `${ip}:${port}`;
    }
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
  if (state.loadingTimeline) {
    return;
  }
  state.loadingTimeline = true;
  const params = new URLSearchParams();
  params.set("limit", "500");
  if (!state.filters.sources.size) {
    renderTimeline([]);
    state.loadingTimeline = false;
    return;
  }
  params.set("source", [...state.filters.sources].join(","));
  const windowMs = rangeToMs(state.filters.range);
  if (windowMs) {
    const end = new Date();
    const start = new Date(end.getTime() - windowMs);
    params.set("start", start.toISOString());
    params.set("end", end.toISOString());
  }
  if (state.activeRun) {
    if (state.activeRun.kind === "session") {
      params.set("session_id", state.activeRun.session_id);
    } else if (state.activeRun.kind === "job") {
      params.set("job_id", state.activeRun.job_id);
    }
  }
  try {
    const data = await fetchJson(`/api/timeline?${params.toString()}`);
    state.timeline = data.rows || [];
    renderTimeline(state.timeline);
  } finally {
    state.loadingTimeline = false;
  }
}

async function boot() {
  try {
    initFilters();
    await loadRuns();
    await loadTimeline();
    setInterval(() => {
      if (!document.hidden) {
        loadTimeline();
      }
    }, 2000);
  } catch (err) {
    timelineEl.innerHTML = `<div class="empty-state">[ FAILED TO LOAD ]</div>`;
    runsEl.innerHTML = `<div class="empty-state">[ FAILED TO LOAD ]</div>`;
  }
}

boot();
