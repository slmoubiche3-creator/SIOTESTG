const TEAMS = ["Support", "Tech", "Billing", "Deliverability", "Migration", "Product", "Security & Legal"];
const ASSIGNEES = ["Alex Rivera", "Maya Chen", "Sam Martin", "Jordan Lee"];

const state = {
  view: "all",
  messages: [],
  summary: { total: 0, critical: 0, needs_review: 0, alerts: [], related_groups: [] },
  search: "",
  urgency: "",
  status: "",
  needsReview: false,
  group: "",
};

const $ = (id) => document.getElementById(id);

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
}

function formatDate(value) {
  if (!value) return "Date needs review";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Date needs review";
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }).format(date);
}

function titleForView() {
  if (state.view === "alerts") return "Urgent now";
  if (state.view === "review") return "Needs review";
  if (state.view === "groups") return "Related issues";
  if (state.view === "group") return "Related requests";
  if (TEAMS.includes(state.view)) return state.view;
  return "All requests";
}

function visibleMessages() {
  const needle = state.search.trim().toLowerCase();
  return state.messages.filter((message) => {
    if (state.view === "alerts" && message.urgency !== "Critical") return false;
    if (state.view === "review" && !message.needs_review) return false;
    if (TEAMS.includes(state.view) && message.team !== state.view) return false;
    if (state.view === "group" && message.related_group !== state.group) return false;
    if (state.urgency && message.urgency !== state.urgency) return false;
    if (state.status && message.status !== state.status) return false;
    if (state.needsReview && !message.needs_review) return false;
    if (needle && ![message.message, message.sender, message.topic, message.team].join(" ").toLowerCase().includes(needle)) return false;
    return true;
  });
}

function renderTeamNav() {
  const counts = Object.fromEntries(TEAMS.map((team) => [team, state.messages.filter((message) => message.team === team).length]));
  $("team-nav").innerHTML = TEAMS.map((team) => `
    <button class="nav-item team-item ${state.view === team ? "active" : ""}" data-view="${escapeHtml(team)}">
      <span class="team-dot team-${team.toLowerCase().replace(/[^a-z]+/g, "-")}"></span>
      <span class="team-name">${escapeHtml(team)}</span><span class="nav-count">${counts[team]}</span>
    </button>`).join("");
}

function renderMetrics() {
  $("all-count").textContent = state.summary.total;
  $("urgent-count").textContent = state.summary.critical;
  $("review-count").textContent = state.summary.needs_review;
  $("group-count").textContent = state.summary.related_groups.length;
  $("metric-open").textContent = state.summary.total;
  $("metric-critical").textContent = state.summary.critical;
  $("metric-review").textContent = state.summary.needs_review;
  $("metric-groups").textContent = state.summary.related_groups.length;
}

function renderCriticalBanner() {
  const banner = $("critical-banner");
  if (!state.summary.critical || state.view === "alerts") {
    banner.hidden = true;
    return;
  }
  const stripeGroup = state.summary.related_groups.find((group) => group.related_group === "incident:stripe-checkout");
  banner.innerHTML = `
    <div class="banner-icon">!</div>
    <div class="banner-copy"><strong>${state.summary.critical} critical requests need attention</strong>
      <span>${stripeGroup ? `${stripeGroup.count} customers report a Stripe checkout issue. ` : ""}Account security requests are included below.</span></div>
    <button class="banner-action" data-view="alerts">Review urgent queue <span>→</span></button>`;
  banner.hidden = false;
}

function renderIssues() {
  const section = $("issues-section");
  const groups = state.summary.related_groups;
  section.hidden = !groups.length || state.view === "alerts" || state.view === "review" || state.view === "group";
  if (section.hidden) return;
  $("issue-grid").innerHTML = groups.map((group) => {
    const isStripe = group.related_group === "incident:stripe-checkout";
    return `<article class="issue-card ${isStripe ? "issue-critical" : ""}">
      <div class="issue-top"><span class="issue-icon">${isStripe ? "!" : "↻"}</span><span class="issue-count">${group.count} messages</span></div>
      <strong>${isStripe ? "Stripe checkout failures" : escapeHtml(group.related_group.replace(/^customer:[^:]+:/, "Repeated customer issue · ").replace(/-/g, " "))}</strong>
      <p>${escapeHtml(group.sample_message)}</p>
      <button class="text-button" data-group="${escapeHtml(group.related_group)}">View related requests <span>→</span></button>
    </article>`;
  }).join("");
}

function flagLabel(flag) {
  const labels = {
    missing_sender: "Missing sender",
    malformed_sender: "Check sender",
    invalid_date: "Check date",
    instruction_override_attempt: "Instruction attempt ignored",
    suspicious_sender: "Sender identity check",
    multiple_requests: "More than one issue",
  };
  return labels[flag] || flag.replace(/_/g, " ");
}

function requestCard(message) {
  const flags = (message.review_flags || []).map((flag) => `<span class="flag-pill">${escapeHtml(flagLabel(flag))}</span>`).join("");
  const assigneeOptions = ["", ...ASSIGNEES].map((name) => `<option value="${escapeHtml(name)}" ${message.assignee === name ? "selected" : ""}>${name ? escapeHtml(name) : "Unassigned"}</option>`).join("");
  const statuses = ["Nouveau", "En cours", "En attente", "Résolu"].map((status) => `<option ${message.status === status ? "selected" : ""}>${status}</option>`).join("");
  return `<article class="request-card" data-id="${message.id}">
    <div class="request-card-top">
      <div class="request-identity"><span class="priority-dot priority-${escapeHtml(message.urgency.toLowerCase())}"></span><span class="request-id">#${String(message.id).padStart(3, "0")}</span><span class="priority-label priority-text-${escapeHtml(message.urgency.toLowerCase())}">${escapeHtml(message.urgency)}</span>
        ${message.is_spam ? '<span class="spam-pill">Spam</span>' : ""}</div>
      <span class="request-date">${escapeHtml(formatDate(message.received_at))} · ${escapeHtml(message.source)}</span>
    </div>
    <div class="request-main">
      <div class="request-person"><span class="avatar">${escapeHtml((message.sender || "?").trim().charAt(0).toUpperCase())}</span><div><strong>${escapeHtml(message.sender)}</strong><small>${escapeHtml(message.language)} · ${escapeHtml(message.topic)}</small></div></div>
      <p class="request-message">${escapeHtml(message.message)}</p>
      <div class="request-tags"><span class="team-pill">${escapeHtml(message.team)}</span>${message.related_group ? `<button class="related-link" data-group="${escapeHtml(message.related_group)}">↗ related issue</button>` : ""}${flags}</div>
      <details class="reason-details"><summary>Why this was routed here</summary><p>${escapeHtml(message.rationale)}</p>${message.sender_warning ? `<p class="warning-copy">${escapeHtml(message.sender_warning)}</p>` : ""}</details>
    </div>
    <div class="request-controls">
      <label><span>Assignee</span><select data-field="assignee" data-id="${message.id}" aria-label="Assign request ${message.id}">${assigneeOptions}</select></label>
      <label><span>Status</span><select data-field="status" data-id="${message.id}" aria-label="Update status for request ${message.id}">${statuses}</select></label>
    </div>
  </article>`;
}

function renderRequests() {
  const title = titleForView();
  $("page-title").textContent = title;
  $("crumb-title").textContent = title;
  $("list-title").textContent = state.view === "groups" ? "All grouped messages" : "Inbox";
  $("list-subtitle").textContent = state.view === "alerts"
    ? "Critical issues, account risks, and incidents that need a fast response."
    : state.view === "review"
      ? "Check messages with incomplete details or unusual content."
      : "Review, assign, and update requests.";
  const messages = visibleMessages();
  $("result-count").textContent = `${messages.length} request${messages.length === 1 ? "" : "s"}`;
  $("request-list").innerHTML = messages.map(requestCard).join("");
  $("empty-state").hidden = messages.length > 0;
  if (!state.messages.length) {
    $("empty-state").innerHTML = `<span class="empty-mark">＋</span><h3>Start with the sample backlog</h3><p>Import the provided CSV to fill the team queues and see the triage rules in action.</p><label class="button button-primary empty-import" for="csv-file">Import requests-backlog.csv</label>`;
  } else {
    $("empty-state").innerHTML = `<span class="empty-mark">✓</span><h3>All caught up</h3><p>No requests match these filters. Try another team or clear your search.</p>`;
  }
}

function render() {
  renderTeamNav();
  renderMetrics();
  renderCriticalBanner();
  renderIssues();
  renderRequests();
  document.querySelectorAll("[data-view]").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === state.view);
  });
}

async function refresh() {
  try {
    const [summaryResponse, messagesResponse] = await Promise.all([
      fetch("/api/summary", { cache: "no-store" }),
      fetch("/api/messages", { cache: "no-store" }),
    ]);
    if (!summaryResponse.ok || !messagesResponse.ok) throw new Error("Could not load requests");
    state.summary = await summaryResponse.json();
    state.messages = (await messagesResponse.json()).messages;
    $("loading-state").hidden = true;
    render();
  } catch (error) {
    $("loading-state").textContent = "Could not connect to the local app. Refresh the page and try again.";
    $("loading-state").classList.add("load-error");
    showToast(error.message, true);
  }
}

let toastTimer;
function showToast(message, isError = false) {
  const toast = $("toast");
  toast.textContent = message;
  toast.classList.toggle("toast-error", isError);
  toast.classList.add("visible");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("visible"), 3400);
}

async function updateRequest(id, field, value) {
  try {
    const response = await fetch(`/api/messages/${encodeURIComponent(id)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ [field]: value }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Could not save this change");
    showToast(field === "assignee" ? "Assignment saved" : "Status updated");
    await refresh();
  } catch (error) {
    showToast(error.message, true);
    await refresh();
  }
}

async function importCsv(file) {
  const button = document.querySelector(".import-button span");
  if (button) button.textContent = "Importing…";
  try {
    const response = await fetch("/api/intake", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ csv: await file.text() }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Import failed");
    state.view = "all";
    state.group = "";
    await refresh();
    showToast(`${result.count} requests imported · ${result.alerts} critical alerts`);
  } catch (error) {
    showToast(error.message + (error.message.includes("token") ? " · Import through n8n instead." : ""), true);
  } finally {
    if (button) button.textContent = "Import CSV";
    $("csv-file").value = "";
  }
}

document.addEventListener("click", (event) => {
  const viewButton = event.target.closest("[data-view]");
  if (viewButton) {
    state.view = viewButton.dataset.view;
    state.group = "";
    render();
    return;
  }
  const groupButton = event.target.closest("[data-group]");
  if (groupButton) {
    state.group = groupButton.dataset.group;
    state.view = "group";
    render();
  }
});

document.addEventListener("change", (event) => {
  const target = event.target;
  if (target.id === "csv-file" && target.files && target.files[0]) {
    importCsv(target.files[0]);
  } else if (target.dataset.field && target.dataset.id) {
    updateRequest(target.dataset.id, target.dataset.field, target.value);
  } else if (target.id === "priority-filter") {
    state.urgency = target.value;
    renderRequests();
  } else if (target.id === "status-filter") {
    state.status = target.value;
    renderRequests();
  } else if (target.id === "review-filter") {
    state.needsReview = target.checked;
    renderRequests();
  }
});

document.addEventListener("input", (event) => {
  if (event.target.id === "search-input") {
    state.search = event.target.value;
    renderRequests();
  }
});

refresh();
