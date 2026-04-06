// --- Constants ---

const TYPE_COLORS = {
  claim: "#4A90D9",
  hypothesis: "#9B59B6",
  evidence: "#2ECC71",
  method: "#F39C12",
  critique: "#E74C3C",
  observation: "#95A5A6",
};

const RELATION_COLORS = {
  supports: "#2ECC71",
  contradicts: "#E74C3C",
  extends: "#4A90D9",
  "derives-from": "#95A5A6",
};

// --- State ---

let simulation = null;
let selectedNodeId = null;

// --- Init ---

document.addEventListener("DOMContentLoaded", async () => {
  renderLegend();
  await Promise.all([loadStats(), loadGraph()]);
});

// --- Stats ---

async function loadStats() {
  const res = await fetch("/api/stats");
  const data = await res.json();
  const bar = document.getElementById("stats-bar");

  const typeBreakdown = Object.entries(data.types || {})
    .map(([k, v]) => `${k}: ${v}`)
    .join(", ");

  const accBreakdown = Object.entries(data.acceptance || {})
    .map(([k, v]) => `${k}: ${v}`)
    .join(", ");

  bar.innerHTML = `
    <div class="stat-card">
      <div class="label">Nodes</div>
      <div class="value">${data.node_count}</div>
      <div class="breakdown">${typeBreakdown || "—"}</div>
    </div>
    <div class="stat-card">
      <div class="label">Links</div>
      <div class="value">${data.link_count}</div>
    </div>
    <div class="stat-card">
      <div class="label">Agents</div>
      <div class="value">${data.agent_count}</div>
    </div>
    <div class="stat-card">
      <div class="label">Acceptance</div>
      <div class="value">&nbsp;</div>
      <div class="breakdown">${accBreakdown || "—"}</div>
    </div>
  `;
}

// --- Legend ---

function renderLegend() {
  const legend = document.getElementById("legend");
  let html = '<div class="legend-title">Node Types</div>';
  for (const [type, color] of Object.entries(TYPE_COLORS)) {
    html += `<div class="legend-item"><div class="legend-dot" style="background:${color}"></div>${type}</div>`;
  }
  html += '<div class="legend-title" style="margin-top:8px">Relations</div>';
  for (const [rel, color] of Object.entries(RELATION_COLORS)) {
    html += `<div class="legend-item"><div class="legend-line" style="background:${color}"></div>${rel}</div>`;
  }
  legend.innerHTML = html;
}

// --- Graph ---

async function loadGraph() {
  const res = await fetch("/api/graph");
  const data = await res.json();

  if (data.nodes.length === 0) {
    document.getElementById("graph-panel").innerHTML =
      '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#7b8794">No data in graph. Submit contributions via MCP first.</div>';
    return;
  }

  renderGraph(data);
}

function renderGraph(data) {
  const svg = d3.select("#graph-svg");
  const container = document.getElementById("graph-panel");
  const width = container.clientWidth;
  const height = container.clientHeight;

  svg.attr("viewBox", [0, 0, width, height]);

  // Clear previous
  svg.selectAll("*").remove();

  // Arrow markers
  const defs = svg.append("defs");
  for (const [rel, color] of Object.entries(RELATION_COLORS)) {
    defs
      .append("marker")
      .attr("id", `arrow-${rel}`)
      .attr("viewBox", "0 -5 10 10")
      .attr("refX", 20)
      .attr("refY", 0)
      .attr("markerWidth", 6)
      .attr("markerHeight", 6)
      .attr("orient", "auto")
      .append("path")
      .attr("fill", color)
      .attr("d", "M0,-5L10,0L0,5");
  }

  const g = svg.append("g");

  // Zoom
  svg.call(
    d3.zoom().scaleExtent([0.2, 5]).on("zoom", (e) => {
      g.attr("transform", e.transform);
    })
  );

  // Links
  const link = g
    .append("g")
    .selectAll("line")
    .data(data.links)
    .join("line")
    .attr("stroke", (d) => RELATION_COLORS[d.relation] || "#555")
    .attr("stroke-width", 1.5)
    .attr("stroke-opacity", 0.6)
    .attr("marker-end", (d) => `url(#arrow-${d.relation})`);

  // Nodes
  const node = g
    .append("g")
    .selectAll("circle")
    .data(data.nodes)
    .join("circle")
    .attr("r", (d) => 6 + (d.trust_score || 0.5) * 10)
    .attr("fill", (d) => TYPE_COLORS[d.type] || "#666")
    .attr("stroke", "#0f1117")
    .attr("stroke-width", 1.5)
    .attr("cursor", "pointer")
    .on("click", (event, d) => {
      event.stopPropagation();
      selectNode(d.id);
    })
    .call(
      d3.drag()
        .on("start", (event, d) => {
          if (!event.active) simulation.alphaTarget(0.3).restart();
          d.fx = d.x;
          d.fy = d.y;
        })
        .on("drag", (event, d) => {
          d.fx = event.x;
          d.fy = event.y;
        })
        .on("end", (event, d) => {
          if (!event.active) simulation.alphaTarget(0);
          d.fx = null;
          d.fy = null;
        })
    );

  // Labels
  const label = g
    .append("g")
    .selectAll("text")
    .data(data.nodes)
    .join("text")
    .text((d) => d.type)
    .attr("font-size", 10)
    .attr("fill", "#aaa")
    .attr("dx", 12)
    .attr("dy", 4)
    .attr("pointer-events", "none");

  // Tooltip on hover
  node.append("title").text((d) => {
    const trust = d.trust_score != null ? d.trust_score.toFixed(4) : "—";
    return `${d.type} (${d.agent_id})\nTrust: ${trust}\n${d.content_text}`;
  });

  // Simulation
  simulation = d3
    .forceSimulation(data.nodes)
    .force(
      "link",
      d3.forceLink(data.links).id((d) => d.id).distance(100)
    )
    .force("charge", d3.forceManyBody().strength(-200))
    .force("center", d3.forceCenter(width / 2, height / 2))
    .force("collision", d3.forceCollide().radius(20))
    .on("tick", () => {
      link
        .attr("x1", (d) => d.source.x)
        .attr("y1", (d) => d.source.y)
        .attr("x2", (d) => d.target.x)
        .attr("y2", (d) => d.target.y);

      node.attr("cx", (d) => d.x).attr("cy", (d) => d.y);
      label.attr("x", (d) => d.x).attr("y", (d) => d.y);
    });

  // Click background to deselect
  svg.on("click", () => {
    selectedNodeId = null;
    node.attr("stroke", "#0f1117").attr("stroke-width", 1.5);
    showEmptyDetail();
  });
}

// --- Node selection ---

async function selectNode(nodeId) {
  selectedNodeId = nodeId;

  // Highlight
  d3.selectAll("#graph-svg circle")
    .attr("stroke", (d) => (d.id === nodeId ? "#fff" : "#0f1117"))
    .attr("stroke-width", (d) => (d.id === nodeId ? 3 : 1.5));

  // Fetch detail
  const res = await fetch(`/api/nodes/${encodeURIComponent(nodeId)}`);
  const data = await res.json();
  renderDetail(data);
}

function showEmptyDetail() {
  const panel = document.getElementById("detail-panel");
  panel.className = "detail-panel empty";
  panel.innerHTML = "Click a node to see details";
}

function renderDetail(data) {
  const panel = document.getElementById("detail-panel");
  panel.className = "detail-panel";

  const typeColor = TYPE_COLORS[data.type] || "#666";
  const accClass = data.acceptance || "unknown";
  const trust = data.trust_score != null ? data.trust_score.toFixed(4) : "—";

  let patternsHtml = (data.patterns || [])
    .map(
      (p) =>
        `<div class="pattern-item"><span class="pattern-status ${p.status}">${p.status}</span><span>${p.id}: ${p.reason}</span></div>`
    )
    .join("");

  let incomingHtml = (data.incoming_links || [])
    .map(
      (l) =>
        `<div class="link-item"><span class="relation relation-${l.relation}">${l.relation}</span> from <code>${l.source_id.slice(0, 16)}...</code> (${l.agent_id})</div>`
    )
    .join("") || '<div style="color:#7b8794;font-size:12px">None</div>';

  let outgoingHtml = (data.outgoing_links || [])
    .map(
      (l) =>
        `<div class="link-item"><span class="relation relation-${l.relation}">${l.relation}</span> to <code>${l.target_id.slice(0, 16)}...</code> (${l.agent_id})</div>`
    )
    .join("") || '<div style="color:#7b8794;font-size:12px">None</div>';

  panel.innerHTML = `
    <div class="detail-section">
      <h3>Node</h3>
      <div class="field"><span class="type-badge" style="background:${typeColor}">${data.type}</span></div>
      <div class="field"><span class="key">Trust:</span> ${trust} <span class="trust-badge ${accClass}">${accClass}</span></div>
      <div class="field"><span class="key">Agent:</span> ${data.agent_id}</div>
      <div class="field"><span class="key">ID:</span> <code style="font-size:11px;word-break:break-all">${data.id}</code></div>
    </div>

    <div class="detail-section">
      <h3>Content</h3>
      <div class="content-text">${escapeHtml(data.content_text)}</div>
    </div>

    <div class="detail-section">
      <h3>Pattern Detection</h3>
      ${patternsHtml || '<div style="color:#7b8794;font-size:12px">No patterns checked</div>'}
    </div>

    <div class="detail-section">
      <h3>Incoming Links (${data.incoming_links?.length || 0})</h3>
      ${incomingHtml}
    </div>

    <div class="detail-section">
      <h3>Outgoing Links (${data.outgoing_links?.length || 0})</h3>
      ${outgoingHtml}
    </div>
  `;
}

// --- Recompute ---

async function recompute() {
  const btn = document.getElementById("recompute-btn");
  btn.disabled = true;
  btn.textContent = "Computing...";
  try {
    await fetch("/api/recompute", { method: "POST" });
    await Promise.all([loadStats(), loadGraph()]);
  } finally {
    btn.disabled = false;
    btn.textContent = "Recompute EpiRank";
  }
  if (selectedNodeId) {
    await selectNode(selectedNodeId);
  }
}

// --- Util ---

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text || "";
  return div.innerHTML;
}
