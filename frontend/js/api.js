/* SME Anchor - shared frontend utilities */
const API_BASE = "/api";

async function apiGet(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`GET ${path} failed`);
  return res.json();
}

async function apiPost(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: "Request failed" }));
    throw new Error(err.error || "Request failed");
  }
  return res.json();
}

function formatCurrency(value) {
  const n = Number(value || 0);
  return "₹" + n.toLocaleString("en-IN", { maximumFractionDigits: 2, minimumFractionDigits: 0 });
}

function timeAgo(iso) {
  const d = new Date(iso);
  const diffMs = Date.now() - d.getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function statusBadgeClass(status) {
  const map = {
    Healthy: "healthy", Warning: "warning", Critical: "critical",
    pending_approval: "warning", pending_supplier: "info", accepted: "info",
    shipped: "info", delivered: "healthy", rejected: "critical",
  };
  return map[status] || "neutral";
}

function statusLabel(status) {
  const map = {
    pending_approval: "Pending Owner Approval", pending_supplier: "Awaiting Supplier",
    accepted: "Accepted by Supplier", shipped: "Shipped", delivered: "Delivered", rejected: "Rejected",
  };
  return map[status] || status;
}

function showToast(message, type = "info") {
  let stack = document.querySelector(".toast-stack");
  if (!stack) {
    stack = document.createElement("div");
    stack.className = "toast-stack";
    document.body.appendChild(stack);
  }
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.textContent = message;
  stack.appendChild(toast);
  setTimeout(() => toast.remove(), 3500);
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function getSessionId() {
  let sid = localStorage.getItem("sme_ai_session");
  if (!sid) {
    sid = "sess_" + Math.random().toString(36).slice(2);
    localStorage.setItem("sme_ai_session", sid);
  }
  return sid;
}

function getRole() {
  return sessionStorage.getItem("sme_role");
}

function getSupplierId() {
  return sessionStorage.getItem("sme_supplier_id");
}

function requireRole(role) {
  const current = getRole();
  if (current !== role) {
    window.location.href = "index.html";
  }
}

function logout() {
  sessionStorage.removeItem("sme_role");
  sessionStorage.removeItem("sme_supplier_id");
  window.location.href = "index.html";
}
