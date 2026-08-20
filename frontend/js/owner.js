/* SME Anchor - Owner portal */
requireRole("owner");

const state = {
  view: "dashboard",
  salesRange: "7d",
  products: [],
  suppliers: [],
};

document.getElementById("logout-btn").addEventListener("click", logout);

/* ---------------- Navigation ---------------- */
document.querySelectorAll(".nav-item[data-view]").forEach(item => {
  item.addEventListener("click", () => switchView(item.dataset.view));
});

function switchView(view) {
  state.view = view;
  document.querySelectorAll(".nav-item[data-view]").forEach(i => i.classList.toggle("active", i.dataset.view === view));
  document.querySelectorAll("section[data-panel]").forEach(s => s.classList.toggle("hidden", s.dataset.panel !== view));
  loadView(view);
}

function loadView(view) {
  const loaders = {
    dashboard: loadDashboard, products: loadProducts, inventory: loadInventory,
    sales: loadSales, customers: loadCustomers, suppliers: loadSuppliersView,
    purchases: loadPurchaseOrders, finance: loadFinance, reports: loadReports,
  };
  if (loaders[view]) loaders[view]();
}

/* ---------------- Dashboard ---------------- */
async function loadDashboard() {
  const kpis = await apiGet("/dashboard");
  const grid = document.getElementById("kpi-grid");
  const cards = [
    { icon: "💵", label: "Available Cash", value: formatCurrency(kpis.available_cash) },
    { icon: "🛍️", label: "Today's Sales", value: formatCurrency(kpis.today_sales) },
    { icon: "📈", label: "Today's Profit", value: formatCurrency(kpis.today_profit) },
    { icon: "📦", label: "Inventory Value", value: formatCurrency(kpis.inventory_value) },
    { icon: "🧾", label: "Pending Orders", value: kpis.pending_orders, cls: kpis.pending_orders > 5 ? "warn" : "" },
    { icon: "⚠️", label: "Low Stock Items", value: kpis.low_stock_items, cls: kpis.low_stock_items > 0 ? "crit" : "" },
  ];
  grid.innerHTML = cards.map(c => `
    <div class="kpi-card ${c.cls || ""}">
      <div class="kpi-top"><div class="kpi-icon">${c.icon}</div></div>
      <div class="kpi-label">${c.label}</div>
      <div class="kpi-value">${c.value}</div>
    </div>`).join("");

  await loadSalesChart();
  await loadLowStockList();
}

async function loadSalesChart() {
  const data = await apiGet(`/sales/chart?range=${state.salesRange}`);
  const changeEl = document.getElementById("sales-change");
  const pct = data.change_pct;
  const sign = pct >= 0 ? "+" : "";
  changeEl.innerHTML = `<span style="color:${pct >= 0 ? 'var(--green)' : 'var(--red)'}; font-weight:700;">${sign}${pct}%</span> compared with previous period`;
  drawLineChart(document.getElementById("sales-canvas"), data.series.map(d => d.sales));
}

document.querySelectorAll("#range-tabs .pill-tab").forEach(tab => {
  tab.addEventListener("click", () => {
    document.querySelectorAll("#range-tabs .pill-tab").forEach(t => t.classList.remove("active"));
    tab.classList.add("active");
    state.salesRange = tab.dataset.range;
    loadSalesChart();
  });
});

function drawLineChart(canvas, values) {
  const ctx = canvas.getContext("2d");
  const dpr = window.devicePixelRatio || 1;
  const cssWidth = canvas.clientWidth || 640;
  const cssHeight = 220;
  canvas.width = cssWidth * dpr;
  canvas.height = cssHeight * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, cssWidth, cssHeight);

  if (!values.length) return;
  const padding = 24;
  const max = Math.max(...values, 1);
  const min = 0;
  const stepX = (cssWidth - padding * 2) / Math.max(values.length - 1, 1);

  const points = values.map((v, i) => {
    const x = padding + i * stepX;
    const y = cssHeight - padding - ((v - min) / (max - min || 1)) * (cssHeight - padding * 2);
    return [x, y];
  });

  // area fill
  const grad = ctx.createLinearGradient(0, 0, 0, cssHeight);
  grad.addColorStop(0, "rgba(47,127,224,0.25)");
  grad.addColorStop(1, "rgba(47,127,224,0.02)");
  ctx.beginPath();
  ctx.moveTo(points[0][0], cssHeight - padding);
  points.forEach(p => ctx.lineTo(p[0], p[1]));
  ctx.lineTo(points[points.length - 1][0], cssHeight - padding);
  ctx.closePath();
  ctx.fillStyle = grad;
  ctx.fill();

  // line
  ctx.beginPath();
  points.forEach((p, i) => (i === 0 ? ctx.moveTo(p[0], p[1]) : ctx.lineTo(p[0], p[1])));
  ctx.strokeStyle = "#2f7fe0";
  ctx.lineWidth = 2.5;
  ctx.lineJoin = "round";
  ctx.stroke();

  // dots
  points.forEach(p => {
    ctx.beginPath();
    ctx.arc(p[0], p[1], 3, 0, Math.PI * 2);
    ctx.fillStyle = "#2f7fe0";
    ctx.fill();
  });
}

async function loadLowStockList() {
  const inv = await apiGet("/inventory");
  const low = inv.items.filter(i => i.status !== "Healthy").sort((a, b) => a.coverage_days - b.coverage_days).slice(0, 6);
  const el = document.getElementById("low-stock-list");
  if (!low.length) {
    el.innerHTML = `<div class="empty-state">All products are healthily stocked 🎉</div>`;
    return;
  }
  el.innerHTML = low.map(p => `
    <div class="flex-between" style="padding:10px 0;border-bottom:1px solid var(--gray-border);">
      <div>
        <div style="font-size:13px;font-weight:600;color:var(--navy);">${escapeHtml(p.name)}</div>
        <div style="font-size:11px;color:var(--gray-muted);">${p.stock} in stock · ${p.coverage_days}d coverage</div>
      </div>
      <span class="badge ${statusBadgeClass(p.status)}">${p.status}</span>
    </div>`).join("");
}

/* ---------------- Products ---------------- */
async function loadProducts(q = "") {
  const data = await apiGet(`/products?page=1&page_size=100${q ? "&q=" + encodeURIComponent(q) : ""}`);
  state.products = data.items;
  document.getElementById("products-tbody").innerHTML = data.items.map(p => `
    <tr>
      <td><b>${escapeHtml(p.name)}</b><div class="muted" style="font-size:11px;">${p.sku}</div></td>
      <td>${p.category}</td>
      <td>${formatCurrency(p.price)}</td>
      <td>${p.stock}</td>
      <td>⭐ ${p.rating}</td>
    </tr>`).join("");
}
document.getElementById("products-search").addEventListener("input", (e) => loadProducts(e.target.value));

/* ---------------- Inventory ---------------- */
async function loadInventory() {
  const inv = await apiGet("/inventory");
  document.getElementById("inventory-tbody").innerHTML = inv.items.map(p => `
    <tr>
      <td><b>${escapeHtml(p.name)}</b></td>
      <td>${p.category}</td>
      <td>${p.stock}</td>
      <td>${p.min_stock}</td>
      <td>${p.daily_demand}/day</td>
      <td>${p.coverage_days}d</td>
      <td><span class="badge ${statusBadgeClass(p.status)}">${p.status}</span></td>
      <td><button class="btn btn-secondary btn-sm" onclick="goToSupplierCompare(${p.id})">Purchase</button></td>
    </tr>`).join("");
}

window.goToSupplierCompare = function (productId) {
  switchView("suppliers");
  setTimeout(() => {
    const select = document.getElementById("po-product-select");
    select.value = productId;
    select.dispatchEvent(new Event("change"));
  }, 150);
};

/* ---------------- Sales ---------------- */
async function loadSales() {
  const inv = await apiGet("/inventory"); // no-op warmup not needed but harmless
  const chart = await apiGet("/sales/chart?range=30d");
  // fetch recent sales via a lightweight endpoint substitute: reuse dashboard + purchase orders not available,
  // so we approximate using chart series is insufficient; call dedicated listing through fetch of raw table isn't exposed,
  // fallback: show daily aggregated rows.
  const tbody = document.getElementById("sales-tbody");
  tbody.innerHTML = chart.series.slice().reverse().map(row => `
    <tr>
      <td colspan="2">Day summary</td>
      <td>—</td>
      <td>${formatCurrency(row.sales)}</td>
      <td>${formatCurrency(row.profit)}</td>
      <td>${row.day}</td>
    </tr>`).join("") || `<tr><td colspan="6" class="empty-state">No sales yet.</td></tr>`;
}

/* ---------------- Customers ---------------- */
async function loadCustomers() {
  const customers = await apiGet("/customers");
  document.getElementById("customers-tbody").innerHTML = customers.map(c => `
    <tr><td>${escapeHtml(c.name)}</td><td>${escapeHtml(c.email || "")}</td></tr>`).join("");
}

/* ---------------- Suppliers / Manual Purchase ---------------- */
async function loadSuppliersView() {
  if (!state.products.length) {
    const data = await apiGet("/products?page=1&page_size=200");
    state.products = data.items;
  }
  const select = document.getElementById("po-product-select");
  select.innerHTML = state.products.map(p => `<option value="${p.id}">${escapeHtml(p.name)}</option>`).join("");
  select.onchange = () => renderSupplierCompare(select.value);
  if (state.products.length) renderSupplierCompare(select.value);
}

async function renderSupplierCompare(productId) {
  const data = await apiGet(`/products/${productId}/offers`);
  const grid = document.getElementById("supplier-compare-grid");
  if (!data.offers.length) {
    grid.innerHTML = `<div class="empty-state">No supplier currently offers this product.</div>`;
    return;
  }
  grid.innerHTML = data.offers.map(o => `
    <div class="supplier-card ${o.id === data.best_offer_id ? "best" : ""}">
      ${o.id === data.best_offer_id ? '<div class="best-tag">Best Match</div>' : ""}
      <div class="sname">${o.supplier_name}</div>
      <div class="srow"><span>Price</span><b>₹${o.price}/unit</b></div>
      <div class="srow"><span>Delivery</span><b>${o.delivery_days}d</b></div>
      <div class="srow"><span>Reliability</span><b>${o.reliability}%</b></div>
      <div class="srow"><span>Available</span><b>${o.available_qty}</b></div>
      <button class="btn btn-primary btn-sm btn-block mt-8" onclick="openPoBuilder(${JSON.stringify(data.product).replace(/"/g, '&quot;')}, ${JSON.stringify(o).replace(/"/g, '&quot;')})">Select</button>
    </div>`).join("");
}

window.openPoBuilder = function (product, offer) {
  const wrap = document.getElementById("po-builder");
  wrap.classList.remove("hidden");
  const body = document.getElementById("po-builder-body");
  body.innerHTML = `
    <div class="grid-2" style="grid-template-columns:1fr 1fr;">
      <div>
        <div class="muted" style="font-size:12px;">Product</div>
        <div style="font-weight:700;">${escapeHtml(product.name)}</div>
      </div>
      <div>
        <div class="muted" style="font-size:12px;">Supplier</div>
        <div style="font-weight:700;">${offer.supplier_name}</div>
      </div>
    </div>
    <div class="mt-16">
      <label class="muted" style="font-size:12px;">Quantity</label>
      <input type="number" id="po-qty" value="50" min="1" style="width:100%;padding:9px 12px;border:1px solid var(--gray-border);border-radius:10px;margin-top:4px;" />
    </div>
    <div class="mt-16" id="po-summary"></div>
    <button class="btn btn-primary btn-block mt-16" id="po-create-btn">Create Purchase Order</button>
  `;
  const updateSummary = () => {
    const qty = parseInt(document.getElementById("po-qty").value || "0", 10);
    const total = qty * offer.price;
    document.getElementById("po-summary").innerHTML = `
      <div class="card" style="padding:14px;background:var(--blue-50);border:none;">
        <div class="cart-total-row"><span>Unit price</span><span>₹${offer.price}</span></div>
        <div class="cart-total-row"><span>Delivery time</span><span>${offer.delivery_days} day(s)</span></div>
        <div class="cart-total-row grand"><span>Total cost</span><span>${formatCurrency(total)}</span></div>
      </div>`;
  };
  document.getElementById("po-qty").addEventListener("input", updateSummary);
  updateSummary();

  document.getElementById("po-create-btn").onclick = async () => {
    const qty = parseInt(document.getElementById("po-qty").value || "0", 10);
    if (qty <= 0) { showToast("Enter a valid quantity", "error"); return; }
    try {
      await apiPost("/purchase-orders", {
        product_id: product.id, supplier_id: offer.supplier_id, qty,
        reason: "Manual purchase created by owner.",
      });
      showToast("Purchase order created — awaiting your approval.", "success");
      wrap.classList.add("hidden");
      switchView("purchases");
    } catch (e) {
      showToast(e.message, "error");
    }
  };
};

/* ---------------- Purchase Orders ---------------- */
async function loadPurchaseOrders() {
  const pos = await apiGet("/purchase-orders");
  document.getElementById("po-tbody").innerHTML = pos.map(po => `
    <tr>
      <td>PO-${1000 + po.id}</td>
      <td>${escapeHtml(po.product_name)}</td>
      <td>${escapeHtml(po.supplier_name)}</td>
      <td>${po.qty}</td>
      <td>${formatCurrency(po.total)}</td>
      <td><span class="badge ${statusBadgeClass(po.status)}">${statusLabel(po.status)}</span></td>
      <td>${timeAgo(po.updated_at)}</td>
      <td>${po.status === "pending_approval" ? `
        <button class="btn btn-success btn-sm" onclick="approvePo(${po.id})">Approve</button>
        <button class="btn btn-danger btn-sm" onclick="rejectPo(${po.id})">Reject</button>` : ""}
      </td>
    </tr>`).join("") || `<tr><td colspan="8" class="empty-state">No purchase orders yet.</td></tr>`;
}

window.approvePo = async (id) => {
  try { await apiPost(`/purchase-orders/${id}/approve`); showToast("Purchase order approved.", "success"); loadPurchaseOrders(); loadDashboard(); }
  catch (e) { showToast(e.message, "error"); }
};
window.rejectPo = async (id) => {
  try { await apiPost(`/purchase-orders/${id}/reject`); showToast("Purchase order rejected.", "success"); loadPurchaseOrders(); }
  catch (e) { showToast(e.message, "error"); }
};

/* ---------------- Finance ---------------- */
async function loadFinance() {
  const kpis = await apiGet("/dashboard");
  const grid = document.getElementById("finance-kpis");
  grid.innerHTML = `
    <div class="kpi-card"><div class="kpi-icon">💵</div><div class="kpi-label">Available Cash</div><div class="kpi-value">${formatCurrency(kpis.available_cash)}</div></div>
    <div class="kpi-card"><div class="kpi-icon">📦</div><div class="kpi-label">Inventory Value</div><div class="kpi-value">${formatCurrency(kpis.inventory_value)}</div></div>
    <div class="kpi-card"><div class="kpi-icon">📈</div><div class="kpi-label">Today's Profit</div><div class="kpi-value">${formatCurrency(kpis.today_profit)}</div></div>
  `;
}

/* ---------------- Reports ---------------- */
async function loadReports() {
  const reply = await apiPost("/ai/chat", { session_id: "reports-internal", message: "Show me my top-selling products." });
  // parse text fallback if needed; but we also have dashboard for numbers. Simple: re-derive via chat text.
  const tbody = document.getElementById("reports-tbody");
  const lines = reply.text.split("\n").filter(l => /^\d+\./.test(l));
  tbody.innerHTML = lines.map(l => {
    const m = l.match(/^(\d+)\.\s(.+?)\s—\s(\d+)\sunits/);
    if (!m) return "";
    return `<tr><td>${m[1]}</td><td>${escapeHtml(m[2])}</td><td>${m[3]}</td></tr>`;
  }).join("") || `<tr><td colspan="3" class="empty-state">No sales recorded yet.</td></tr>`;
}

/* ---------------- Settings ---------------- */
document.getElementById("reset-demo-btn").addEventListener("click", async () => {
  if (!confirm("This will reset all demo data. Continue?")) return;
  await apiPost("/admin/reset");
  showToast("Demo data reset.", "success");
  loadView(state.view);
});

/* ---------------- AI Anchor dock ---------------- */
const SESSION_ID = getSessionId();
const aiMessages = document.getElementById("ai-messages");
const aiDock = document.getElementById("ai-dock");
const suggestions = [
  "What should I purchase today?",
  "Which products are running low?",
  "Why did my profit decrease?",
  "Which supplier is best for oil?",
  "How are sales today?",
  "Show me my top-selling products.",
];

document.getElementById("ai-suggestions").innerHTML = suggestions.map(s =>
  `<div class="ai-suggestion-chip" onclick="sendAiMessage(${JSON.stringify(s)})">${s}</div>`).join("");

document.getElementById("ai-header-toggle").addEventListener("click", () => {
  aiDock.classList.toggle("collapsed");
  document.getElementById("ai-toggle-caret").textContent = aiDock.classList.contains("collapsed") ? "▸" : "▾";
});

document.getElementById("ai-send").addEventListener("click", () => {
  const input = document.getElementById("ai-input");
  if (input.value.trim()) { sendAiMessage(input.value.trim()); input.value = ""; }
});
document.getElementById("ai-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter") document.getElementById("ai-send").click();
});

function appendUserBubble(text) {
  const div = document.createElement("div");
  div.className = "ai-msg user";
  div.innerHTML = `<div class="mini-avatar">🧭</div><div class="bubble">${escapeHtml(text)}</div>`;
  aiMessages.appendChild(div);
  aiMessages.scrollTop = aiMessages.scrollHeight;
}

function appendAiReply(reply) {
  const div = document.createElement("div");
  div.className = "ai-msg";
  let inner = `<div class="mini-avatar">⚓</div><div>`;
  inner += `<div class="bubble">${escapeHtml(reply.text).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>")}</div>`;

  if (reply.type === "restock_recommendation" && reply.data) {
    inner += `<div class="ai-card mt-8">
      ${reply.data.priority_products.map(p => `<div class="row"><span>${escapeHtml(p.name)}</span><b>${p.status}</b></div>`).join("")}
      </div>
      <div class="ai-card-actions">
        <button class="btn btn-primary btn-sm" onclick="sendAiMessage('Prepare the order')">Prepare Order</button>
        <button class="btn btn-secondary btn-sm" onclick="switchView('suppliers')">Show Supplier Comparison</button>
      </div>`;
  }

  if (reply.type === "supplier_comparison" && reply.data) {
    inner += `<div class="ai-card mt-8">
      ${reply.data.offers.map(o => `<div class="row"><span>${o.supplier_name}${o.is_best ? " ⭐" : ""}</span><b>₹${o.price} · ${o.delivery_days}d</b></div>`).join("")}
      </div>`;
  }

  if (reply.type === "purchase_order_preview" && reply.data) {
    const d = reply.data;
    inner += `<div class="ai-card mt-8">
        <div class="row"><span>Product</span><b>${escapeHtml(d.product_name)}</b></div>
        <div class="row"><span>Quantity</span><b>${d.qty} units</b></div>
        <div class="row"><span>Supplier</span><b>${escapeHtml(d.supplier_name)}</b></div>
        <div class="row"><span>Unit Price</span><b>₹${d.unit_price}</b></div>
        <div class="row"><span>Total</span><b>${formatCurrency(d.total)}</b></div>
        <div class="row"><span>Delivery</span><b>${d.delivery_days} day(s)</b></div>
      </div>
      <div class="ai-card-actions">
        <button class="btn btn-success btn-sm" onclick="confirmAiPurchase()">Approve Purchase</button>
        <button class="btn btn-danger btn-sm" onclick="this.closest('.ai-msg').querySelector('.ai-card-actions').remove()">Reject</button>
      </div>`;
  }

  inner += `</div>`;
  div.innerHTML = inner;
  aiMessages.appendChild(div);
  aiMessages.scrollTop = aiMessages.scrollHeight;
}

window.sendAiMessage = async function (text) {
  appendUserBubble(text);
  try {
    const reply = await apiPost("/ai/chat", { session_id: SESSION_ID, message: text });
    appendAiReply(reply);
  } catch (e) {
    showToast(e.message, "error");
  }
};

window.confirmAiPurchase = async function () {
  try {
    await apiPost("/ai/confirm-purchase", { session_id: SESSION_ID });
    showToast("Purchase order approved and sent to supplier.", "success");
    loadDashboard();
  } catch (e) {
    showToast(e.message, "error");
  }
};

/* ---------------- Global search (products quick filter) ---------------- */
document.getElementById("global-search").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && e.target.value.trim()) {
    switchView("products");
    setTimeout(() => {
      document.getElementById("products-search").value = e.target.value;
      loadProducts(e.target.value);
    }, 100);
  }
});

/* ---------------- init ---------------- */
loadDashboard();
