/* AI Visibility dashboard: fetches /api/run/<id> and renders the report. */
(function () {
  const $ = (sel) => document.querySelector(sel);
  const state = { runs: [], runId: null, provider: "", data: null, charts: {} };
  const COLORS = ["#6b47ff", "#0ea5e9", "#f59e0b", "#10b981", "#ef4444", "#8b5cf6", "#14b8a6", "#f97316", "#64748b", "#a855f7", "#22c55e", "#e11d48"];

  const fmt = (v, suffix = "") => (v === null || v === undefined ? "–" : `${v}${suffix}`);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const when = (iso) => (iso ? new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "");

  async function getJSON(url, opts) {
    const r = await fetch(url, opts);
    if (!r.ok) throw new Error(`${r.status} ${url}`);
    return r.json();
  }

  // ---- data ---------------------------------------------------------------
  async function loadRuns() {
    state.runs = await getJSON("/api/runs");
    const sel = $("#run-select");
    sel.innerHTML = state.runs.map((r) => `<option value="${esc(r.id)}">${esc(r.brand)} · ${when(r.started_at)} · ${r.n_ok}/${r.n_answers} ok${r.status !== "done" ? " · " + r.status : ""}</option>`).join("");
    if (!state.runs.length) { $("#empty-state").classList.remove("hidden"); $("#content").classList.add("hidden"); $("#run-subtitle").textContent = "No runs stored yet"; return; }
    if (!state.runId || !state.runs.some((r) => r.id === state.runId)) state.runId = state.runs[0].id;
    sel.value = state.runId;
    await loadRun();
  }

  async function loadRun() {
    state.data = await getJSON(`/api/run/${state.runId}`);
    $("#empty-state").classList.add("hidden");
    $("#content").classList.remove("hidden");
    const ps = $("#provider-select");
    const keep = state.provider;
    ps.innerHTML = `<option value="">All engines</option>` + state.data.providers.map((p) => `<option value="${esc(p.id)}">${esc(p.label)}${p.model ? " · " + esc(p.model) : ""}</option>`).join("");
    state.provider = state.data.providers.some((p) => p.id === keep) ? keep : "";
    ps.value = state.provider;
    render();
    loadTrend().catch(console.error);
  }

  // The stats table for the current scope (all engines or one engine).
  function scope() {
    const d = state.data;
    if (state.provider && d.by_provider[state.provider]) return { table: d.by_provider[state.provider].brands, ranking: d.by_provider[state.provider].ranking };
    return { table: d.overall, ranking: d.ranking };
  }

  // ---- rendering ----------------------------------------------------------
  function render() {
    const d = state.data;
    const r = d.run;
    $("#run-subtitle").textContent = `${d.target} · run ${r.id} · ${when(r.started_at)} · ${d.totals.ok}/${d.totals.answers} answers ok · ${d.totals.eligible} used for ranking${state.provider ? " · engine: " + state.provider : ""}`;
    renderKpis();
    renderRankingChart();
    renderEngineTable();
    renderBrandTable();
    renderMatrix();
    renderSources();
    renderProviders();
  }

  function renderKpis() {
    const d = state.data, { table, ranking } = scope();
    const t = table[d.target] || {};
    const rank = ranking.indexOf(d.target) + 1;
    const leader = ranking[0];
    const lead = table[leader] || {};
    const gap = t.visibility != null && lead.visibility != null ? (t.visibility - lead.visibility).toFixed(1) : null;
    const kpis = [
      { label: "Your rank", value: rank ? `#${rank}` : "–", sub: `of ${ranking.length} tracked brands${leader && leader !== d.target ? ` · leader: ${leader}` : ""}`, target: true },
      { label: "Visibility", value: fmt(t.visibility, "%"), sub: `mentioned in ${t.mentioned ?? 0} of ${t.answers ?? 0} answers${gap !== null && leader !== d.target ? ` · ${gap} pts vs leader` : ""}` },
      { label: "Share of voice", value: fmt(t.share_of_voice, "%"), sub: "of all tracked-brand mentions" },
      { label: "Avg. position", value: fmt(t.avg_position), sub: `first-mentioned in ${fmt(t.first_rate, "%")} of answers` },
      { label: "Sentiment", value: fmt(t.sentiment), sub: t.sentiment_counts ? `${t.sentiment_counts.positive} pos · ${t.sentiment_counts.neutral} neu · ${t.sentiment_counts.negative} neg` : "not judged" },
      { label: "Citation share", value: fmt(t.citation_share, "%"), sub: `${t.own_citations ?? 0} links to your domains` },
    ];
    $("#kpis").innerHTML = kpis.map((k) => `<div class="kpi${k.target ? " target" : ""}"><div class="label">${esc(k.label)}</div><div class="value">${esc(k.value)}</div><div class="sub">${esc(k.sub)}</div></div>`).join("");
  }

  function chart(id, config) {
    if (state.charts[id]) state.charts[id].destroy();
    state.charts[id] = new Chart(document.getElementById(id), config);
  }

  function renderRankingChart() {
    const d = state.data, { table, ranking } = scope();
    $("#ranking-note").textContent = `visibility (% of ${table[ranking[0]]?.answers ?? 0} answers)`;
    chart("ranking-chart", {
      type: "bar",
      data: {
        labels: ranking,
        datasets: [
          { label: "Visibility %", data: ranking.map((b) => table[b].visibility ?? 0), backgroundColor: ranking.map((b) => (b === d.target ? "#6b47ff" : "#c7cbd8")), borderRadius: 6 },
          { label: "Share of voice %", data: ranking.map((b) => table[b].share_of_voice ?? 0), backgroundColor: ranking.map((b) => (b === d.target ? "#b39cff" : "#e3e5ec")), borderRadius: 6 },
        ],
      },
      options: { responsive: true, maintainAspectRatio: false, scales: { y: { beginAtZero: true, max: 100, ticks: { callback: (v) => v + "%" } } }, plugins: { legend: { position: "bottom" } } },
    });
  }

  function heat(v) {
    if (v === null || v === undefined) return "";
    const a = Math.min(1, v / 100) * 0.75 + 0.05;
    return `style="background: rgba(107,71,255,${a.toFixed(2)}); color:${v > 55 ? "#fff" : "#222"}"`;
  }

  function renderEngineTable() {
    const d = state.data;
    const provs = d.providers;
    const brands = d.ranking;
    let html = `<thead><tr><th>Brand</th>${provs.map((p) => `<th class="num" title="${esc(p.model || "")}">${esc(p.label)}</th>`).join("")}<th class="num">All</th></tr></thead><tbody>`;
    for (const b of brands) {
      html += `<tr class="${b === d.target ? "target" : ""}"><td>${esc(b)}${b === d.target ? ' <span class="tag you">you</span>' : ""}</td>`;
      for (const p of provs) {
        const s = d.by_provider[p.id]?.brands[b];
        html += `<td class="heat" ${heat(s?.visibility)}>${fmt(s?.visibility, "%")}</td>`;
      }
      html += `<td class="heat" ${heat(d.overall[b].visibility)}>${fmt(d.overall[b].visibility, "%")}</td></tr>`;
    }
    $("#engine-table").innerHTML = html + "</tbody>";
  }

  function renderBrandTable() {
    const d = state.data, { table, ranking } = scope();
    let html = `<thead><tr><th>#</th><th>Brand</th><th>Visibility</th><th class="num">Mentioned</th><th class="num">Share of voice</th><th class="num">Avg. position</th><th class="num">First</th><th class="num">Sentiment</th><th class="num">Citation share</th></tr></thead><tbody>`;
    ranking.forEach((b, i) => {
      const s = table[b];
      html += `<tr class="${b === d.target ? "target" : ""}"><td>${i + 1}</td><td>${esc(b)}${b === d.target ? ' <span class="tag you">you</span>' : ""}</td>
        <td><div class="cellbar"><div class="bar ${b === d.target ? "" : "other"}"><span style="width:${s.visibility ?? 0}%"></span></div><span>${fmt(s.visibility, "%")}</span></div></td>
        <td class="num">${s.mentioned}/${s.answers}</td><td class="num">${fmt(s.share_of_voice, "%")}</td><td class="num">${fmt(s.avg_position)}</td>
        <td class="num">${fmt(s.first_rate, "%")}</td><td class="num">${fmt(s.sentiment)}</td><td class="num">${fmt(s.citation_share, "%")}</td></tr>`;
    });
    $("#brand-table").innerHTML = html + "</tbody>";
  }

  function renderMatrix() {
    const d = state.data;
    const provs = state.provider ? d.providers.filter((p) => p.id === state.provider) : d.providers;
    $("#matrix-target").textContent = d.target;
    let html = `<thead><tr><th>Prompt</th><th>Type</th>${provs.map((p) => `<th>${esc(p.label)}</th>`).join("")}<th>Brands mentioned</th></tr></thead><tbody>`;
    for (const row of d.prompts) {
      const allBrands = new Set();
      html += `<tr><td class="prompt">${esc(row.text)}</td><td><span class="tag ${row.category === "branded" ? "branded" : ""}">${esc(row.category)}</span></td>`;
      for (const p of provs) {
        const c = row.cells[p.id];
        if (!c || (c.runs === 0 && c.errors)) { html += `<td class="cell err" data-ids="${c ? c.answer_ids.join(",") : ""}">error</td>`; continue; }
        (c.brands || []).forEach((b) => allBrands.add(b));
        const cls = c.mention_rate === 100 ? "yes" : c.mention_rate > 0 ? "partial" : "no";
        const label = c.mentioned ? `#${fmt(c.position)}${c.runs > 1 ? ` · ${c.mention_rate}%` : ""}` : "not mentioned";
        html += `<td class="cell ${cls}" data-ids="${c.answer_ids.join(",")}" title="${c.mentioned}/${c.runs} answers mention ${esc(d.target)}">${label}</td>`;
      }
      html += `<td class="muted">${esc([...allBrands].join(", "))}</td></tr>`;
    }
    const tbl = $("#matrix-table");
    tbl.innerHTML = html + "</tbody>";
    tbl.querySelectorAll("td.cell").forEach((td) => td.addEventListener("click", () => { const ids = td.dataset.ids.split(",").filter(Boolean); if (ids.length) openAnswer(ids.map(Number)); }));
  }

  function renderSources() {
    const d = state.data;
    const provFilter = state.provider;
    let rows = d.sources;
    if (provFilter) rows = rows.filter((s) => s.providers.includes(provFilter));
    rows = rows.slice(0, 40);
    let html = `<thead><tr><th>Domain</th><th>Owner</th><th class="num">Citations</th><th class="num">Answers</th><th>Engines</th></tr></thead><tbody>`;
    for (const s of rows) {
      const ownerTag = s.owner === "other" ? "" : `<span class="tag ${s.owner === d.target ? "own" : "competitor"}">${esc(s.owner)}</span>`;
      html += `<tr><td><a href="https://${esc(s.domain)}" target="_blank" rel="noopener">${esc(s.domain)}</a></td><td>${ownerTag}</td><td class="num">${s.citations}</td><td class="num">${fmt(s.answer_pct, "%")}</td><td class="muted">${esc(s.providers.join(", "))}</td></tr>`;
    }
    $("#sources-table").innerHTML = html + (rows.length ? "" : `<tr><td colspan="5" class="muted">No sources captured. Engines without web search return none.</td></tr>`) + "</tbody>";
  }

  function renderProviders() {
    const d = state.data;
    let html = `<thead><tr><th>Engine</th><th>Model</th><th class="num">Answers</th><th class="num">Errors</th><th class="num">Avg. latency</th><th class="num">Your rank here</th></tr></thead><tbody>`;
    for (const p of d.providers) html += `<tr><td>${esc(p.label)} <span class="muted">${esc(p.id)}</span></td><td>${esc(p.model || "–")}</td><td class="num">${p.ok}/${p.answers}</td><td class="num">${p.errors}</td><td class="num">${p.avg_latency_ms ? p.avg_latency_ms + " ms" : "–"}</td><td class="num">${p.target_rank ? "#" + p.target_rank : "–"}</td></tr>`;
    $("#provider-table").innerHTML = html + "</tbody>";
  }

  async function loadTrend() {
    const d = state.data;
    const t = await getJSON(`/api/trend?brand=${encodeURIComponent(d.target)}`);
    const labels = t.points.map((p) => when(p.started_at));
    const brands = Object.keys(t.series);
    chart("trend-chart", {
      type: "line",
      data: { labels, datasets: brands.map((b, i) => ({ label: b, data: t.series[b], borderColor: b === d.target ? "#6b47ff" : COLORS[(i + 1) % COLORS.length], borderWidth: b === d.target ? 3 : 1.5, tension: 0.25, pointRadius: 3, spanGaps: true })) },
      options: { responsive: true, maintainAspectRatio: false, scales: { y: { beginAtZero: true, max: 100, ticks: { callback: (v) => v + "%" } } }, plugins: { legend: { position: "bottom", labels: { boxWidth: 10 } } } },
    });
  }

  // ---- answer modal --------------------------------------------------------
  async function openAnswer(ids) {
    const answers = await Promise.all(ids.map((id) => getJSON(`/api/answer/${id}`)));
    const d = state.data;
    const brands = d.brands.map((b) => [b.name, ...(b.aliases || [])]).flat().filter(Boolean).sort((a, b) => b.length - a.length);
    const re = brands.length ? new RegExp(`(?<![\\w])(${brands.map((b) => b.replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/[\s-]+/g, "[\\s-]+")).join("|")})(?![\\w])`, "gi") : null;
    const targetNames = new Set([d.target, ...(d.brands.find((b) => b.name === d.target)?.aliases || [])].map((s) => s.toLowerCase().replace(/[\s-]+/g, " ")));
    const body = answers.map((a) => {
      const text = re ? esc(a.text).replace(re, (m) => `<mark class="${targetNames.has(m.toLowerCase().replace(/[\s-]+/g, " ")) ? "" : "other"}">${m}</mark>`) : esc(a.text);
      const ment = a.mentions.map((m) => `${esc(m.brand)} <span class="muted">#${m.position} ×${m.count}</span>${a.sentiment[m.brand] ? ` <span class="sent-${a.sentiment[m.brand]}">${a.sentiment[m.brand]}</span>` : ""}`).join(" · ");
      const cites = a.citations.map((c) => `<a href="${esc(c.url)}" target="_blank" rel="noopener" title="${esc(c.title || c.url)}">${esc(c.domain)}${c.owner && c.owner !== "other" ? " · " + esc(c.owner) : ""}</a>`).join("");
      return `<h3 style="margin:0 0 4px">${esc(a.provider_label)} <span class="muted">${esc(a.model || "")}${a.repeat_index ? " · repeat " + (a.repeat_index + 1) : ""} · ${a.latency_ms} ms</span></h3>
        <div class="muted">${esc(a.prompt_text)}</div>
        ${a.error ? `<pre>${esc(a.error)}</pre>` : `<div class="answer-text">${text}</div>`}
        <div><b>Brands:</b> ${ment || '<span class="muted">none of the tracked brands</span>'}</div>
        <div><b>Sources (${a.citations.length}):</b><div class="chips">${cites || '<span class="muted">none</span>'}</div></div>`;
    }).join("<hr style='border:0;border-top:1px solid #e6e8ef;margin:16px 0'>");
    $("#modal-body").innerHTML = body;
    $("#modal").classList.remove("hidden");
  }

  // ---- wiring -------------------------------------------------------------
  $("#run-select").addEventListener("change", (e) => { state.runId = e.target.value; loadRun().catch(showError); });
  $("#provider-select").addEventListener("change", (e) => { state.provider = e.target.value; render(); });
  $("#refresh-btn").addEventListener("click", () => loadRuns().catch(showError));
  $("#modal-close").addEventListener("click", () => $("#modal").classList.add("hidden"));
  $("#modal").addEventListener("click", (e) => { if (e.target.id === "modal") $("#modal").classList.add("hidden"); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") $("#modal").classList.add("hidden"); });
  function showError(e) { console.error(e); $("#run-subtitle").textContent = "Error: " + e.message; }

  loadRuns().catch(showError);
})();
