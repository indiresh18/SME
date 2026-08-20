/* SME Anchor - Supplier portal */
requireRole("supplier");
const SUPPLIER_ID = getSupplierId();
if (!SUPPLIER_ID) window.location.href = "index.html";

document.getElementById("logout-btn").addEventListener("click", logout);

document.querySelectorAll(".nav-item[data-view]").forEach(item => {
  item.addEventListener("click", () => switchView(item.dataset.view));
});

function switchView(view) {
  document.querySelectorAll(".nav-item[data-view]").forEach(i => i.classList.toggle("active", i.dataset.view === view));
  document.querySelectorAll("section[data-panel]").forEach(s => s.classList.toggle("hidden", s.dataset.panel !== view));
  const loaders = { dashboard: loadDashboard, orders: loadOrders, products: loadProducts, profile: loadProfile };
  if (loaders[view]) loaders[view]();
}

async function loadDashboard() {
  const data = await apiGet(`/suppliers/${SUPPLIER_ID}/dashboard`);
  document.getElementById("supplier-name-label").textContent = data.supplier.name;
  document.getElementById("topbar-supplier-name").textContent = `${data.supplier.name} Dashboard`;
  document.getElementById("supplier-chip-name").textContent = data.supplier.name;
  document.getElementById("supplier-avatar").textContent = data.supplier.name.slice(-1);

  const c = data.status_counts;
  const cards = [
    { icon: "🆕", label: "Today's Orders", value: data.today_orders },
    { icon: "⏳", label: "Pending Orders", value: c.pending_approval },
    { icon: "✅", label: "Accepted Orders", value: c.accepted },
    { icon: "🚚", label: "Shipped Orders", value: c.shipped },
    { icon: "📦", label: "Delivered Orders", value: c.delivered },
    { icon: "💰", label: "Revenue", value: formatCurrency(data.revenue) },
  ];
  document.getElementById("supplier-kpis").innerHTML = cards.map(k => `
    <div class="kpi-card">
      <div class="kpi-top"><div class="kpi-icon">${k.icon}</div></div>
      <div class="kpi-label">${k.label}</div>
      <div class="kpi-value">${k.value}</div>
    </div>`).join("");
}

async function loadOrders() {
  const pos = await apiGet(`/purchase-orders?supplier_id=${SUPPLIER_ID}`);
  // suppliers only see orders that have been approved by the owner (accepted/shipped/delivered)
  // plus newly created ones awaiting acceptance are represented as "accepted" stage trigger from owner approval.
  document.getElementById("supplier-po-tbody").innerHTML = pos
    .filter(po => po.status !== "pending_approval")
    .map(po => `
    <tr>
      <td>PO-${1000 + po.id}</td>
      <td>${escapeHtml(po.product_name)}</td>
      <td>${po.qty}</td>
      <td>${formatCurrency(po.total)}</td>
      <td>${po.delivery_days} day(s)</td>
      <td><span class="badge ${statusBadgeClass(po.status)}">${statusLabel(po.status)}</span></td>
      <td>${supplierActionButtons(po)}</td>
    </tr>`).join("") || `<tr><td colspan="7" class="empty-state">No orders yet from SME Anchor.</td></tr>`;
}

function supplierActionButtons(po) {
  if (po.status === "pending_supplier") {
    return `<button class="btn btn-success btn-sm" onclick="acceptOrder(${po.id})">Accept Order</button>
            <button class="btn btn-danger btn-sm" onclick="rejectOrder(${po.id})">Reject Order</button>`;
  }
  if (po.status === "accepted") return `<button class="btn btn-secondary btn-sm" onclick="shipOrder(${po.id})">Mark as Shipped</button>`;
  if (po.status === "shipped") return `<button class="btn btn-primary btn-sm" onclick="deliverOrder(${po.id})">Mark as Delivered</button>`;
  return "";
}

window.acceptOrder = async (id) => {
  try { await apiPost(`/purchase-orders/${id}/supplier-accept`); showToast("Order accepted.", "success"); loadOrders(); loadDashboard(); }
  catch (e) { showToast(e.message, "error"); }
};
window.rejectOrder = async (id) => {
  try { await apiPost(`/purchase-orders/${id}/supplier-reject`); showToast("Order rejected.", "success"); loadOrders(); loadDashboard(); }
  catch (e) { showToast(e.message, "error"); }
};
window.shipOrder = async (id) => {
  try { await apiPost(`/purchase-orders/${id}/ship`); showToast("Order marked as shipped.", "success"); loadOrders(); loadDashboard(); }
  catch (e) { showToast(e.message, "error"); }
};
window.deliverOrder = async (id) => {
  try { await apiPost(`/purchase-orders/${id}/deliver`); showToast("Order delivered — buyer inventory updated.", "success"); loadOrders(); loadDashboard(); }
  catch (e) { showToast(e.message, "error"); }
};

async function loadProducts() {
  const pos = await apiGet(`/purchase-orders?supplier_id=${SUPPLIER_ID}`);
  // Show distinct products this supplier has offered via any historical PO plus a live sample using product offers endpoint isn't per-supplier;
  // fall back: query all products, then for each check offers (limited to avoid heavy calls -> use first 40 products for demo speed).
  const productsData = await apiGet("/products?page=1&page_size=40");
  const rows = [];
  for (const p of productsData.items) {
    const offerData = await apiGet(`/products/${p.id}/offers`);
    const mine = offerData.offers.find(o => o.supplier_id == SUPPLIER_ID);
    if (mine) rows.push({ product: p, offer: mine });
  }
  document.getElementById("supplier-products-tbody").innerHTML = rows.map(r => `
    <tr>
      <td>${escapeHtml(r.product.name)}</td>
      <td>₹${r.offer.price}</td>
      <td>${r.offer.delivery_days} day(s)</td>
      <td>${r.offer.available_qty}</td>
    </tr>`).join("") || `<tr><td colspan="4" class="empty-state">No offers found in this sample.</td></tr>`;
}

async function loadProfile() {
  const data = await apiGet(`/suppliers/${SUPPLIER_ID}/dashboard`);
  document.getElementById("supplier-profile-card").innerHTML = `
    <div class="cart-total-row"><span>Name</span><b>${data.supplier.name}</b></div>
    <div class="cart-total-row"><span>Reliability</span><b>${data.supplier.reliability}%</b></div>
    <div class="cart-total-row"><span>Rating</span><b>⭐ ${data.supplier.rating}</b></div>
    <div class="cart-total-row"><span>Products Supplied</span><b>${data.products_supplied}</b></div>
    <div class="cart-total-row grand"><span>Total Revenue</span><b>${formatCurrency(data.revenue)}</b></div>
  `;
}

loadDashboard();
