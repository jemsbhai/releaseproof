"use strict";

(() => {
  const $ = (id) => document.getElementById(id);
  const SESSION_KEY = "releaseproof.session.v1";
  const sourceLabels = { fixture: "Synthetic fixture", live: "Live · Nebius", live_probe: "Live probes · Nebius", replay: "Recorded replay", fault_injection: "Injected fault", controlled_fault_injection: "Injected fault", "controlled_fixture_A/A": "Fixture A/A", system: "System", not_run: "Not run" };
  const actionLabels = { qualify: "Running qualification", mutate: "Updating the contract", promote: "Checking and approving this candidate", execute: "Processing a demo issue", canary: "Collecting canary observations", mitigate: "Applying mitigation", configure_budget: "Updating the budget policy", reset: "Resetting the session" };
  let state = null;
  let catalog = { models: [] };
  let health = {};
  let selectedMode = "fixture";
  let selectedModel = null;
  let activePane = "overview";
  let pollTimer = null;
  let toastTimer = null;
  let pendingAction = null;
  let posting = false;
  let connecting = false;
  let comparisonA = null;
  let comparisonB = null;
  let comparisonSignature = "";

  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
  const titleCase = (value) => String(value || "unknown").replace(/[_-]/g, " ").replace(/^\w/, (char) => char.toUpperCase());
  const number = (value) => Number.isFinite(Number(value)) ? Number(value) : 0;
  const integer = (value) => Number.isFinite(Number(value)) ? Number(value).toLocaleString("en-US") : "—";
  const money = (value, precision = 4) => value == null ? "—" : new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: precision }).format(number(value));
  const shortHash = (value, count = 16) => value ? String(value).slice(0, count) + (String(value).length > count ? "…" : "") : "Not yet available";
  const pretty = (value) => typeof value === "string" ? value : JSON.stringify(value ?? null, null, 2);
  const descriptor = (value) => typeof value === "object" && value !== null ? value.message || value.detail || value.reason || value.label || value.name || pretty(value) : String(value ?? "");
  const asList = (value) => Array.isArray(value) ? value : value ? [value] : [];
  const bytes = (value) => number(value) < 1024 ? `${integer(value)} B` : number(value) < 1048576 ? `${(number(value) / 1024).toFixed(1)} KB` : `${(number(value) / 1048576).toFixed(1)} MB`;
  const duration = (value) => value == null ? "—" : number(value) < 1000 ? `${Math.round(number(value))} ms` : `${(number(value) / 1000).toFixed(2)} s`;
  const sourceBadge = (source) => `<span class="badge source ${source === "live" || source === "live_probe" ? "good" : String(source).includes("fault_injection") ? "warn" : "neutral"}">${esc(sourceLabels[source] || titleCase(source))}</span>`;
  const emptyState = (title, description, action = "") => `<div class="empty-state"><div class="empty-art" aria-hidden="true">⌘</div><h3>${esc(title)}</h3><p>${esc(description)}</p>${action}</div>`;
  const time = (value) => { if (!value) return ""; const date = new Date(value); return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }); };
  const statusClass = (value) => /^(pass|passed|qualified|approved|ready|active|stable|valid|allow|allowed|success|ok|complete|completed)$/i.test(value || "") ? "good" : /drift|blocked|invalid|failed|error|denied|hold|held|stale/i.test(value || "") ? "bad" : /warn|review|changed|pending/i.test(value || "") ? "warn" : "neutral";
  const setText = (id, value) => { const node = $(id); if (node) node.textContent = value; };
  const setBadge = (id, label, status) => { const node = $(id); if (node) { node.textContent = label; node.className = `badge ${statusClass(status)}`; } };
  const busy = () => posting || Boolean(state?.busy);

  function readSession() {
    try { return localStorage.getItem(SESSION_KEY); } catch { return null; }
  }
  function saveSession(sessionId) {
    try { localStorage.setItem(SESSION_KEY, sessionId); } catch { toast("Browser storage is unavailable. Keep this tab open to retain the session."); }
  }
  function forgetSession() {
    try { localStorage.removeItem(SESSION_KEY); } catch { /* A private session can still run in memory. */ }
  }
  async function request(path, options = {}) {
    const response = await fetch(path, { headers: { "Content-Type": "application/json", ...(options.headers || {}) }, ...options });
    let result;
    try { result = await response.json(); } catch { throw new Error(`The server returned an unreadable response (${response.status}).`); }
    if (!response.ok) {
      const error = new Error(descriptor(result.detail || result.error || result.message || `Request failed (${response.status})`));
      error.status = response.status;
      throw error;
    }
    return result;
  }

  function toast(message, error = false) {
    clearTimeout(toastTimer);
    $("toast").textContent = message;
    $("toast").className = `toast${error ? " error" : ""}`;
    toastTimer = setTimeout(() => $("toast").classList.add("hidden"), error ? 8000 : 4500);
  }

  function showPane(pane, updateHash = true) {
    if (!["overview", "qualification", "board", "evidence"].includes(pane)) pane = "overview";
    activePane = pane;
    document.querySelectorAll(".pane").forEach((node) => node.classList.toggle("hidden", node.id !== `pane-${pane}`));
    document.querySelectorAll(".nav-item").forEach((node) => {
      const current = node.dataset.pane === pane;
      node.classList.toggle("active", current);
      if (current) node.setAttribute("aria-current", "page"); else node.removeAttribute("aria-current");
    });
    setText("breadcrumb-current", { overview: "Overview", qualification: "Qualification", board: "Issue board", evidence: "Evidence & activity" }[pane]);
    if (updateHash && window.location.hash !== `#${pane}`) history.replaceState(null, "", `#${pane}`);
  }

  function renderMode() {
    const live = selectedMode === "live";
    setText("mode-label", live ? "Live Nebius mode" : "Synthetic fixture mode");
    setText("mode-explanation", live ? "NVIDIA models · actual provider calls · estimated cost" : "Local examples · simulated model calls and cost");
    document.querySelectorAll("[data-mode]").forEach((node) => {
      const selected = node.dataset.mode === selectedMode;
      node.classList.toggle("selected", selected);
      node.setAttribute("aria-pressed", String(selected));
    });
    $("live-mode-button").disabled = !health.live_available || busy();
    $("live-mode-button").title = health.live_available ? "Use the server’s configured Nebius NVIDIA model connection" : "Live calls need a Nebius API key and an enabled funded budget on the server";
    renderCanaryControls();
  }

  function liveProbeReady() {
    const qualification = state?.qualification;
    if (!health.live_available || selectedMode !== "live" || qualification?.mode !== "live" || !qualificationPassed()) return false;
    if (typeof qualification.canary_eligible === "boolean") return qualification.canary_eligible;
    const counts = new Map();
    asList(qualification.cases).filter((item) => item.passed && item.source === "live").forEach((item) => counts.set(item.id, (counts.get(item.id) || 0) + 1));
    return counts.size >= 4 && [...counts.values()].every((count) => count >= 2);
  }

  function renderCanaryControls() {
    const ready = liveProbeReady();
    $("live-canary-option").disabled = !ready;
    $("live-canary-option").textContent = ready ? "Live Nebius · fresh behavioral probes" : "Live Nebius · qualify 2× first";
    if (selectedMode !== "live" && $("canary-scenario").value === "live_probe") $("canary-scenario").value = "stable";
    setText("canary-readiness", ready ? "Live probes make fresh Nebius calls using the recovery allowance and compare against recorded baseline samples. A small panel can miss changes." : !health.live_available ? "Live probes become available after Nebius is connected and a live suite passes with 2 or 3 repetitions. Fixture experiments make no provider calls." : "Choose Live Nebius mode and pass a current qualification with 2 or 3 repetitions before running live probes. These calls use the recovery allowance.");
    document.querySelectorAll('[data-action="canary"]').forEach((node) => {
      node.disabled = !state || busy() || ($("canary-scenario").value === "live_probe" && !ready);
      node.title = $("canary-scenario").value === "live_probe" ? "Make fresh live Nebius calls under the recovery budget and compare repeated behaviors" : "Run a controlled local fixture experiment; no provider requests";
    });
  }

  function renderModels() {
    const models = asList(catalog.models);
    if (!selectedModel) selectedModel = state?.candidate?.model_id || models[0]?.id;
    const options = models.length ? models : state?.candidate ? [{ id: state.candidate.model_id, label: state.candidate.label }] : [];
    $("model-select").innerHTML = options.map((model) => `<option value="${esc(model.id)}">${esc(model.label || model.id)}</option>`).join("") || '<option value="">No models available</option>';
    if (options.some((model) => model.id === selectedModel)) $("model-select").value = selectedModel;
  }

  function qualificationPassed() {
    const qualification = state?.qualification;
    if (qualification?.fingerprint && state?.candidate?.fingerprint && qualification.fingerprint !== state.candidate.fingerprint) return false;
    return Boolean(qualification && (qualification.status === "passed" || qualification.status === "qualified" || (number(qualification.total) > 0 && number(qualification.passed) === number(qualification.total) && !/stale|fail|invalid|block/i.test(qualification.status || ""))));
  }

  function approvalEligible() {
    if (!qualificationPassed()) return false;
    if (typeof state?.governance?.approval_eligible === "boolean") return state.governance.approval_eligible;
    return state?.governance?.status === "ready_for_approval";
  }

  function renderDecision() {
    const candidate = state.candidate || {};
    const active = state.active;
    const qualification = state.qualification;
    const approved = Boolean(state.governance?.approval_valid);
    const held = /hold|held|block|drift/.test(state.status || "") || /hold|held/.test(state.drift?.mitigation || "");
    const stale = Boolean(qualification && (qualification.status === "stale" || (qualification.fingerprint && candidate.fingerprint && qualification.fingerprint !== candidate.fingerprint)));
    setBadge("release-badge", titleCase(state.status), state.status);
    let title = "Good decisions start\nwith evidence.";
    let description = "Run the qualification suite to see whether this candidate is ready for the demo issue board.";
    if (held) {
      title = "A boundary is doing\nits job.";
      description = "Review the recorded signal and governance checks. New actions must satisfy the current policy before they can proceed.";
    } else if (approved) {
      title = "Evidence checked.\nRelease approved.";
      description = "This approval is bound to the current contract. Every demo-board action will be revalidated before execution.";
    } else if (stale || /stale|changed/.test(state.status || "")) {
      title = "The contract changed.\nRebuild the proof.";
      description = "Previous evidence cannot authorize a different contract. Requalify this candidate before approving new board actions.";
    } else if (approvalEligible()) {
      title = "The suite passed.\nThe decision is yours.";
      description = "Inspect the cases and current checks, then explicitly approve this candidate for the bounded demo workflow.";
    } else if (qualificationPassed()) {
      title = "A useful first check.\nComplete the evidence.";
      description = "Passing a smoke test does not qualify a release. Run the full suite, including security and adversarial cases, then inspect the current governance checks.";
    } else if (qualification) {
      title = "A result worth\nlooking into.";
      description = "Inspect the failed cases and recorded errors. A failed qualification cannot authorize a release.";
    }
    $("decision-title").innerHTML = esc(title).replace(/\n/g, "<br>");
    setText("decision-description", description);
    setText("active-model", active?.label || active?.model_id || "No approved release");
    setText("active-detail", active ? `${active.mode || state.mode} · ${shortHash(active.fingerprint, 18)}` : "Board actions are held");
    setText("candidate-model", candidate.label || candidate.model_id || "No candidate configured");
    setText("candidate-detail", `prompt ${candidate.prompt_version ?? "—"} · tools ${candidate.tool_version ?? "—"} · policy ${candidate.policy_version ?? "—"}`);
    setText("main-qualify-button", qualification ? "↻  Re-run qualification" : "▶  Run qualification");
    $("step-qualify").classList.toggle("completed", qualificationPassed() && !stale);
    $("step-approve").classList.toggle("completed", approved);
    $("step-run").classList.toggle("completed", asList(state.board).some((issue) => issue.status !== "open"));
    const model = asList(catalog.models).find((item) => item.id === selectedModel);
    $("model-select").title = model ? `${money(model.input_per_million, 2)} input / ${money(model.output_per_million, 2)} output per million tokens. Live cost is an estimate.` : "Select the model for the next qualification run";
    setText("model-pricing", model ? `${money(model.input_per_million, 2)} in / ${money(model.output_per_million, 2)} out per 1M tokens · applies on qualification` : "Selection applies on qualification");
  }

  function renderBudget() {
    const budget = state.budget || {};
    const limit = Math.max(0, number(budget.limit_usd));
    const spent = Math.max(0, number(budget.spent_usd));
    const reserved = Math.max(0, number(budget.reserved_usd));
    const recovery = budget.protected_usd ?? limit * number(budget.reserve_percent) / 100;
    const progress = (value) => `${Math.max(0, Math.min(100, limit ? value / limit * 100 : 0))}%`;
    setText("budget-spent", money(spent));
    setText("budget-limit", money(limit, 2));
    setText("budget-caption", state.mode === "live" ? "Estimated from observed provider tokens" : "Simulated fixture spend · no provider billing");
    $("budget-used").style.width = progress(spent);
    $("budget-reserved").style.width = progress(reserved);
    $("budget-recovery").style.width = `${number(budget.reserve_percent)}%`;
    $("budget-track").setAttribute("aria-label", `${money(spent)} spent, ${money(reserved)} currently reserved, ${money(recovery)} protected for recovery, session limit ${money(limit)}`);
    setText("budget-remaining", money(Math.max(0, number(budget.remaining_usd) - recovery)));
    setText("budget-reserve-value", `${money(recovery)} · ${number(budget.reserve_percent)}%`);
    setText("budget-accounting", `${money(budget.live_spent_usd || 0)} / ${money(budget.simulated_spent_usd || 0)}`);
    setText("budget-blocked", integer(budget.blocked_calls ?? 0));
    if (!$("budget-form").contains(document.activeElement)) {
      $("budget-limit-input").value = limit;
      $("reserve-input").value = number(budget.reserve_percent) || 20;
      $("strategy-input").value = budget.strategy || "balanced";
      setText("reserve-percent-label", `${$("reserve-input").value}%`);
    }
  }

  function renderGovernance() {
    const governance = state.governance || {};
    setBadge("governance-badge", governance.approval_valid ? "Approval valid" : titleCase(governance.status || "Awaiting evidence"), governance.approval_valid ? "valid" : governance.status);
    let checks = asList(governance.checks);
    if (!checks.length) checks = asList(governance.reasons).map((reason) => ({ label: descriptor(reason), passed: false }));
    $("governance-checks").innerHTML = checks.length ? checks.map((check) => {
      if (typeof check === "string") return `<div class="check-row"><span class="check-symbol">·</span><span>${esc(check)}</span></div>`;
      const passed = check.passed ?? check.ok ?? check.allowed ?? /pass|allow|valid|ok/.test(check.status || "");
      const label = check.label || check.name || check.check || check.reason || "Policy check";
      const detail = check.detail || check.message;
      return `<div class="check-row${passed ? "" : " fail"}"><span class="check-symbol" aria-label="${passed ? "Passed" : "Needs attention"}">${passed ? "✓" : "○"}</span><span>${esc(label)}${detail && detail !== label ? `<small class="check-sub">${esc(descriptor(detail))}</small>` : ""}</span></div>`;
    }).join("") : '<div class="empty-inline">Qualification will populate the release checks.</div>';
    const fingerprint = state.candidate?.fingerprint || state.evidence?.fingerprint;
    setText("contract-fingerprint", shortHash(fingerprint, 24));
    $("contract-fingerprint").title = fingerprint || "";
    $("copy-fingerprint").disabled = !fingerprint;
    $("promote-button").textContent = governance.approval_valid ? "Approval bound to current contract  ✓" : "Approve this candidate  →";
  }

  function renderDrift() {
    const drift = state.drift || {};
    setBadge("drift-badge", drift.status === "unknown" ? "Not enough evidence" : drift.status === "stable" ? "No change detected" : titleCase(drift.status), drift.status);
    setText("drift-observations", drift.observations ? integer(drift.observations) : "—");
    setText("drift-p-value", drift.p_value == null ? "—" : number(drift.p_value) < .0001 ? number(drift.p_value).toExponential(2) : number(drift.p_value).toFixed(4));
    setText("drift-mitigation", drift.mitigation === "fallback_requires_requalification" ? "Requalify fallback" : titleCase(drift.mitigation || "none"));
    const details = asList(drift.details).map(descriptor).filter(Boolean);
    $("drift-details").innerHTML = `${drift.mode && drift.mode !== "not_run" ? sourceBadge(drift.mode) + " " : ""}${esc(details.join(" · ") || "No canary has run in this session.")}${drift.verdict ? `<details class="statistical-evidence"><summary>Inspect recorded statistical evidence <span>${drift.recomputed ? "recomputed ✓" : "not verified"}</span></summary><div class="code-block"><span class="field-label">EPICORMIC VERDICT · RECORDED EXPERIMENT</span><pre>${esc(pretty(drift.verdict))}</pre></div></details>` : ""}`;
    $("drift-details").classList.toggle("has-signal", /drift|warning/.test(drift.status || ""));
  }

  function renderQualification() {
    const qualification = state.qualification;
    const cases = asList(qualification?.cases);
    const tokenValue = qualification?.tokens;
    const tokenCount = tokenValue && typeof tokenValue === "object" ? number(tokenValue.total_tokens || tokenValue.total || number(tokenValue.input_tokens) + number(tokenValue.output_tokens)) : tokenValue;
    let accuracy = qualification?.accuracy;
    if (accuracy != null && number(accuracy) <= 1) accuracy = number(accuracy) * 100;
    const metrics = [
      ["CASES PASSED", qualification ? `${integer(qualification.passed)} / ${integer(qualification.total)}` : "—", qualification ? `${number(accuracy).toFixed(0)}% on this suite` : "Run the suite to measure"],
      ["RUN LATENCY", duration(qualification?.latency_ms), qualification?.mode === "live" ? "Observed wall-clock time" : qualification ? "Local fixture harness time" : "No measurements yet"],
      ["TOKENS", qualification ? integer(tokenCount) : "—", qualification?.mode === "live" ? "Provider-reported usage" : qualification ? "Simulated fixture usage" : "No qualification calls"],
      [qualification?.mode === "live" ? "ESTIMATED COST" : "SIMULATED COST", money(qualification?.cost_usd, 6), qualification?.mode === "live" ? "Observed tokens × model prices" : "Fixture cost is not a bill"]
    ];
    $("qualification-metrics").innerHTML = metrics.map(([label, value, detail]) => `<div class="metric-card"><span class="field-label">${esc(label)}</span><strong>${esc(value)}</strong><small>${esc(detail)}</small></div>`).join("");
    renderComparison();
    if (!qualification) {
      setBadge("qualification-source", "No run", "unknown");
      $("qualification-cases").innerHTML = emptyState("Nothing to approve yet.", "Choose a suite and run qualification. Every case will show its expected decision, observed output, and source.", '<button type="button" class="button primary" data-action="qualify">Run qualification →</button>');
      return;
    }
    setBadge("qualification-source", `${sourceLabels[qualification.mode] || titleCase(qualification.mode)} · ${titleCase(qualification.status)}`, qualification.status);
    $("qualification-cases").innerHTML = cases.length ? `<div class="case-list">${cases.map((item, index) => `<details class="case-item" data-case="${esc(item.id || index)}"><summary><span class="case-status${item.passed ? "" : " fail"}" aria-label="${item.passed ? "Passed" : "Failed"}">${item.passed ? "✓" : "×"}</span><span class="case-title">${esc(item.title || item.id || `Case ${index + 1}`)}<small>${esc(item.id || "")}</small></span><span class="case-numeric">${esc(duration(item.latency_ms))}</span><span class="case-numeric">${esc(money(item.cost_usd, 6))}</span><span class="case-expand" aria-hidden="true">＋</span></summary><div class="case-body"><div class="case-meta">${sourceBadge(item.source || qualification.mode)}<span>${integer(item.input_tokens)} input · ${integer(item.output_tokens)} output tokens</span><span>${integer(asList(item.tool_calls).length)} tool calls</span></div>${item.error ? `<div class="case-error">${esc(descriptor(item.error))}</div>` : ""}<div class="case-comparison"><div class="code-block"><span class="field-label">EXPECTED DECISION</span><pre>${esc(pretty(item.expected))}</pre></div><div class="code-block"><span class="field-label">OBSERVED OUTPUT</span><pre>${esc(pretty(item.actual))}</pre></div></div>${asList(item.tool_calls).length ? `<div class="code-block"><span class="field-label">TOOL TRACE</span><pre>${esc(pretty(item.tool_calls))}</pre></div>` : ""}</div></details>`).join("")}</div>` : emptyState("No case outputs were recorded.", "Inspect the activity log for the provider or budget error before rerunning this qualification.");
  }

  function renderComparison() {
    let history = asList(state.qualification_history);
    if (!history.length && state.qualification) history = [state.qualification];
    setText("comparison-count", `${history.length} saved run${history.length === 1 ? "" : "s"}`);
    if (history.length < 2) {
      $("qualification-comparison").innerHTML = `<div class="comparison-empty"><div><h3>${history.length ? "One run is a start. Compare the next." : "Evidence that stays comparable."}</h3><p>Qualify two model or prompt configurations to compare their recorded checks, time, tokens, and cost. Each result keeps its source and exact contract.</p></div><button type="button" class="button secondary small" data-pane="overview">${history.length ? "Choose another candidate" : "Choose a candidate"} →</button></div>`;
      return;
    }
    const signature = history.map((run) => run.id).join("|");
    if (signature !== comparisonSignature) {
      comparisonSignature = signature;
      comparisonB = history.at(-1).id;
      comparisonA = history.slice(0, -1).reverse().find((run) => run.fingerprint !== history.at(-1).fingerprint)?.id || history.at(-2).id;
    }
    const left = history.find((run) => run.id === comparisonA) || history.at(-2);
    const right = history.find((run) => run.id === comparisonB) || history.at(-1);
    const modelName = (run) => run.model_label || asList(catalog.models).find((model) => model.id === run.model_id)?.label || run.model_id || "Model not recorded";
    const options = (selection) => history.map((run, index) => `<option value="${esc(run.id)}"${run.id === selection ? " selected" : ""}>Run ${index + 1} · ${esc(modelName(run))} · ${esc(run.mode)} · ${esc(run.status)}</option>`).join("");
    const versions = (run) => run.config_versions ? `prompt ${run.config_versions.prompt ?? "—"} · tools ${run.config_versions.tools ?? "—"} · policy ${run.config_versions.policy ?? "—"}` : "Versions not recorded";
    const cells = (label, leftValue, rightValue, code = false) => `<div class="comparison-row"><span class="comparison-label">${esc(label)}</span><span${code ? ' class="comparison-mono"' : ""}>${esc(leftValue)}</span><span${code ? ' class="comparison-mono"' : ""}>${esc(rightValue)}</span></div>`;
    const warning = left.mode !== right.mode ? "These runs use different sources. A fixture is not live model-quality evidence." : number(left.total) !== number(right.total) ? "These runs contain different case counts. Inspect their suites before drawing a quality or cost conclusion." : left.mode === "fixture" ? "Both runs use deterministic synthetic fixtures. This comparison demonstrates the release workflow, not relative NVIDIA model quality." : "Observed results on a small synthetic corpus. Cost is estimated; latency can vary between requests. No broad model ranking is implied.";
    $("qualification-comparison").innerHTML = `<div class="comparison-selectors"><label>REFERENCE RUN<select id="comparison-a" aria-label="Reference qualification">${options(left.id)}</select></label><label>COMPARISON RUN<select id="comparison-b" aria-label="Comparison qualification">${options(right.id)}</select></label></div><div class="comparison-table" role="group" aria-label="Recorded qualification comparison"><div class="comparison-row comparison-header"><span>RECORDED RESULT</span><strong>${esc(modelName(left))}</strong><strong>${esc(modelName(right))}</strong></div><div class="comparison-row"><span class="comparison-label">Source / outcome</span><span>${sourceBadge(left.mode)} <span class="comparison-outcome ${statusClass(left.status)}">${esc(titleCase(left.status))}</span></span><span>${sourceBadge(right.mode)} <span class="comparison-outcome ${statusClass(right.status)}">${esc(titleCase(right.status))}</span></span></div>${cells("Configuration", versions(left), versions(right))}${cells("Exact fingerprint", left.fingerprint || "—", right.fingerprint || "—", true)}${cells("Passed checks", `${integer(left.passed)} / ${integer(left.total)}`, `${integer(right.passed)} / ${integer(right.total)}`)}${cells("Recorded latency", duration(left.latency_ms), duration(right.latency_ms))}${cells("Tokens", integer(left.tokens), integer(right.tokens))}${cells("Cost (source above)", money(left.cost_usd, 6), money(right.cost_usd, 6))}</div><p class="comparison-note">${esc(warning)}</p>`;
  }

  function renderBoard() {
    const issues = asList(state.board);
    const approved = Boolean(state.governance?.approval_valid);
    const open = issues.filter((issue) => issue.status === "open");
    setText("board-notice", approved ? `Current approval is valid. ${open.length} open demo issue${open.length === 1 ? "" : "s"} remain. The server revalidates before each action.` : state.active ? "The previous release no longer has a valid approval. Try a governed action to inspect the server’s current decision; a closed gate will block it and record the refusal." : "Board actions need a qualified, current approval and an open governance gate. Inspect Overview to resolve any hold.");
    setText("execute-next-button", approved ? "Process next issue  →" : "Try governed action  →");
    $("issue-board").innerHTML = issues.length ? issues.map((issue) => `<article class="issue-card"><div class="issue-top"><span class="issue-id">${esc(issue.id)}</span><span class="badge ${issue.status === "open" ? "neutral" : "good"}">${esc(titleCase(issue.status))}</span></div><h3>${esc(issue.title)}</h3><p class="issue-body">${esc(issue.body)}</p><div class="issue-labels">${asList(issue.labels).map((label) => `<span class="issue-label${label === "security" ? " security" : ""}">${esc(descriptor(label))}</span>`).join("")}${issue.needs_review ? '<span class="issue-label security">Human review required</span>' : ""}</div>${issue.draft ? `<div class="issue-draft"><span class="field-label">DRAFT ONLY · NOT SENT</span>${esc(typeof issue.draft === "string" ? issue.draft : descriptor(issue.draft))}</div>` : ""}<div class="issue-bottom"><span class="issue-route">Assigned route<strong>${esc(issue.route || "Awaiting triage")}</strong></span><button class="button secondary small" type="button" data-execute="${esc(issue.id)}" ${busy() || !approved || issue.status !== "open" ? "disabled" : ""} title="${approved ? "Process this synthetic issue through the current release" : "Approve a qualified candidate first"}">${issue.status === "open" ? "Process issue →" : "Processed ✓"}</button></div></article>`).join("") : emptyState("The board is empty.", "This session has no synthetic issues available.");
  }

  function renderEvidence() {
    const evidence = state.evidence || {};
    const versions = asList(evidence.versions);
    setText("revision-badge", `Revision ${state.revision ?? "—"}`);
    $("evidence-summary").innerHTML = `<div class="evidence-stat"><span>Current fingerprint</span><code>${esc(shortHash(evidence.fingerprint, 32))}</code></div><div class="evidence-stat"><span>Snapshot storage</span><code>${esc(bytes(evidence.snapshot_bytes))}</code></div><div class="evidence-stat"><span>Packet seal</span><code>${esc(evidence.seal ? shortHash(typeof evidence.seal === "object" ? evidence.seal.sha256 || pretty(evidence.seal) : evidence.seal, 32) : "Available after export")}</code></div><div class="evidence-stat"><span>Changed dependencies</span><code>${esc(asList(evidence.changed).map(descriptor).join(", ") || "None recorded")}</code></div>`;
    $("evidence-versions").innerHTML = versions.length ? `<div class="version-list">${versions.slice().reverse().map((version, index) => `<div class="version-item"><strong>${esc(version.label || version.title || version.reason || `Evidence version ${version.revision || version.version || versions.length - index}`)}</strong><small>${esc(shortHash(version.fingerprint || version.hash || version.id, 28))}${version.time || version.created_at ? ` · ${esc(time(version.time || version.created_at))}` : ""}</small>${version.changed ? `<small>${esc(asList(version.changed).map(descriptor).join(", "))}</small>` : ""}</div>`).join("")}</div>` : '<div class="empty-inline">New evidence versions will appear as the contract and its qualification change.</div>';
    const metrics = state.metrics || {};
    $("execution-metrics").innerHTML = [["live_calls", "Live provider calls"], ["fixture_calls", "Simulated fixture calls"], ["replayed_calls", "Recorded replays"], ["blocked_calls", "Blocked calls"]].map(([key, label]) => `<div><strong>${integer(metrics[key] || 0)}</strong><span>${esc(label)}</span></div>`).join("");
    const decisions = asList(state.budget?.decisions);
    $("budget-decisions").innerHTML = decisions.length ? decisions.slice(-8).reverse().map((decision) => `<details class="budget-event"><summary><span>${esc(decision.title || decision.action || decision.reason || decision.decision || descriptor(decision))}</span><code>${decision.charged_usd != null || decision.cost_usd != null || decision.reserve_usd != null ? esc(money(decision.charged_usd ?? decision.cost_usd ?? decision.reserve_usd, 6)) : esc(decision.status || "")}</code></summary><div class="code-block"><span class="field-label">RESERVATION & RECONCILIATION</span><pre>${esc(pretty(decision))}</pre></div></details>`).join("") : '<div class="empty-inline">No budget decisions yet. Reservations and reconciliations will be recorded here.</div>';
    const audit = asList(evidence.audit);
    setText("audit-count", `${integer(evidence.audit_nodes ?? audit.length)} recorded nodes`);
    $("audit-trace").innerHTML = audit.length ? `<div class="audit-list">${audit.slice(-30).reverse().map((node) => `<details class="audit-node"><summary><span class="audit-kind">${esc(titleCase(node.kind))}</span><span class="audit-name">${esc(node.tool || node.reason || shortHash(node.id, 18))}</span>${sourceBadge(node.source || "system")}<span class="case-expand" aria-hidden="true">＋</span></summary><div class="code-block"><span class="field-label">RECORDED NODE · ${esc(node.id)}</span><pre>${esc(pretty(node))}</pre></div></details>`).join("")}</div><p class="card-footnote">${Math.min(audit.length, 30)} recorded nodes shown. The evidence packet includes the retained audit. Hashrope fingerprints are noncryptographic; integrity checks use the SHA-256 seals.</p>` : '<div class="empty-inline">Actual model calls, tool calls, and refusals recorded by Pollard will appear here.</div>';
    const events = asList(state.events);
    setText("event-count", `${events.length} event${events.length === 1 ? "" : "s"}`);
    $("activity-log").innerHTML = events.length ? events.slice().reverse().map((event) => `<div class="event-row"><span class="event-symbol" aria-hidden="true">${/block|fail|error/i.test(event.status || event.kind || "") ? "⊘" : /approve|pass|complete/i.test(event.kind || "") ? "✓" : "↳"}</span><div><div class="event-title">${esc(event.title || titleCase(event.kind))}</div><div class="event-detail">${esc(descriptor(event.detail))}</div></div><div class="event-right">${sourceBadge(event.source || "system")}<time class="event-time" datetime="${esc(event.time || "")}">${esc(time(event.time))}</time></div></div>`).join("") : emptyState("A clean slate.", "Run a qualification to start the execution and evidence trail.");
  }

  function renderDisabled() {
    const locked = !state || busy();
    document.querySelectorAll("[data-action], [data-mutate], [data-mitigation], #budget-form button, #reset-button, #model-select, #suite-select, #repetitions-select, #canary-scenario").forEach((node) => node.disabled = locked);
    $("promote-button").disabled = locked || !approvalEligible() || Boolean(state?.governance?.approval_valid);
    $("promote-button").title = !approvalEligible() ? "Pass the full suite and resolve the current governance checks before approval" : "Explicitly approve the current server-side contract and evidence";
    $("execute-next-button").disabled = locked || !state?.active || !asList(state?.board).some((issue) => issue.status === "open");
    $("export-button").disabled = !state || busy();
    document.querySelectorAll("[data-execute]").forEach((node) => {
      const processed = asList(state?.board).find((issue) => issue.id === node.dataset.execute)?.status !== "open";
      node.disabled = locked || !state?.active || processed;
      node.textContent = processed ? "Processed ✓" : state?.governance?.approval_valid ? "Process issue →" : "Try governed action →";
      node.title = !state?.active ? "Approve a qualified candidate first" : "Attempt this demo-board action. The server will allow or deny it against the current release contract.";
    });
    document.querySelectorAll("[data-mode]").forEach((node) => node.disabled = locked || (node.dataset.mode === "live" && !health.live_available));
    renderCanaryControls();
    $("busy-banner").classList.toggle("hidden", !busy());
    setText("busy-text", `${actionLabels[pendingAction] || "Running a governed action"}…`);
  }

  function render() {
    if (!state) return;
    const openCases = [...document.querySelectorAll(".case-item[open]")].map((node) => node.dataset.case);
    renderMode();
    renderDecision();
    renderBudget();
    renderGovernance();
    renderDrift();
    renderQualification();
    renderBoard();
    renderEvidence();
    renderDisabled();
    openCases.forEach((id) => [...document.querySelectorAll(".case-item")].find((node) => node.dataset.case === id)?.setAttribute("open", ""));
    setText("nav-case-count", state.qualification ? `${state.qualification.passed}/${state.qualification.total}` : "—");
    setText("nav-board-count", asList(state.board).filter((issue) => issue.status === "open").length);
    setText("session-tag", "Private session");
  }

  async function connect() {
    if (connecting) return;
    connecting = true;
    clearTimeout(pollTimer);
    $("connection-error").classList.add("hidden");
    setText("connection-status", "Connecting to workbench");
    try {
      const resources = await Promise.allSettled([request("/api/health"), request("/api/catalog")]);
      if (resources[0].status === "rejected") throw resources[0].reason;
      health = resources[0].value;
      if (resources[1].status === "fulfilled") catalog = resources[1].value;
      const sessionId = state?.session_id || readSession();
      if (sessionId) {
        try { state = await request(`/api/sessions/${encodeURIComponent(sessionId)}`); }
        catch (error) { if (error.status !== 404) throw error; forgetSession(); state = null; }
      }
      if (!state) state = await request("/api/sessions", { method: "POST", body: "{}" });
      saveSession(state.session_id);
      selectedMode = state.mode === "live" && health.live_available ? "live" : "fixture";
      selectedModel = state.candidate?.model_id || catalog.models?.[0]?.id;
      renderModels();
      render();
      $("connection-dot").classList.add("connected");
      setText("connection-status", "Session connected · auto-saved");
      if (state.busy) schedulePoll();
      if (state.last_error) toast(descriptor(state.last_error), true);
    } catch (error) {
      $("connection-dot").classList.remove("connected");
      setText("connection-status", "Connection unavailable");
      setText("connection-error-text", `Could not open the workbench: ${error.message}`);
      $("connection-error").classList.remove("hidden");
      renderDisabled();
    } finally { connecting = false; }
  }

  function schedulePoll() {
    clearTimeout(pollTimer);
    pollTimer = setTimeout(poll, 700);
  }
  async function poll() {
    if (!state) return;
    try {
      state = await request(`/api/sessions/${encodeURIComponent(state.session_id)}`);
      if (!state.busy && ["qualify", "mitigate", "reset"].includes(pendingAction)) {
        selectedModel = state.candidate?.model_id || selectedModel;
        selectedMode = state.mode === "live" ? "live" : "fixture";
        renderModels();
      }
      render();
      if (state.busy) return schedulePoll();
      const completedAction = pendingAction;
      pendingAction = null;
      if (state.last_error) toast(descriptor(state.last_error), true);
      else if (completedAction) {
        const lastEvent = asList(state.events).at(-1);
        if (/blocked|error|failed/.test(lastEvent?.status || "")) toast(`${lastEvent.title}. ${descriptor(lastEvent.detail)}`, true);
        else toast({ qualify: "Qualification recorded. Inspect the cases before approval.", promote: "Approval decision recorded against this contract.", execute: "Board action complete. Inspect its draft and trace.", mutate: "Contract changed. Check the current approval status.", canary: "Canary observations recorded. Review the evidence.", mitigate: "Mitigation decision recorded.", configure_budget: "Budget policy updated.", reset: "Session reset. Start a fresh qualification." }[completedAction] || "Action complete.");
      }
      if (completedAction === "reset") { selectedModel = state.candidate?.model_id; selectedMode = "fixture"; renderModels(); render(); showPane("overview"); }
    } catch (error) {
      pendingAction = null;
      if (state) state.busy = false;
      renderDisabled();
      toast(`Could not refresh the result: ${error.message}. Reconnect to recover the saved state.`, true);
      setText("connection-error-text", "The action may still be running. Reconnect to read the saved result before trying it again.");
      $("connection-error").classList.remove("hidden");
    }
  }

  async function perform(action, payload = {}) {
    if (!state || busy()) return;
    posting = true;
    pendingAction = action;
    renderDisabled();
    try {
      await request(`/api/sessions/${encodeURIComponent(state.session_id)}/actions`, { method: "POST", body: JSON.stringify({ action, payload }) });
      state.busy = true;
      posting = false;
      renderDisabled();
      schedulePoll();
    } catch (error) {
      posting = false;
      pendingAction = null;
      toast(error.message, true);
      renderDisabled();
      if (error.status === 409) schedulePoll();
    }
  }

  function actionPayload(action) {
    if (action === "qualify") return { mode: selectedMode, model_id: $("model-select").value || selectedModel, suite: $("suite-select").value, repetitions: number($("repetitions-select").value) || 1 };
    if (action === "execute") return { mode: selectedMode };
    if (action === "canary") return { scenario: $("canary-scenario").value };
    return {};
  }

  document.addEventListener("click", (event) => {
    const target = event.target.closest("button, a");
    if (!target || target.disabled) return;
    if (target.dataset.pane) { event.preventDefault(); showPane(target.dataset.pane); return; }
    if (target.dataset.focus) {
      showPane("overview");
      const node = $(target.dataset.focus);
      node?.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "center" });
      node?.focus({ preventScroll: true });
      return;
    }
    if (target.dataset.mode) { selectedMode = target.dataset.mode; renderMode(); return; }
    if (target.dataset.mutate) { perform("mutate", { change: target.dataset.mutate }); return; }
    if (target.dataset.mitigation) { perform("mitigate", { strategy: target.dataset.mitigation }); return; }
    if (target.dataset.execute) { perform("execute", { issue_id: target.dataset.execute, mode: selectedMode }); return; }
    if (target.dataset.action) { perform(target.dataset.action, actionPayload(target.dataset.action)); }
  });

  $("budget-form").addEventListener("submit", (event) => {
    event.preventDefault();
    if (!event.currentTarget.reportValidity()) return;
    perform("configure_budget", { limit_usd: number($("budget-limit-input").value), reserve_percent: number($("reserve-input").value), strategy: $("strategy-input").value });
  });
  $("reserve-input").addEventListener("input", () => setText("reserve-percent-label", `${$("reserve-input").value}%`));
  $("canary-scenario").addEventListener("change", renderCanaryControls);
  $("model-select").addEventListener("change", () => { selectedModel = $("model-select").value; renderDecision(); });
  document.addEventListener("change", (event) => {
    if (event.target.id === "comparison-a") { comparisonA = event.target.value; renderComparison(); }
    if (event.target.id === "comparison-b") { comparisonB = event.target.value; renderComparison(); }
  });
  $("retry-button").addEventListener("click", connect);
  $("reset-button").addEventListener("click", () => $("reset-dialog").showModal());
  $("reset-dialog").addEventListener("close", () => { if ($("reset-dialog").returnValue === "reset") perform("reset"); });
  $("copy-fingerprint").addEventListener("click", async () => {
    const fingerprint = state?.candidate?.fingerprint || state?.evidence?.fingerprint;
    if (!fingerprint) return;
    try { await navigator.clipboard.writeText(fingerprint); toast("Contract fingerprint copied."); }
    catch { toast("Clipboard access is unavailable. The full fingerprint is included in the evidence export."); }
  });
  $("export-button").addEventListener("click", async () => {
    if (!state) return;
    try {
      const response = await fetch(`/api/sessions/${encodeURIComponent(state.session_id)}/export`);
      if (!response.ok) throw new Error(`Export failed (${response.status})`);
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `releaseproof-evidence-r${state.revision || 1}.json`;
      anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      toast("Evidence packet downloaded. Source labels and recorded failures are included.");
    } catch (error) { toast(error.message, true); }
  });
  window.addEventListener("hashchange", () => showPane(window.location.hash.slice(1), false));
  window.addEventListener("online", () => { if (!state || $("connection-error").classList.contains("hidden") === false) connect(); });
  showPane(window.location.hash.slice(1) || "overview", false);
  renderDisabled();
  connect();
})();
